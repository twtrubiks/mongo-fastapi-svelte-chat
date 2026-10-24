import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 封鎖名單（僅房主）
export const GET: RequestHandler = async ({ params, cookies }) => {
  try {
    const bannedUsers = await bffAuthRequest(cookies, `/api/rooms/${params.id}/bans`);
    return json(createBFFResponse(bannedUsers));
  } catch (error) {
    return toBffErrorResponse(error, '獲取封鎖名單失敗', 'BANS_ERROR');
  }
};
