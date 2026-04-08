import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  toBffErrorResponse
} from '$lib/bff-utils';

// 驗證邀請碼 - 不需要認證
export const POST: RequestHandler = async ({ request }) => {
  try {
    const body = await request.json();

    const { inviteCode } = body;

    if (!inviteCode) {
      return json(createBFFError('VALIDATION_ERROR', '邀請碼不能為空'), { status: 400 });
    }

    const result = await bffBackendClient.request<{
      valid: boolean;
      room_id?: string;
      room_name?: string;
      inviter_name?: string;
    }>('/api/invitations/validate', {
      method: 'POST',
      data: { invite_code: inviteCode }
    });

    // 後端回應格式：{ valid: true, room_id: "xxx", room_name: "xxx", inviter_name: "xxx" }
    // 前端期望格式：{ valid: true, room: { id: "xxx", name: "xxx", ... } }

    if (result && result.valid) {
      return json(createBFFResponse({
        valid: true,
        room: {
          id: result.room_id,
          name: result.room_name,
          inviter_name: result.inviter_name
        }
      }));
    } else {
      return json(createBFFError('INVALID_INVITE', '邀請碼無效或已過期'), { status: 400 });
    }
    
  } catch (error: unknown) {
    return toBffErrorResponse(error, '驗證邀請碼失敗', 'INVALID_INVITE');
  }
};