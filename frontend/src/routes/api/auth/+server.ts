import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';
import type { 
  AuthAggregateData, 
  Activity, 
  UserSettings 
} from '$lib/bff-types';
import type { User, Room } from '$lib/types';

// 認證聚合 API - 獲取用戶完整認證資訊
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, url, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  // 設置後端客戶端認證
  bffBackendClient.setAuth(token);
  
  try {
    // 並行獲取用戶相關的所有認證資訊
    const authData = await bffBackendClient.parallel({
      user: () => bffBackendClient.request<User>('/api/auth/me'),
      permissions: () => bffBackendClient.request<string[]>('/api/auth/permissions'),
      activeRooms: () => bffBackendClient.request<Room[]>('/api/rooms/active'),
      recentActivity: () => bffBackendClient.request<any[]>('/api/users/activity/recent?limit=5'),
      settings: () => bffBackendClient.request<any>('/api/users/settings'),
    });
    
    // 轉換用戶設置
    const settings: UserSettings = transformUserSettings(authData.settings);
    
    // 轉換最近活動
    const recentActivity: Activity[] = transformRecentActivity(
      Array.isArray(authData.recentActivity) ? authData.recentActivity : []
    );
    
    // 組合認證聚合資料
    const aggregateData: AuthAggregateData = {
      user: authData.user as User,
      permissions: Array.isArray(authData.permissions) ? authData.permissions : ['user:read', 'room:join', 'message:send'],
      activeRooms: Array.isArray(authData.activeRooms) ? authData.activeRooms : [],
      recentActivity,
      settings,
    };
    
    // 設置快取頭部（10分鐘快取）
    const response = json(createBFFResponse(aggregateData), {
      headers: {
        'Cache-Control': 'max-age=600, s-maxage=900',
        'ETag': generateAuthETag(authData.user as User),
        'Vary': 'Authorization',
      },
    });
    
    return response;
    
  } catch (error: any) {
    console.error('Auth aggregate API error:', error);
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取認證資訊失敗', error),
      { status: 500 }
    );
  }
}, 'auth_aggregate');

// 處理認證相關的 POST 請求
export const POST: RequestHandler = async ({ cookies, request }) => {
  const token = getAuthToken(cookies);
  
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  bffBackendClient.setAuth(token);
  
  try {
    const { action, data } = await request.json();
    
    switch (action) {
      case 'refresh_token': {
        // 刷新 JWT token
        const refreshResult = await bffBackendClient.request('/api/auth/refresh', {
          method: 'POST'
        });
        
        return json(createBFFResponse(refreshResult));
      }
      
      case 'update_settings': {
        // 更新用戶設置
        const updatedSettings = await bffBackendClient.request('/api/users/settings', {
          method: 'PUT',
          data
        });
        
        return json(createBFFResponse(updatedSettings));
      }
      
      case 'logout': {
        // 登出（後端可能需要廢除 token）
        try {
          await bffBackendClient.request('/api/auth/logout', {
            method: 'POST'
          });
        } catch (error) {
          // 即使後端登出失敗，前端也要清除認證狀態
          console.warn('Backend logout failed:', error);
        }
        
        return json(createBFFResponse({ message: '登出成功' }));
      }
      
      case 'change_password': {
        // 更改密碼
        const result = await bffBackendClient.request('/api/auth/change-password', {
          method: 'POST',
          data
        });
        
        return json(createBFFResponse(result));
      }
      
      default:
        return json(createBFFError('VALIDATION_ERROR', '無效的操作'), { status: 400 });
    }
    
  } catch (error: any) {
    console.error('Auth POST error:', error);
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    if (error.code === 403) {
      return json(createBFFError('FORBIDDEN', '權限不足'), { status: 403 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '操作失敗', error),
      { status: 500 }
    );
  }
};

// 轉換用戶設置為標準格式
function transformUserSettings(backendSettings: any): UserSettings {
  return {
    theme: backendSettings?.theme || 'auto',
    language: backendSettings?.language || 'zh-TW',
    notifications: {
      email: backendSettings?.notifications?.email ?? true,
      push: backendSettings?.notifications?.push ?? true,
      sound: backendSettings?.notifications?.sound ?? true,
    },
    privacy: {
      showOnlineStatus: backendSettings?.privacy?.showOnlineStatus ?? true,
      allowDirectMessages: backendSettings?.privacy?.allowDirectMessages ?? true,
    },
  };
}

// 轉換最近活動
function transformRecentActivity(backendActivity: any[]): Activity[] {
  return backendActivity.map(item => ({
    id: String(item.id || `activity_${Math.random()}`),
    type: mapActivityType(item.type) as Activity['type'],
    user: {
      id: String(item.user_id || item.user?.id || ''),
      username: String(item.username || item.user?.username || ''),
      avatar: item.avatar || item.user?.avatar,
    },
    room: item.room_id ? {
      id: String(item.room_id),
      name: String(item.room_name || '未知房間'),
    } : undefined,
    content: String(item.content || generateActivityContent(item)),
    timestamp: String(item.created_at || item.timestamp || new Date().toISOString()),
  }));
}

// 映射活動類型
function mapActivityType(backendType: string): Activity['type'] {
  const typeMap: Record<string, Activity['type']> = {
    'message': 'message',
    'join_room': 'room_join',
    'create_room': 'room_create',
    'register': 'user_register',
  };
  
  return typeMap[backendType] || 'message';
}

// 生成活動內容
function generateActivityContent(item: any): string {
  switch (item.type) {
    case 'message':
      return item.content || '發送了一條訊息';
    case 'join_room':
      return `加入了房間 ${item.room_name}`;
    case 'create_room':
      return `創建了房間 ${item.room_name}`;
    case 'register':
      return '註冊了帳號';
    default:
      return '執行了某個操作';
  }
}

// 生成認證相關的 ETag
function generateAuthETag(user: User): string {
  const hash = btoa(JSON.stringify({
    userId: user.id,
    username: user.username,
    lastActivity: Math.floor(Date.now() / 600000), // 10分鐘間隔
  }));
  return `"auth_${hash}"`;
}