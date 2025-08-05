import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking,
  generateCacheKey
} from '$lib/bff-utils';
import type { 
  RoomSummaryData, 
  UserPermission, 
  MessageStats 
} from '$lib/bff-types';
import type { User, Room, Message } from '$lib/types';

// 聊天室摘要聚合 API
export const GET: RequestHandler = withPerformanceTracking(async ({ params, cookies, url, request }) => {
  const { id: roomId } = params;
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  // 檢查房間 ID
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '缺少房間 ID'), { status: 400 });
  }
  
  // 設置後端客戶端認證
  bffBackendClient.setAuth(token);
  
  try {
    // 並行獲取聊天室相關的所有資訊
    const roomData = await bffBackendClient.parallel({
      room: () => bffBackendClient.request<Room>(`/api/rooms/${roomId}`),
      onlineUsers: () => bffBackendClient.request<User[]>(`/api/rooms/${roomId}/online-users`),
      recentMessages: () => bffBackendClient.request<Message[]>(`/api/rooms/${roomId}/messages?limit=20`),
      members: () => bffBackendClient.request<User[]>(`/api/rooms/${roomId}/members`),
      messageStats: () => bffBackendClient.request<any>(`/api/rooms/${roomId}/stats`),
      unreadCount: () => bffBackendClient.request<{ count: number }>(`/api/rooms/${roomId}/unread`),
    });
    
    // 檢查房間是否存在
    if (!roomData.room) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    // 生成用戶權限（簡化版本）
    const userPermissions: UserPermission[] = generateUserPermissions(
      roomData.room,
      roomData.members || []
    );
    
    // 生成訊息統計
    const messageStats: MessageStats = generateMessageStats(
      roomData.recentMessages || [],
      roomData.messageStats
    );
    
    // 組合聊天室摘要資料
    const summaryData: RoomSummaryData = {
      room: roomData.room,
      onlineUsers: roomData.onlineUsers || [],
      recentMessages: roomData.recentMessages || [],
      unreadCount: roomData.unreadCount?.count || 0,
      userPermissions,
      messageStats,
    };
    
    // 生成快取鍵
    const cacheKey = generateCacheKey('room_summary', { 
      roomId, 
      timestamp: Math.floor(Date.now() / 60000) // 1分鐘間隔
    });
    
    // 設置快取頭部（2分鐘快取）
    const response = json(createBFFResponse(summaryData), {
      headers: {
        'Cache-Control': 'max-age=120, s-maxage=300',
        'ETag': `"${cacheKey}"`,
        'Vary': 'Authorization',
      },
    });
    
    return response;
    
  } catch (error: any) {
    console.error(`Room summary API error for room ${roomId}:`, error);
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    if (error.code === 403) {
      return json(createBFFError('FORBIDDEN', '沒有權限訪問此聊天室'), { status: 403 });
    }
    
    if (error.code === 404) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取聊天室摘要失敗', error),
      { status: 500 }
    );
  }
}, 'room_summary_aggregate');

// 生成用戶權限（簡化版本）
function generateUserPermissions(room: Room, members: User[]): UserPermission[] {
  return members.map(user => ({
    user_id: user.id,
    room_id: room.id,
    role: user.id === room.owner_id ? 'owner' : 'member',
    permissions: user.id === room.owner_id 
      ? ['admin', 'moderate', 'invite', 'kick', 'message']
      : ['message'],
  }));
}

// 生成訊息統計
function generateMessageStats(recentMessages: Message[], backendStats?: any): MessageStats {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const thisWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  
  const todayMessages = recentMessages.filter(msg => 
    new Date(msg.created_at) >= today
  );
  
  const thisWeekMessages = recentMessages.filter(msg =>
    new Date(msg.created_at) >= thisWeek
  );
  
  // 按訊息類型統計
  const byType = recentMessages.reduce((acc, msg) => {
    acc[msg.message_type] = (acc[msg.message_type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  // 統計用戶發言數
  const userStats = recentMessages.reduce((acc, msg) => {
    const key = `${msg.user_id}:${msg.username}`;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  const topUsers = Object.entries(userStats)
    .map(([key, count]) => {
      const [user_id, username] = key.split(':');
      return { user_id, username, count };
    })
    .sort((a, b) => b.count - a.count)
    .slice(0, 5);
  
  return {
    total: backendStats?.total || recentMessages.length,
    today: todayMessages.length,
    thisWeek: thisWeekMessages.length,
    byType: {
      text: byType.text || 0,
      image: byType.image || 0,
      system: byType.system || 0,
    },
    topUsers,
  };
}

// 處理 POST 請求 - 刷新聊天室摘要
export const POST: RequestHandler = async ({ params, cookies, request }) => {
  const { id: roomId } = params;
  const token = getAuthToken(cookies, request.headers);
  
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  try {
    const { action } = await request.json();
    
    if (action === 'refresh') {
      // 這裡可以清除特定房間的快取
      return json(createBFFResponse({ 
        message: `聊天室 ${roomId} 摘要已刷新` 
      }));
    }
    
    if (action === 'mark_read') {
      // 標記房間訊息為已讀
      bffBackendClient.setAuth(token);
      await bffBackendClient.request(`/api/rooms/${roomId}/mark-read`, {
        method: 'POST'
      });
      
      return json(createBFFResponse({ 
        message: '已標記為已讀' 
      }));
    }
    
    return json(createBFFError('VALIDATION_ERROR', '無效的操作'), { status: 400 });
    
  } catch (error: any) {
    console.error('Room summary POST error:', error);
    return json(
      createBFFError('INTERNAL_ERROR', '操作失敗', error),
      { status: 500 }
    );
  }
};