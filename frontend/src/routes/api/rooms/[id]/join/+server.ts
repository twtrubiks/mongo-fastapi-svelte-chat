import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const POST: RequestHandler = async ({ params, request, cookies }) => {
  try {
    const roomId = params.id;

    let joinRequest = {};
    try {
      const body = await request.text();
      if (body) {
        joinRequest = JSON.parse(body);
      }
    } catch {
      // 忽略 JSON 解析錯誤，使用空對象
    }

    const result = await bffAuthRequest(cookies, `/api/rooms/${roomId}/join`, {
      method: 'POST',
      data: joinRequest,
    });

    return json(createBFFResponse(result));
  } catch (error: any) {
    return toBffErrorResponse(error, '加入房間失敗', 'JOIN_ERROR');
  }
};
