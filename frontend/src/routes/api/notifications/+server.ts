import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  toBffErrorResponse,
  transformNotificationListResponse,
  type RawNotification,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const GET: RequestHandler = async ({ url, cookies }) => {
  try {
    const offset = url.searchParams.get('offset') || '0';
    const limit = url.searchParams.get('limit') || '20';
    const status = url.searchParams.get('status');
    const type = url.searchParams.get('type');

    const params = new URLSearchParams({ skip: offset, limit });
    if (status) params.append('status', status);
    if (type) params.append('type', type);

    const response = await bffAuthRequest<{ notifications: RawNotification[] }>(cookies, `/api/notifications/?${params.toString()}`);
    const transformedResponse = transformNotificationListResponse(response);
    return json(transformedResponse);
  } catch (error: unknown) {
    return toBffErrorResponse(error, '載入通知失敗');
  }
};

export const DELETE: RequestHandler = async ({ cookies }) => {
  try {
    const result = await bffAuthRequest(cookies, '/api/notifications/', { method: 'DELETE' });
    return json(createBFFResponse(result));
  } catch (error: unknown) {
    return toBffErrorResponse(error, '清除所有通知失敗');
  }
};
