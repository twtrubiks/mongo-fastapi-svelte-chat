import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 房主解除封鎖
export const DELETE: RequestHandler = async ({ params, cookies }) => {
  try {
    const result = await bffAuthRequest(cookies, `/api/rooms/${params.id}/bans/${params.userId}`, {
      method: 'DELETE',
    });
    return json(createBFFResponse(result));
  } catch (error) {
    return toBffErrorResponse(error, '解除封鎖失敗', 'UNBAN_ERROR');
  }
};
