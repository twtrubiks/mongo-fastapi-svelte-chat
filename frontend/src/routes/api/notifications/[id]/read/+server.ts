import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const POST: RequestHandler = async ({ params, cookies }) => {
  try {
    const { id } = params;
    const result = await bffAuthRequest(cookies, `/api/notifications/${id}/read`, { method: 'POST' });
    return json(createBFFResponse(result));
  } catch (error: any) {
    return toBffErrorResponse(error, '標記通知已讀失敗');
  }
};
