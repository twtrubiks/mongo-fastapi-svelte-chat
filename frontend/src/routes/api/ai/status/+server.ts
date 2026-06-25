import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// AI 助理狀態：代理後端 GET /api/ai/status（供成員列表顯示上線狀態）
export const GET: RequestHandler = async ({ cookies }) => {
  try {
    const status = await bffAuthRequest(cookies, '/api/ai/status');
    return json(createBFFResponse(status));
  } catch (error) {
    return toBffErrorResponse(error, '獲取 AI 助理狀態失敗');
  }
};
