import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired
} from '$lib/bff-utils';
import type { Room, RoomJoinRequest } from '$lib/types';

// 加入房間響應
export interface JoinRoomResponse {
  success: boolean;
  message: string;
  room?: Room;
  requiresAction?: {
    type: 'password' | 'invite_code' | 'approval' | 'error';
    message: string;
  };
}

// 處理進階加入房間請求
export const POST: RequestHandler = async ({ params, cookies, request }) => {
  const { id: roomId } = params;
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  // 檢查房間 ID
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '缺少房間 ID'), { status: 400 });
  }
  
  // 設置後端客戶端認證
  bffBackendClient.setAuth(token);
  
  try {
    // 解析請求資料
    const joinRequest = await request.json() as RoomJoinRequest;
    
    // 先獲取房間資訊以確定加入策略
    const room = await bffBackendClient.request<Room>(`/api/rooms/${roomId}`);
    
    if (!room) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    try {
      // 嘗試加入房間
      
      await bffBackendClient.request(`/api/rooms/${roomId}/join`, {
        method: 'POST',
        data: joinRequest
      });
      
      // 成功加入
      const response: JoinRoomResponse = {
        success: true,
        message: '成功加入聊天室',
        room
      };
      
      return json(createBFFResponse(response));
      
    } catch (error: any) {
      // 處理特定的錯誤情況
      if (error.message) {
        const errorMessage = error.message.toLowerCase();
        
        // 需要密碼
        if (errorMessage.includes('需要提供密碼') || errorMessage.includes('need password')) {
          const response: JoinRoomResponse = {
            success: false,
            message: error.message,
            requiresAction: {
              type: 'password',
              message: '此聊天室需要密碼才能加入'
            }
          };
          return json(createBFFResponse(response));
        }
        
        // 密碼錯誤
        if (errorMessage.includes('密碼錯誤') || errorMessage.includes('wrong password') || errorMessage.includes('incorrect password')) {
          const response: JoinRoomResponse = {
            success: false,
            message: error.message,
            requiresAction: {
              type: 'error',
              message: error.message
            }
          };
          return json(createBFFResponse(response));
        }
        
        // 需要邀請碼
        if (errorMessage.includes('邀請') || errorMessage.includes('invite')) {
          const response: JoinRoomResponse = {
            success: false,
            message: error.message,
            requiresAction: {
              type: 'invite_code',
              message: '此聊天室需要邀請碼才能加入'
            }
          };
          return json(createBFFResponse(response));
        }
        
        // 需要申請
        if (errorMessage.includes('申請') || errorMessage.includes('approval')) {
          const response: JoinRoomResponse = {
            success: false,
            message: error.message,
            requiresAction: {
              type: 'approval',
              message: '此聊天室需要提交加入申請'
            }
          };
          return json(createBFFResponse(response));
        }
        
        // 房間已滿
        if (errorMessage.includes('已滿') || errorMessage.includes('full')) {
          return json(createBFFError('ROOM_FULL', '聊天室已滿'), { status: 400 });
        }
        
        // 已是成員
        if (errorMessage.includes('已經是') || errorMessage.includes('already')) {
          const response: JoinRoomResponse = {
            success: true,
            message: '您已經是該聊天室的成員',
            room
          };
          return json(createBFFResponse(response));
        }
      }
      
      // 其他錯誤
      throw error;
    }
    
  } catch (error: any) {
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    if (error.code === 403) {
      return json(createBFFError('FORBIDDEN', '無權加入此聊天室'), { status: 403 });
    }
    
    if (error.code === 404) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', error.message || '加入聊天室失敗', error),
      { status: 500 }
    );
  }
};

// 檢查房間加入要求
export const GET: RequestHandler = async ({ params, cookies, request }) => {
  const { id: roomId } = params;
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  // 設置後端客戶端認證
  bffBackendClient.setAuth(token);
  
  try {
    // 獲取房間資訊
    const room = await bffBackendClient.request<Room>(`/api/rooms/${roomId}`);
    
    if (!room) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    // 獲取當前用戶資訊
    const currentUser = await bffBackendClient.request<any>('/api/auth/me');
    
    // 檢查是否已是成員
    const isMember = room.members.includes(currentUser.id || currentUser._id || '');
    
    if (isMember) {
      return json(createBFFResponse({
        isMember: true,
        room,
        message: '您已經是該聊天室的成員'
      }));
    }
    
    // 根據房間類型和加入策略返回要求
    const response = {
      isMember: false,
      room: {
        id: room.id,
        name: room.name,
        description: room.description,
        room_type: room.room_type,
        join_policy: room.join_policy,
        has_password: room.has_password,
        member_count: room.members.length
      },
      requirements: {
        needsPassword: room.join_policy === 'password',
        needsInviteCode: room.join_policy === 'invite',
        needsApproval: room.join_policy === 'approval',
        canDirectJoin: room.join_policy === 'direct' && room.room_type === 'public'
      }
    };
    
    return json(createBFFResponse(response));
    
  } catch (error: any) {
    
    return json(
      createBFFError('INTERNAL_ERROR', '檢查加入要求失敗', error),
      { status: 500 }
    );
  }
};