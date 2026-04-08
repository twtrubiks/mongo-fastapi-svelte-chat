import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  toBffErrorResponse,
  transformNotificationStats,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取通知統計
export const GET: RequestHandler = async ({ cookies }) => {
  try {
    const stats = await bffAuthRequest<{ total_count?: number; unread_count?: number; type_counts?: Record<string, number> }>(cookies, '/api/notifications/stats');
    const transformedStats = transformNotificationStats(stats);
    return json(createBFFResponse(transformedStats));
  } catch (error: unknown) {
    return toBffErrorResponse(error, '獲取通知統計失敗');
  }
};
