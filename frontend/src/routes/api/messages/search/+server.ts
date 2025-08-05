import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking,
  paginate,
  deduplicateBy
} from '$lib/bff-utils';
import type { 
  SearchAggregateData, 
  SearchResult, 
  SearchFacets, 
  PaginationInfo 
} from '$lib/bff-types';
import type { Message, Room, User } from '$lib/types';

// 跨房間搜尋聚合 API
export const POST: RequestHandler = withPerformanceTracking(async ({ cookies, request, url }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  bffBackendClient.setAuth(token);
  
  try {
    const searchParams = await request.json();
    
    // 驗證搜尋參數
    const validatedParams = validateSearchParams(searchParams);
    if (!validatedParams.valid) {
      return json(
        createBFFError('VALIDATION_ERROR', validatedParams.error!), 
        { status: 400 }
      );
    }
    
    // 並行執行搜尋和相關查詢
    const searchData = await bffBackendClient.parallel({
      // 主要搜尋結果
      searchResults: () => performMainSearch(validatedParams.params!),
      // 用戶有權限的房間列表
      userRooms: () => bffBackendClient.request<Room[]>('/api/rooms/'),
      // 搜尋建議
      suggestions: () => generateSearchSuggestions(validatedParams.params!.keyword),
      // 相關房間
      relatedRooms: () => findRelatedRooms(validatedParams.params!),
    });
    
    // 過濾搜尋結果（只保留用戶有權限的房間）
    const userRoomIds = new Set(searchData.userRooms?.map(room => room.id) || []);
    const filteredResults = (searchData.searchResults || [])
      .filter((result: any) => userRoomIds.has(result.room_id));
    
    // 轉換搜尋結果
    const searchResults: SearchResult[] = transformSearchResults(
      filteredResults, 
      searchData.userRooms || []
    );
    
    // 生成分頁資訊
    const { items: paginatedResults, pagination } = paginate(
      searchResults,
      validatedParams.params!.page || 1,
      validatedParams.params!.pageSize || 20
    );
    
    // 生成搜尋面向（facets）
    const facets: SearchFacets = generateSearchFacets(searchResults);
    
    // 組合聚合資料
    const aggregateData: SearchAggregateData = {
      results: paginatedResults,
      facets,
      pagination,
      suggestions: searchData.suggestions || [],
      relatedRooms: searchData.relatedRooms || [],
    };
    
    // 設置快取頭部（5分鐘快取）
    const cacheKey = generateSearchCacheKey(validatedParams.params!);
    const response = json(createBFFResponse(aggregateData), {
      headers: {
        'Cache-Control': 'max-age=300, s-maxage=600',
        'ETag': `"search_${cacheKey}"`,
        'Vary': 'Authorization',
      },
    });
    
    return response;
    
  } catch (error: any) {
    console.error('Search aggregate API error:', error);
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '搜尋失敗', error),
      { status: 500 }
    );
  }
}, 'search_aggregate');

// 驗證搜尋參數
function validateSearchParams(params: any): { 
  valid: boolean; 
  params?: any; 
  error?: string; 
} {
  if (!params || typeof params !== 'object') {
    return { valid: false, error: '無效的搜尋參數' };
  }
  
  // 檢查必要參數
  if (!params.keyword && !params.room_id && !params.user_id) {
    return { valid: false, error: '至少需要提供關鍵字、房間ID或用戶ID其中一個' };
  }
  
  // 清理和驗證參數
  const cleanParams = {
    keyword: params.keyword?.toString().trim() || '',
    message_type: params.message_type || undefined,
    room_id: params.room_id || undefined,
    user_id: params.user_id || undefined,
    start_date: params.start_date || undefined,
    end_date: params.end_date || undefined,
    page: Math.max(1, parseInt(params.page) || 1),
    pageSize: Math.min(100, Math.max(10, parseInt(params.pageSize) || 20)),
  };
  
  // 驗證日期格式
  if (cleanParams.start_date && !isValidDate(cleanParams.start_date)) {
    return { valid: false, error: '無效的開始日期格式' };
  }
  
  if (cleanParams.end_date && !isValidDate(cleanParams.end_date)) {
    return { valid: false, error: '無效的結束日期格式' };
  }
  
  return { valid: true, params: cleanParams };
}

// 執行主要搜尋
async function performMainSearch(params: any): Promise<any[]> {
  // 如果指定了房間，使用房間搜尋 API
  if (params.room_id) {
    return bffBackendClient.request(`/api/messages/room/${params.room_id}/search`, {
      method: 'POST',
      data: params
    });
  }
  
  // 否則使用全域搜尋 API
  return bffBackendClient.request('/api/messages/search', {
    method: 'POST',
    data: params
  });
}

// 生成搜尋建議
async function generateSearchSuggestions(keyword?: string): Promise<string[]> {
  if (!keyword || keyword.length < 2) {
    return [];
  }
  
  try {
    const suggestions = await bffBackendClient.request<string[]>('/api/search/suggestions', {
      method: 'POST',
      data: { keyword, limit: 5 }
    });
    return suggestions || [];
  } catch (error) {
    console.warn('Failed to get search suggestions:', error);
    return [];
  }
}

// 找出相關房間
async function findRelatedRooms(params: any): Promise<Room[]> {
  if (!params.keyword) {
    return [];
  }
  
  try {
    const relatedRooms = await bffBackendClient.request<Room[]>('/api/rooms/search', {
      method: 'POST',
      data: { 
        keyword: params.keyword,
        limit: 5 
      }
    });
    return relatedRooms || [];
  } catch (error) {
    console.warn('Failed to get related rooms:', error);
    return [];
  }
}

// 轉換搜尋結果
function transformSearchResults(results: any[], rooms: Room[]): SearchResult[] {
  const roomMap = new Map(rooms.map(room => [room.id, room]));
  
  return results.map(result => ({
    message: {
      id: result.id,
      room_id: result.room_id,
      user_id: result.user_id,
      username: result.username,
      content: result.content,
      message_type: result.message_type,
      created_at: result.created_at,
    },
    room: roomMap.get(result.room_id) || {
      id: result.room_id,
      name: '未知房間',
      description: '',
      owner_id: '',
      members: [],
      is_public: false,
      created_at: '',
    },
    highlights: result.highlights || [],
    relevanceScore: result.score || 1.0,
  }));
}

// 生成搜尋面向
function generateSearchFacets(results: SearchResult[]): SearchFacets {
  // 按訊息類型統計
  const messageTypeCounts = results.reduce((acc, result) => {
    const type = result.message.message_type;
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  // 按用戶統計
  const userCounts = results.reduce((acc, result) => {
    const key = `${result.message.user_id}:${result.message.username}`;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  // 按房間統計
  const roomCounts = results.reduce((acc, result) => {
    const key = `${result.room.id}:${result.room.name}`;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  // 按時間範圍統計
  const now = new Date();
  const timeRanges = {
    '今天': results.filter(r => isToday(new Date(r.message.created_at))).length,
    '本週': results.filter(r => isThisWeek(new Date(r.message.created_at))).length,
    '本月': results.filter(r => isThisMonth(new Date(r.message.created_at))).length,
    '更早': results.filter(r => !isThisMonth(new Date(r.message.created_at))).length,
  };
  
  return {
    messageTypes: Object.entries(messageTypeCounts)
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count),
      
    users: Object.entries(userCounts)
      .map(([key, count]) => {
        const [user_id, username] = key.split(':');
        return { user_id, username, count };
      })
      .sort((a, b) => b.count - a.count)
      .slice(0, 10),
      
    rooms: Object.entries(roomCounts)
      .map(([key, count]) => {
        const [room_id, room_name] = key.split(':');
        return { room_id, room_name, count };
      })
      .sort((a, b) => b.count - a.count)
      .slice(0, 10),
      
    timeRanges: Object.entries(timeRanges)
      .map(([range, count]) => ({ range, count }))
      .filter(item => item.count > 0),
  };
}

// 工具函數
function isValidDate(dateString: string): boolean {
  const date = new Date(dateString);
  return !isNaN(date.getTime());
}

function isToday(date: Date): boolean {
  const today = new Date();
  return date.toDateString() === today.toDateString();
}

function isThisWeek(date: Date): boolean {
  const now = new Date();
  const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
  return date >= weekAgo;
}

function isThisMonth(date: Date): boolean {
  const now = new Date();
  return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear();
}

function generateSearchCacheKey(params: any): string {
  const keyData = {
    keyword: params.keyword,
    room_id: params.room_id,
    user_id: params.user_id,
    message_type: params.message_type,
    page: params.page,
    timestamp: Math.floor(Date.now() / 300000), // 5分鐘間隔
  };
  return btoa(JSON.stringify(keyData));
}