import { json, type RequestHandler } from '@sveltejs/kit';
import {
  createBFFResponse,
  createBFFError,
  toBffErrorResponse,
} from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';
import type { Room, RoomSummary, RoomJoinRequest } from '$lib/types';
import type { JoinRoomResponse } from '$lib/bff-types';

// 處理進階加入房間請求
export const POST: RequestHandler = async ({ params, cookies, request }) => {
  const { id: roomId } = params;

  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '缺少房間 ID'), { status: 400 });
  }

  try {
    const joinRequest = await request.json() as RoomJoinRequest;

    try {
      // 先嘗試加入房間（私人房間非成員無法 GET，必須先加入再取資訊）
      await bffAuthRequest(cookies, `/api/rooms/${roomId}/join`, {
        method: 'POST',
        data: joinRequest,
      });

      // 加入成功，取得房間資訊（此時已是成員，可存取私人房間）
      const room = await bffAuthRequest<Room>(cookies, `/api/rooms/${roomId}`);
      const response: JoinRoomResponse = { success: true, message: '成功加入聊天室', room };
      return json(createBFFResponse(response));
    } catch (error: any) {
      // 處理特定的錯誤情況
      if (error.message) {
        const errorMessage = error.message.toLowerCase();

        if (errorMessage.includes('需要提供密碼') || errorMessage.includes('need password')) {
          const response: JoinRoomResponse = {
            success: false,
            message: error.message,
            requiresAction: { type: 'password', message: '此聊天室需要密碼才能加入' }
          };
          return json(createBFFResponse(response));
        }

        if (errorMessage.includes('密碼錯誤') || errorMessage.includes('wrong password') || errorMessage.includes('incorrect password')) {
          const response: JoinRoomResponse = {
            success: false,
            message: error.message,
            requiresAction: { type: 'error', message: error.message }
          };
          return json(createBFFResponse(response));
        }

        if (errorMessage.includes('邀請') || errorMessage.includes('invite')) {
          const response: JoinRoomResponse = {
            success: false,
            message: error.message,
            requiresAction: { type: 'invite_code', message: '此聊天室需要邀請碼才能加入' }
          };
          return json(createBFFResponse(response));
        }

        if (errorMessage.includes('已滿') || errorMessage.includes('full')) {
          return json(createBFFError('ROOM_FULL', '聊天室已滿'), { status: 400 });
        }

        if (errorMessage.includes('已經是') || errorMessage.includes('already')) {
          // 已是成員，直接取得房間資訊
          const room = await bffAuthRequest<Room>(cookies, `/api/rooms/${roomId}`);
          const response: JoinRoomResponse = { success: true, message: '您已經是該聊天室的成員', room };
          return json(createBFFResponse(response));
        }
      }
      throw error;
    }
  } catch (error: any) {
    return toBffErrorResponse(error, '加入聊天室失敗', 'JOIN_ERROR');
  }
};

// 檢查房間加入要求
export const GET: RequestHandler = async ({ params, cookies }) => {
  const { id: roomId } = params;

  try {
    const room = await bffAuthRequest<Room | RoomSummary>(cookies, `/api/rooms/${roomId}`);

    if (!room) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }

    const isMember = room.is_member ?? false;

    if (isMember) {
      return json(createBFFResponse({ isMember: true, room, message: '您已經是該聊天室的成員' }));
    }

    const response = {
      isMember: false,
      room: {
        id: room.id,
        name: room.name,
        description: room.description,
        room_type: room.room_type,
        join_policy: room.join_policy,
        has_password: room.has_password,
        member_count: room.member_count ?? 0
      },
      requirements: {
        needsPassword: room.join_policy === 'password',
        needsInviteCode: room.join_policy === 'invite',
        canDirectJoin: room.join_policy === 'direct' && room.room_type === 'public'
      }
    };

    return json(createBFFResponse(response));
  } catch (error: any) {
    return toBffErrorResponse(error, '檢查加入要求失敗');
  }
};
