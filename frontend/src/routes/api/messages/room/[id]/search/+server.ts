import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, createBFFError, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const POST: RequestHandler = async ({ cookies, params, request }) => {
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }

  try {
    const searchParams = await request.json();
    const results = await bffAuthRequest(cookies, `/api/messages/room/${roomId}/search`, {
      method: 'POST',
      data: searchParams,
    });
    return json(createBFFResponse(results));
  } catch (error: any) {
    return toBffErrorResponse(error, '搜尋失敗', 'SEARCH_ERROR', { roomId });
  }
};
