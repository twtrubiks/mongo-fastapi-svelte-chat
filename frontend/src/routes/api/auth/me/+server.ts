import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取當前用戶資訊
export const GET: RequestHandler = async ({ cookies }) => {
  try {
    const user = await bffAuthRequest(cookies, '/api/auth/me');
    return json(createBFFResponse(user));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取用戶資訊失敗');
  }
};
