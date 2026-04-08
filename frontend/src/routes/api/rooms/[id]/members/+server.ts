import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  createBFFError,
  toBffErrorResponse,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取房間成員列表
export const GET: RequestHandler = async ({ cookies, params, url }) => {
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }

  try {
    const queryParams = new URLSearchParams();
    const limit = url.searchParams.get('limit') || '100';
    const offset = url.searchParams.get('offset') || '0';
    const status = url.searchParams.get('status');

    queryParams.append('limit', limit);
    queryParams.append('skip', offset);
    if (status) queryParams.append('status', status);

    const members = await bffAuthRequest(cookies, `/api/rooms/${roomId}/members?${queryParams.toString()}`);
    return json(createBFFResponse(members));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取房間成員失敗', 'MEMBERS_ERROR', { roomId });
  }
};
