import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  toBffErrorResponse,
  transformNotifications,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取未讀通知
export const GET: RequestHandler = async ({ cookies, url }) => {
  try {
    const limit = url.searchParams.get('limit') || '10';
    const notifications = await bffAuthRequest<any[]>(cookies, `/api/notifications/unread?limit=${limit}`);
    const transformedNotifications = transformNotifications(notifications as any[]);
    return json(createBFFResponse(transformedNotifications));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取未讀通知失敗');
  }
};
