import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const POST: RequestHandler = async ({ cookies }) => {
  try {
    const result = await bffAuthRequest(cookies, '/api/notifications/read-all', { method: 'POST' });
    return json(createBFFResponse(result));
  } catch (error: any) {
    return toBffErrorResponse(error, '標記全部已讀失敗');
  }
};
