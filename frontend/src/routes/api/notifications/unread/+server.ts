import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  toBffErrorResponse,
  transformNotificationListResponse,
  type RawNotification,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取未讀通知（後端回 {notifications, unread_count}，與通知列表同格式）
export const GET: RequestHandler = async ({ cookies, url }) => {
  try {
    const params = new URLSearchParams({ limit: url.searchParams.get('limit') || '10' });
    const response = await bffAuthRequest<{ notifications: RawNotification[] }>(
      cookies,
      `/api/notifications/unread?${params.toString()}`
    );
    return json(createBFFResponse(transformNotificationListResponse(response)));
  } catch (error: unknown) {
    return toBffErrorResponse(error, '獲取未讀通知失敗');
  }
};
