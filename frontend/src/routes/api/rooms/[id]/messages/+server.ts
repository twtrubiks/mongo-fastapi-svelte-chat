import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  createBFFError,
  toBffErrorResponse,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取房間訊息列表
export const GET: RequestHandler = async ({ cookies, params, url }) => {
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }

  try {
    const queryParams = new URLSearchParams();
    const limit = url.searchParams.get('limit') || '50';
    const offset = url.searchParams.get('offset') || '0';
    const before = url.searchParams.get('before');
    const after = url.searchParams.get('after');

    queryParams.append('limit', limit);
    queryParams.append('skip', offset);
    if (before) queryParams.append('before', before);
    if (after) queryParams.append('after', after);

    const messages = await bffAuthRequest(cookies, `/api/rooms/${roomId}/messages?${queryParams.toString()}`);
    return json(createBFFResponse(messages));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取訊息失敗', 'MESSAGES_ERROR', { roomId });
  }
};

// 發送新訊息
export const POST: RequestHandler = async ({ cookies, params, request }) => {
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }

  try {
    const messageData = await request.json();

    if (!messageData.content || messageData.content.trim().length === 0) {
      return json(createBFFError('VALIDATION_ERROR', '訊息內容不能為空'), { status: 400 });
    }

    const newMessage = await bffAuthRequest(cookies, `/api/rooms/${roomId}/messages`, {
      method: 'POST',
      data: {
        content: messageData.content.trim(),
        message_type: messageData.type || 'text',
        room_id: roomId,
        metadata: messageData.metadata || {}
      },
    });
    return json(createBFFResponse(newMessage));
  } catch (error: any) {
    return toBffErrorResponse(error, '發送訊息失敗', 'MESSAGE_SEND_ERROR', { roomId });
  }
};
