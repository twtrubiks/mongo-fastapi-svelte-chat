import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import { 
  createBFFResponse, 
  createBFFError, 
  getAuthToken, 
  isTokenExpired,
  withPerformanceTracking,
  aggregateData,
  deduplicateBy
} from '$lib/bff-utils';
import type { 
  DashboardData, 
  Activity, 
  BFFErrorCode 
} from '$lib/bff-types';
import type { User, Room, Message, Notification } from '$lib/types';

// 儀表板聚合 API
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, fetch, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  // 設置後端客戶端認證
  bffBackendClient.setAuth(token);
  
  try {
    // 並行獲取多個資料源
    const aggregatedData = await bffBackendClient.parallel({
      user: () => bffBackendClient.request<User>('/api/auth/me'),
      rooms: () => bffBackendClient.request<Room[]>('/api/rooms/'),
      notifications: () => bffBackendClient.request<Notification[]>('/api/notifications/unread'),
      recentMessages: () => bffBackendClient.request<Message[]>('/api/messages/recent?limit=10'),
      onlineUsersCount: () => bffBackendClient.request<{ count: number }>('/api/users/online/count'),
      messageStats: () => bffBackendClient.request<{ total: number }>('/api/messages/stats'),
    });
    
    // 資料轉換和聚合
    const dashboardData: DashboardData = {
      user: aggregatedData.user as User,
      rooms: Array.isArray(aggregatedData.rooms) ? aggregatedData.rooms : [],
      unreadCount: Array.isArray(aggregatedData.notifications) ? aggregatedData.notifications.length : 0,
      recentActivity: generateRecentActivity(
        Array.isArray(aggregatedData.recentMessages) ? aggregatedData.recentMessages : [], 
        Array.isArray(aggregatedData.rooms) ? aggregatedData.rooms : []
      ),
      notifications: Array.isArray(aggregatedData.notifications) ? aggregatedData.notifications : [],
      onlineUsers: (aggregatedData.onlineUsersCount as any)?.count || 0,
      totalMessages: (aggregatedData.messageStats as any)?.total || 0,
    };
    
    // 設置快取頭部（5分鐘快取）
    const response = json(createBFFResponse(dashboardData), {
      headers: {
        'Cache-Control': 'max-age=300, s-maxage=600',
        'ETag': generateETag(dashboardData),
      },
    });
    
    return response;
    
  } catch (error: any) {
    console.error('Dashboard API error:', error);
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取儀表板資料失敗', error), 
      { status: 500 }
    );
  }
}, 'dashboard_aggregate');

// 生成最近活動
function generateRecentActivity(messages: Message[], rooms: Room[]): Activity[] {
  const roomMap = new Map(rooms.map(room => [room.id, room]));
  
  const activities: Activity[] = messages
    .filter(msg => msg.message_type !== 'system')
    .map(msg => ({
      id: String(`msg_${msg.id}`),
      type: 'message' as Activity['type'],
      user: {
        id: String(msg.user_id),
        username: String(msg.username),
      },
      room: roomMap.get(msg.room_id) ? {
        id: String(msg.room_id),
        name: String(roomMap.get(msg.room_id)!.name),
      } : undefined,
      content: String(msg.message_type === 'image' ? '發送了一張圖片' : 
              msg.content.length > 50 ? msg.content.substring(0, 50) + '...' : msg.content),
      timestamp: String(msg.created_at),
    }));
  
  // 按時間排序，最新的在前
  return activities
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    .slice(0, 10); // 只保留最近 10 條
}

// 生成 ETag 用於快取
function generateETag(data: DashboardData): string {
  const hash = btoa(JSON.stringify({
    userCount: data.rooms.length,
    messageCount: data.totalMessages,
    unreadCount: data.unreadCount,
    timestamp: Math.floor(Date.now() / 300000), // 5分鐘間隔
  }));
  return `"${hash}"`;
}

// 處理 POST 請求 - 刷新儀表板快取
export const POST: RequestHandler = async ({ cookies, request }) => {
  const token = getAuthToken(cookies);
  
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  try {
    const { action } = await request.json();
    
    if (action === 'refresh') {
      // 這裡可以清除快取或觸發資料重新載入
      return json(createBFFResponse({ message: '儀表板已刷新' }));
    }
    
    return json(createBFFError('VALIDATION_ERROR', '無效的操作'), { status: 400 });
    
  } catch (error) {
    return json(
      createBFFError('INTERNAL_ERROR', '操作失敗'),
      { status: 500 }
    );
  }
};