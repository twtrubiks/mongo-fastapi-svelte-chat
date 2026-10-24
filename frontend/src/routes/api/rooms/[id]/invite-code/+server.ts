import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 重新產生邀請碼（僅房主，舊邀請碼立即失效）
export const POST: RequestHandler = async ({ params, cookies }) => {
  try {
    const result = await bffAuthRequest(cookies, `/api/rooms/${params.id}/invite-code`, { method: 'POST' });
    return json(createBFFResponse(result));
  } catch (error) {
    return toBffErrorResponse(error, '重新產生邀請碼失敗', 'INVITE_CODE_ERROR');
  }
};
