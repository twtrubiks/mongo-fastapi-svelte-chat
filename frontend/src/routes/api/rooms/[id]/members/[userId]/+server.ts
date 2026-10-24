import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 房主將成員移出房間
export const DELETE: RequestHandler = async ({ params, cookies }) => {
  try {
    const result = await bffAuthRequest(cookies, `/api/rooms/${params.id}/members/${params.userId}`, {
      method: 'DELETE',
    });
    return json(createBFFResponse(result));
  } catch (error) {
    return toBffErrorResponse(error, '移除成員失敗', 'REMOVE_MEMBER_ERROR');
  }
};
