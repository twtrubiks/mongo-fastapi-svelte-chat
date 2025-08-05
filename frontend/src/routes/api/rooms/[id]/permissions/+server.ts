import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking,
  generateCacheKey
} from '$lib/bff-utils';
import type { Room, User, RoomInvitation, JoinRequest, MemberRole } from '$lib/types';

// 房間權限聚合資料
export interface RoomPermissionsData {
  room: Room;
  currentUserRole: MemberRole;
  permissions: string[];
  members: Array<{
    user: User;
    role: MemberRole;
    joined_at: string;
  }>;
  pendingInvitations?: RoomInvitation[];
  pendingRequests?: JoinRequest[];
  canManageRoom: boolean;
  canInviteMembers: boolean;
  canApproveRequests: boolean;
  canKickMembers: boolean;
}

// 獲取房間權限聚合資料
export const GET: RequestHandler = withPerformanceTracking(async ({ params, cookies, request }) => {
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
    // 獲取當前用戶資訊
    const currentUser = await bffBackendClient.request<User>('/api/auth/me');
    
    // 並行獲取房間權限相關資訊
    const [room, members] = await Promise.all([
      bffBackendClient.request<Room>(`/api/rooms/${roomId}`),
      bffBackendClient.request<User[]>(`/api/rooms/${roomId}/members`)
    ]);
    
    // 檢查房間是否存在
    if (!room) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    // 獲取當前用戶的角色
    const currentUserRole = room.member_roles?.[currentUser.id || currentUser._id || ''] || MemberRole.MEMBER;
    
    // 判斷權限
    const isOwner = currentUserRole === MemberRole.OWNER;
    const isAdmin = currentUserRole === MemberRole.ADMIN;
    const isMember = room.members.includes(currentUser.id || currentUser._id || '');
    
    // 生成權限列表
    const permissions: string[] = [];
    if (isMember) permissions.push('message', 'view_members');
    if (isOwner || isAdmin) {
      permissions.push('invite', 'kick', 'manage_room');
      if (isOwner) permissions.push('delete_room', 'transfer_ownership');
    }
    
    // 準備成員列表（包含角色資訊）
    const membersWithRoles = members.map(member => ({
      user: member,
      role: room.member_roles?.[member.id || member._id || ''] || MemberRole.MEMBER,
      joined_at: member.created_at || new Date().toISOString()
    }));
    
    // 如果是管理員，獲取待處理的邀請和申請
    let pendingInvitations: RoomInvitation[] = [];
    let pendingRequests: JoinRequest[] = [];
    
    if (isOwner || isAdmin) {
      try {
        // 並行獲取邀請和申請（如果這些 API 存在）
        const [invitations, requests] = await Promise.allSettled([
          bffBackendClient.request<RoomInvitation[]>(`/api/invitations/rooms/${roomId}/invitations?active_only=true`),
          bffBackendClient.request<JoinRequest[]>(`/api/invitations/rooms/${roomId}/join-requests?status=pending`)
        ]);
        
        if (invitations.status === 'fulfilled') {
          pendingInvitations = invitations.value;
        }
        if (requests.status === 'fulfilled') {
          pendingRequests = requests.value;
        }
      } catch (error) {
        console.warn('Failed to fetch invitations/requests:', error);
      }
    }
    
    // 組合權限資料
    const permissionsData: RoomPermissionsData = {
      room,
      currentUserRole,
      permissions,
      members: membersWithRoles,
      pendingInvitations: isOwner || isAdmin ? pendingInvitations : undefined,
      pendingRequests: isOwner || isAdmin ? pendingRequests : undefined,
      canManageRoom: isOwner || isAdmin,
      canInviteMembers: isOwner || isAdmin,
      canApproveRequests: isOwner || isAdmin,
      canKickMembers: isOwner || isAdmin
    };
    
    // 生成快取鍵
    const cacheKey = generateCacheKey('room_permissions', { 
      roomId, 
      userId: currentUser.id || currentUser._id,
      timestamp: Math.floor(Date.now() / 300000) // 5分鐘間隔
    });
    
    // 設置快取頭部（5分鐘快取）
    const response = json(createBFFResponse(permissionsData), {
      headers: {
        'Cache-Control': 'max-age=300, s-maxage=300',
        'ETag': `"${cacheKey}"`,
        'Vary': 'Authorization',
      },
    });
    
    return response;
    
  } catch (error: any) {
    console.error(`Room permissions API error for room ${roomId}:`, error);
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    if (error.code === 403) {
      return json(createBFFError('FORBIDDEN', '沒有權限訪問此聊天室'), { status: 403 });
    }
    
    if (error.code === 404) {
      return json(createBFFError('NOT_FOUND', '聊天室不存在'), { status: 404 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取房間權限失敗', error),
      { status: 500 }
    );
  }
}, 'room_permissions_aggregate');