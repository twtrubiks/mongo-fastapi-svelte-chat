import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  toBffErrorResponse,
  transformNotifications,
  type RawNotification,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';
import type { DashboardData } from '$lib/bff-types';
import type { User, RoomSummary } from '$lib/types';

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
    // /api/rooms 會含未加入的公開房間，儀表板只顯示已加入的；
    // /unread 回 {notifications, unread_count}，notifications 只到 limit 筆，總數以 unread_count 為準
    const [user, rooms, unread] = await Promise.all([
      bffAuthRequest<User>(cookies, '/api/auth/me'),
      safeRequest(bffAuthRequest<RoomSummary[]>(cookies, '/api/rooms/my?limit=100')),
      safeRequest(
        bffAuthRequest<{ notifications: RawNotification[]; unread_count: number }>(
          cookies,
          '/api/notifications/unread'
        )
      ),
    ]);

    const dashboardData: DashboardData = {
      user: user as User,
      rooms: Array.isArray(rooms) ? rooms : [],
      unreadCount: unread?.unread_count ?? 0,
      notifications: transformNotifications(unread?.notifications ?? []),
    };

    // 每位使用者的資料不同，且「刷新」須取得最新資料：不讓瀏覽器或共用快取存下
    return json(createBFFResponse(dashboardData), {
      headers: { 'Cache-Control': 'private, no-store' },
    });
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取儀表板資料失敗');
  }
};

