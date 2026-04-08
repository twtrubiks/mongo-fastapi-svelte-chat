import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  createBFFError,
  toBffErrorResponse,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取單個房間詳細資訊
export const GET: RequestHandler = async ({ cookies, params }) => {
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }

  try {
    const roomData = await bffAuthRequest(cookies, `/api/rooms/${roomId}`);
    return json(createBFFResponse(roomData));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取房間信息失敗', 'ROOM_ERROR', { roomId });
  }
};

// 更新房間資訊
export const PUT: RequestHandler = async ({ cookies, params, request }) => {
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }

  try {
    const updateData = await request.json();

    if (updateData.name && updateData.name.trim().length === 0) {
      return json(createBFFError('VALIDATION_ERROR', '房間名稱不能為空'), { status: 400 });
    }

    const updatedRoom = await bffAuthRequest(cookies, `/api/rooms/${roomId}`, {
      method: 'PUT',
      data: updateData,
    });
    return json(createBFFResponse(updatedRoom));
  } catch (error: any) {
    return toBffErrorResponse(error, '更新房間失敗', 'ROOM_UPDATE_ERROR', { roomId });
  }
};

// 刪除房間
export const DELETE: RequestHandler = async ({ cookies, params }) => {
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }

  try {
    await bffAuthRequest(cookies, `/api/rooms/${roomId}`, { method: 'DELETE' });
    return json(createBFFResponse({ success: true, message: '房間已刪除', roomId }));
  } catch (error: any) {
    return toBffErrorResponse(error, '刪除房間失敗', 'ROOM_DELETE_ERROR', { roomId });
  }
};
