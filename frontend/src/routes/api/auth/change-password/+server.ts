import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const PUT: RequestHandler = async ({ cookies, request }) => {
  try {
    const data = await request.json();
    const result = await bffAuthRequest(cookies, '/api/auth/change-password', {
      method: 'PUT',
      data,
    });
    return json(createBFFResponse(result));
  } catch (error: any) {
    return toBffErrorResponse(error, '修改密碼失敗');
  }
};
