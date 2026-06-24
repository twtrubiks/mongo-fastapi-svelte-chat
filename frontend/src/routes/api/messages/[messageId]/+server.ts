import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, createBFFError, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 編輯訊息（後端僅允許作者本人；成功後由後端廣播 message_edited）
export const PUT: RequestHandler = async ({ cookies, params, request }) => {
  const messageId = params.messageId;
  if (!messageId) {
    return json(createBFFError('VALIDATION_ERROR', '訊息 ID 不能為空'), { status: 400 });
  }

  try {
    const updateData = await request.json();
    const content = typeof updateData.content === 'string' ? updateData.content.trim() : '';
    if (!content) {
      return json(createBFFError('VALIDATION_ERROR', '訊息內容不能為空'), { status: 400 });
    }

    const updated = await bffAuthRequest(cookies, `/api/messages/${messageId}`, {
      method: 'PUT',
      data: { content },
    });
    return json(createBFFResponse(updated));
  } catch (error: any) {
    return toBffErrorResponse(error, '編輯訊息失敗', 'MESSAGE_UPDATE_ERROR', { messageId });
  }
};

// 刪除訊息（後端軟刪除，僅允許作者本人；成功後由後端廣播 message_deleted）
export const DELETE: RequestHandler = async ({ cookies, params }) => {
  const messageId = params.messageId;
  if (!messageId) {
    return json(createBFFError('VALIDATION_ERROR', '訊息 ID 不能為空'), { status: 400 });
  }

  try {
    await bffAuthRequest(cookies, `/api/messages/${messageId}`, { method: 'DELETE' });
    return json(createBFFResponse({ success: true, message: '訊息已刪除', messageId }));
  } catch (error: any) {
    return toBffErrorResponse(error, '刪除訊息失敗', 'MESSAGE_DELETE_ERROR', { messageId });
  }
};
