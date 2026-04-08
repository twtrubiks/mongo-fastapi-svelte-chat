import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const DELETE: RequestHandler = async ({ params, cookies }) => {
  try {
    const { id } = params;
    const result = await bffAuthRequest(cookies, `/api/notifications/${id}`, { method: 'DELETE' });
    return json(createBFFResponse(result));
  } catch (error: any) {
    return toBffErrorResponse(error, '刪除通知失敗');
  }
};
