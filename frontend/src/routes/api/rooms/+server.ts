import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  createBFFError,
  toBffErrorResponse,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取房間列表
export const GET: RequestHandler = async ({ cookies, url }) => {
  try {
    const queryParams = new URLSearchParams();
    const limit = url.searchParams.get('limit');
    const offset = url.searchParams.get('offset');
    const search = url.searchParams.get('search');
    const excludeJoined = url.searchParams.get('exclude_joined');

    if (limit) queryParams.append('limit', limit);
    if (offset) queryParams.append('skip', offset);
    if (search) queryParams.append('search', search);
    if (excludeJoined) queryParams.append('exclude_joined', excludeJoined);

    const queryString = queryParams.toString();
    const endpoint = queryString ? `/api/rooms?${queryString}` : '/api/rooms';

    const rooms = await bffAuthRequest(cookies, endpoint);
    return json(createBFFResponse(rooms));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取房間列表失敗');
  }
};

// 創建新房間
export const POST: RequestHandler = async ({ cookies, request }) => {
  try {
    const roomData = await request.json();

    if (!roomData.name) {
      return json(
        createBFFError('VALIDATION_ERROR', '房間名稱不能為空'),
        { status: 400 }
      );
    }

    const newRoom = await bffAuthRequest(cookies, '/api/rooms/', {
      method: 'POST',
      data: roomData,
    });
    return json(createBFFResponse(newRoom), { status: 201 });
  } catch (error: any) {
    return toBffErrorResponse(error, '創建房間失敗');
  }
};
