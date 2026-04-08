import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  toBffErrorResponse,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';
import type { DashboardData } from '$lib/bff-types';
import type { User, RoomSummary, Notification } from '$lib/types';

// 單一失敗不影響整體：失敗時回傳 null
async function safeRequest<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch (error: any) {
    // 401 需要向上拋，觸發統一的認證失敗處理
    if (error.code === 401) throw error;
    return null;
  }
}

// 儀表板聚合 API
export const GET: RequestHandler = async ({ cookies }) => {
  try {
    const [user, rooms, notifications] = await Promise.all([
      bffAuthRequest<User>(cookies, '/api/auth/me'),
      safeRequest(bffAuthRequest<RoomSummary[]>(cookies, '/api/rooms/?limit=100')),
      safeRequest(bffAuthRequest<Notification[]>(cookies, '/api/notifications/unread')),
    ]);

    const dashboardData: DashboardData = {
      user: user as User,
      rooms: Array.isArray(rooms) ? rooms : [],
      unreadCount: Array.isArray(notifications) ? notifications.length : 0,
      notifications: Array.isArray(notifications) ? notifications : [],
    };

    return json(createBFFResponse(dashboardData), {
      headers: {
        'Cache-Control': 'max-age=300, s-maxage=600',
        'ETag': generateETag(dashboardData),
      },
    });
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取儀表板資料失敗');
  }
};

// 生成 ETag 用於快取
function generateETag(data: DashboardData): string {
  const hash = btoa(JSON.stringify({
    userCount: data.rooms.length,
    unreadCount: data.unreadCount,
    timestamp: Math.floor(Date.now() / 300000),
  }));
  return `"${hash}"`;
}
