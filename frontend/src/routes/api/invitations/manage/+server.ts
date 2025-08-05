import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired
} from '$lib/bff-utils';
import type { 
  RoomInvitation, 
  InvitationCreate, 
  JoinRequest, 
  JoinRequestCreate,
  JoinRequestReview,
  JoinRequestStatus 
} from '$lib/types';

// 邀請管理聚合資料
export interface InvitationManageData {
  invitations: RoomInvitation[];
  joinRequests: JoinRequest[];
  canCreateInvitation: boolean;
  canReviewRequests: boolean;
}

// 獲取邀請管理資料
export const GET: RequestHandler = async ({ url, cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  const roomId = url.searchParams.get('room_id');
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '缺少房間 ID'), { status: 400 });
  }
  
  // 設置後端客戶端認證
  bffBackendClient.setAuth(token);
  
  try {
    // 檢查房間權限
    const room = await bffBackendClient.request<any>(`/api/rooms/${roomId}`);
    const currentUser = await bffBackendClient.request<any>('/api/auth/me');
    
    if (!room) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    // 檢查權限
    const currentUserRole = room.member_roles?.[currentUser.id || currentUser._id] || 'member';
    const canManage = currentUserRole === 'owner' || currentUserRole === 'admin';
    
    if (!canManage) {
      return json(createBFFError('FORBIDDEN', '沒有權限管理邀請'), { status: 403 });
    }
    
    // 並行獲取邀請和加入申請
    const [invitations, joinRequests] = await Promise.allSettled([
      bffBackendClient.request<RoomInvitation[]>(`/api/invitations/rooms/${roomId}/invitations`),
      bffBackendClient.request<JoinRequest[]>(`/api/invitations/rooms/${roomId}/join-requests`)
    ]);
    
    const data: InvitationManageData = {
      invitations: invitations.status === 'fulfilled' ? invitations.value : [],
      joinRequests: joinRequests.status === 'fulfilled' ? joinRequests.value : [],
      canCreateInvitation: canManage,
      canReviewRequests: canManage
    };
    
    return json(createBFFResponse(data));
    
  } catch (error: any) {
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取邀請管理資料失敗', error),
      { status: 500 }
    );
  }
};

// 處理 OPTIONS 請求 (CORS preflight)
export const OPTIONS: RequestHandler = async () => {
  return new Response(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
};

// 創建邀請或處理申請
export const POST: RequestHandler = async ({ cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  bffBackendClient.setAuth(token);
  
  try {
    const body = await request.json();
    const { action, data } = body;
    
    switch (action) {
      case 'create_invitation': {
        const invitationData = data as InvitationCreate;
        const invitation = await bffBackendClient.request<RoomInvitation>(
          `/api/invitations/rooms/${invitationData.room_id}/invitations`,
          {
            method: 'POST',
            data: invitationData
          }
        );
        
        return json(createBFFResponse({
          action: 'invitation_created',
          invitation
        }));
      }
      
      case 'create_join_request': {
        const requestData = data as JoinRequestCreate;
        const joinRequest = await bffBackendClient.request<JoinRequest>(
          `/api/invitations/rooms/${requestData.room_id}/join-requests`,
          {
            method: 'POST',
            data: requestData
          }
        );
        
        return json(createBFFResponse({
          action: 'join_request_created',
          joinRequest
        }));
      }
      
      case 'review_join_request': {
        const { requestId, review } = data as { requestId: string; review: JoinRequestReview };
        await bffBackendClient.request(
          `/api/invitations/join-requests/${requestId}/review`,
          {
            method: 'PUT',
            data: review
          }
        );
        
        return json(createBFFResponse({
          action: 'join_request_reviewed',
          status: review.status
        }));
        break;
      }
      
      case 'revoke_invitation': {
        const { inviteCode } = data as { inviteCode: string };
        await bffBackendClient.request(`/api/invitations/${inviteCode}`, {
          method: 'DELETE'
        });
        
        return json(createBFFResponse({
          action: 'invitation_revoked'
        }));
        break;
      }
      
      
      default:
        return json(createBFFError('VALIDATION_ERROR', '無效的操作'), { status: 400 });
    }
    
  } catch (error: any) {
    
    if (error.message?.includes('邀請碼無效') || error.message?.includes('已過期')) {
      return json(createBFFError('INVALID_INVITE', error.message), { status: 400 });
    }
    
    if (error.code === 403) {
      return json(createBFFError('FORBIDDEN', '沒有權限執行此操作'), { status: 403 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', error.message || '操作失敗', error),
      { status: 500 }
    );
  }
};