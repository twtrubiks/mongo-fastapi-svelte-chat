import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFError, createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
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

// 以使用者名稱封鎖（僅房主；可封鎖已離開或從未加入的人）
export const POST: RequestHandler = async ({ params, cookies, request }) => {
  let username: unknown;
  try {
    ({ username } = await request.json());
  } catch {
    username = undefined;
  }
  if (typeof username !== 'string' || !username.trim()) {
    return json(createBFFError('VALIDATION_ERROR', '請輸入使用者名稱'), { status: 400 });
  }

  try {
    const bannedUser = await bffAuthRequest(cookies, `/api/rooms/${params.id}/bans`, {
      method: 'POST',
      data: { username: username.trim() },
    });
    return json(createBFFResponse(bannedUser));
  } catch (error) {
    return toBffErrorResponse(error, '封鎖失敗', 'BAN_ERROR');
  }
};
