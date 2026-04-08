import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取用戶已加入的房間列表
export const GET: RequestHandler = async ({ cookies, url }) => {
  try {
    const queryParams = new URLSearchParams();
    const limit = url.searchParams.get('limit') || '50';
    const offset = url.searchParams.get('offset') || '0';
    queryParams.append('limit', limit);
    queryParams.append('skip', offset);

    const userRooms = await bffAuthRequest(cookies, `/api/rooms/my?${queryParams.toString()}`);
    return json(createBFFResponse(userRooms));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取用戶房間列表失敗');
  }
};
