import { apiClient } from '../api/client';
import { bffApiClient, isSuccessResponse } from '../bff-api-client';
import type { 
  RoomState, Room, User, RoomCreate, RoomJoinRequest,
  MemberRole, RoomInvitation, JoinRequest, InvitationCreate,
  JoinRequestCreate, JoinRequestReview, RoomType, JoinPolicy
} from '../types';
import { normalizeUser, normalizeUserList, addUserToList, removeUserFromList } from '../utils/userIdNormalizer';
import { withRetry, roomRetryOptions } from '../utils/retry';

// 初始狀態
const initialState: RoomState = {
  currentRoom: null,
  rooms: [],
  users: [],
  loading: false,
  currentUserRole: null,
  permissions: [],
  invitations: [],
  joinRequests: [],
  permissionsLoading: false,
  // 分頁相關狀態
  hasMoreRooms: true,
  roomsOffset: 0,
  loadingMoreRooms: false,
};

// 創建響應式狀態
let roomState = $state<RoomState>(initialState);

// 輔助函數：更新 roomState 的部分屬性
function updateRoomState(updates: Partial<RoomState>) {
  Object.assign(roomState, updates);
}

export const roomStore = {
  // 暴露狀態的 getter
  get state() {
    return roomState;
  },

  get currentRoom() {
    return roomState.currentRoom;
  },

  get rooms() {
    return roomState.rooms;
  },

  get users() {
    return roomState.users;
  },

  get loading() {
    return roomState.loading;
  },

  get currentUserRole() {
    return roomState.currentUserRole;
  },

  get permissions() {
    return roomState.permissions;
  },

  get invitations() {
    return roomState.invitations;
  },

  get joinRequests() {
    return roomState.joinRequests;
  },

  get hasMoreRooms() {
    return roomState.hasMoreRooms;
  },

  get loadingMoreRooms() {
    return roomState.loadingMoreRooms;
  },

  // 初始化 store（用於 server-side loaded rooms）
  initializeWithServerRooms: (serverRooms: Room[]) => {
    // 直接更新屬性以保持響應式
    roomState.rooms = serverRooms;
    roomState.roomsOffset = 0; // 重置 offset，因為這是初始數據
    roomState.hasMoreRooms = true; // 總是假設有更多數據，讓用戶可以手動載入更多
    roomState.loading = false;
    roomState.loadingMoreRooms = false;
  },
  
  // 載入所有聊天室（支援分頁）
  loadRooms: async (reset: boolean = false) => {
    
    // 直接更新屬性以保持響應式
    roomState.loading = reset;
    roomState.loadingMoreRooms = !reset;
    
    try {
      const offset = reset ? 0 : roomState.roomsOffset;
      const limit = 50; // 每次載入50個房間
      
      
      
      const newRooms = await withRetry(
        () => apiClient.rooms.list({ limit, offset }),
        roomRetryOptions
      );
      
      
      let updatedRooms: Room[];
      
      if (reset) {
        updatedRooms = newRooms;
      } else {
        // 合併房間列表時去重，使用 Map 來確保唯一性
        const roomMap = new Map<string, Room>();
        
        // 先添加現有的房間
        roomState.rooms.forEach(room => roomMap.set(room.id, room));
        
        // 再添加新房間（會覆蓋重複的）
        let duplicateCount = 0;
        newRooms.forEach(room => {
          if (roomMap.has(room.id)) {
            duplicateCount++;
          }
          roomMap.set(room.id, room);
        });
        
        updatedRooms = Array.from(roomMap.values());
      }
      
      // 直接更新屬性以保持響應式
      roomState.rooms = updatedRooms;
      roomState.loading = false;
      roomState.loadingMoreRooms = false;
      roomState.roomsOffset = offset + newRooms.length;
      roomState.hasMoreRooms = newRooms.length === limit; // 如果返回的數量少於limit，說明沒有更多了
      
      return newRooms;
    } catch (error) {
      // 直接更新屬性以保持響應式
      roomState.loading = false;
      roomState.loadingMoreRooms = false;
      throw error;
    }
  },

  // 載入更多聊天室
  loadMoreRooms: async () => {
    if (!roomState.hasMoreRooms || roomState.loadingMoreRooms) {
      return;
    }

    updateRoomState({ loadingMoreRooms: true });
    
    try {
      const offset = roomState.roomsOffset;
      const limit = 50;
      
      const newRooms = await withRetry(
        () => apiClient.rooms.list({ limit, offset }),
        roomRetryOptions
      );
      
      // 合併房間列表時去重，使用 Map 來確保唯一性
      const roomMap = new Map<string, Room>();
      
      // 先添加現有的房間
      roomState.rooms.forEach(room => roomMap.set(room.id, room));
      
      // 再添加新房間（會覆蓋重複的）
      let duplicateCount = 0;
      newRooms.forEach(room => {
        if (roomMap.has(room.id)) {
          duplicateCount++;
        }
        roomMap.set(room.id, room);
      });
      
      const updatedRooms = Array.from(roomMap.values());
      
      updateRoomState({
        rooms: updatedRooms,
        loadingMoreRooms: false,
        roomsOffset: offset + newRooms.length,
        hasMoreRooms: newRooms.length === limit
      });
      
      return newRooms;
    } catch (error) {
      updateRoomState({ loadingMoreRooms: false });
      throw error;
    }
  },

  // 載入用戶已加入的聊天室
  loadMyRooms: async () => {
    updateRoomState({ loading: true });
    
    try {
      const myRooms = await apiClient.rooms.myRooms();
      
      // 不要覆蓋所有房間，而是標記用戶已加入的房間
      // 或者返回用戶的房間列表，讓調用者決定如何處理
      updateRoomState({ loading: false });
      
      // 只返回用戶已加入的房間，不修改 store 中的房間列表
      return myRooms;
    } catch (error) {
      updateRoomState({ loading: false });
      throw error;
    }
  },

  // 載入特定聊天室
  loadRoom: async (roomId: string) => {
    // console.log('[RoomStore] 開始載入房間:', roomId);
    updateRoomState({ loading: true });
    // console.log('[RoomStore] 設置 loading = true');
    
    try {
      const room = await apiClient.rooms.get(roomId);
      // console.log('[RoomStore] 獲取房間資料完成:', room);
      const users = await apiClient.rooms.getMembers(roomId);
      // console.log('[RoomStore] 獲取房間成員完成，成員數量:', users.length);
      
      updateRoomState({
        currentRoom: room,
        users,
        loading: false,
      });
      // console.log('[RoomStore] 設置 loading = false，房間載入完成');
      
      return { room, users };
    } catch (error) {
      console.error('[RoomStore] 載入房間失敗:', error);
      updateRoomState({ loading: false });
      // console.log('[RoomStore] 錯誤情況下設置 loading = false');
      throw error;
    }
  },

  // 創建聊天室
  createRoom: async (roomData: RoomCreate) => {
    updateRoomState({ loading: true });
    
    try {
      const room = await apiClient.rooms.create(roomData);
      
      updateRoomState({
        rooms: [room, ...roomState.rooms], // 將新房間添加到列表開頭，保持與後端排序一致
        loading: false,
      });
      
      return room;
    } catch (error) {
      updateRoomState({ loading: false });
      throw error;
    }
  },

  // 加入聊天室（支援新的權限系統）
  joinRoom: async (roomId: string, joinRequest?: RoomJoinRequest) => {
    updateRoomState({ loading: true });
    
    try {
      if (joinRequest) {
        // 使用進階加入 API
        const response = await bffApiClient.rooms.joinAdvanced(roomId, joinRequest);
        
        if (isSuccessResponse(response)) {
          if (response.data.success) {
            // 成功加入，重新載入房間資料
            const room = await apiClient.rooms.get(roomId);
            const users = await apiClient.rooms.getMembers(roomId);
            
            updateRoomState({
              currentRoom: room,
              users,
              rooms: roomState.rooms.some(r => r.id === room.id) 
                ? roomState.rooms.map(r => r.id === room.id ? room : r)
                : [...roomState.rooms, room],
              loading: false,
            });
            
            return { success: true, room, users };
          } else {
            // 需要進一步操作
            updateRoomState({ loading: false });
            return response.data;
          }
        } else {
          throw new Error(response.error?.message || '加入房間失敗');
        }
      } else {
        // 使用原本的加入 API（帶重試機制）
        await withRetry(
          () => apiClient.rooms.join(roomId),
          roomRetryOptions
        );
        
        // 重新載入聊天室資料（帶重試機制）
        const room = await withRetry(
          () => apiClient.rooms.get(roomId),
          roomRetryOptions
        );
        const users = await withRetry(
          () => apiClient.rooms.getMembers(roomId),
          roomRetryOptions
        );
        
        updateRoomState({
          currentRoom: room,
          users,
          rooms: roomState.rooms.some(r => r.id === room.id) 
            ? roomState.rooms.map(r => r.id === room.id ? room : r)
            : [...roomState.rooms, room],
          loading: false,
        });
        
        return { success: true, room, users };
      }
    } catch (error: any) {
      // 如果房間不存在（404），自動從列表中移除
      if (error.status === 404 || error.response?.status === 404) {
        console.warn(`[Room Store] 房間 ${roomId} 不存在，從列表中移除`);
        updateRoomState({
          rooms: roomState.rooms.filter(r => r.id !== roomId),
          loading: false
        });
      } else {
        updateRoomState({ loading: false });
      }
      throw error;
    }
  },

  // 檢查加入要求
  checkJoinRequirements: async (roomId: string) => {
    try {
      const response = await bffApiClient.rooms.checkJoinRequirements(roomId);
      
      if (isSuccessResponse(response)) {
        return response.data;
      } else {
        throw new Error(response.error?.message || '檢查加入要求失敗');
      }
    } catch (error) {
      throw error;
    }
  },

  // 離開聊天室
  leaveRoom: async (roomId: string) => {
    updateRoomState({ loading: true });
    
    try {
      await apiClient.rooms.leave(roomId);
      
      updateRoomState({
        rooms: roomState.rooms.filter(room => room.id !== roomId),
        currentRoom: roomState.currentRoom?.id === roomId ? null : roomState.currentRoom,
        users: roomState.currentRoom?.id === roomId ? [] : roomState.users,
        loading: false,
      });
      
    } catch (error) {
      updateRoomState({ loading: false });
      throw error;
    }
  },

  // 設置當前聊天室
  setCurrentRoom: (room: Room | null) => {
    updateRoomState({ currentRoom: room });
  },

  // 添加用戶 (WebSocket 事件)
  addUser: (user: User) => {
    try {
      const normalizedUser = normalizeUser(user);
      
      updateRoomState({
        users: addUserToList(roomState.users, normalizedUser),
      });
    } catch (error) {
      // 靜默處理錯誤
    }
  },

  // 移除用戶 (WebSocket 事件)
  removeUser: (userId: string) => {
    updateRoomState({
      users: removeUserFromList(roomState.users, userId),
    });
  },

  // 設置用戶列表 (WebSocket 事件)
  setUsers: (users: User[]) => {
    const normalizedUsers = normalizeUserList(users);

    updateRoomState({
      users: normalizedUsers,
    });
  },

  // 更新聊天室資料
  updateRoom: (updatedRoom: Room) => {
    updateRoomState({
      rooms: roomState.rooms.map(room => 
        room.id === updatedRoom.id ? updatedRoom : room
      ),
      currentRoom: roomState.currentRoom?.id === updatedRoom.id 
        ? updatedRoom 
        : roomState.currentRoom,
    });
  },

  // 載入使用者權限
  loadPermissions: async (roomId: string) => {
    updateRoomState({ permissionsLoading: true });
    
    try {
      const permissions = await apiClient.rooms.getPermissions(roomId);
      
      updateRoomState({
        permissions: permissions.permissions || [],
        currentUserRole: permissions.role,
        permissionsLoading: false,
      });
      
      return permissions;
    } catch (error) {
      updateRoomState({ permissionsLoading: false });
      throw error;
    }
  },

  // 更新房間設定
  updateRoomSettings: async (roomId: string, settings: Partial<Room>) => {
    updateRoomState({ loading: true });
    
    try {
      const updatedRoom = await apiClient.rooms.updateSettings(roomId, settings);
      
      updateRoomState({
        rooms: roomState.rooms.map(room => 
          room.id === roomId ? updatedRoom : room
        ),
        currentRoom: roomState.currentRoom?.id === roomId 
          ? updatedRoom 
          : roomState.currentRoom,
        loading: false,
      });
      
      return updatedRoom;
    } catch (error) {
      updateRoomState({ loading: false });
      throw error;
    }
  },

  // 清除 store
  clear: () => {
    roomState = initialState;
  },

  // 驗證邀請碼
  validateInvitation: async (inviteCode: string) => {
    try {
      const response = await bffApiClient.invitations.validate(inviteCode);
      
      if (!isSuccessResponse(response)) {
        const errorMessage = typeof response.error === 'string' 
          ? response.error 
          : response.error?.message || '邀請碼驗證失敗';
        throw new Error(errorMessage);
      }
      
      return response.data;
    } catch (error) {
      console.error('[RoomStore] 驗證邀請碼失敗:', error);
      throw error;
    }
  },

  // WebSocket 房間列表同步方法
  // 添加新房間到列表（房間創建事件）
  addNewRoom: (room: Room) => {
    // 檢查是否已存在，避免重複添加
    const existingIndex = roomState.rooms.findIndex(r => r.id === room.id);
    if (existingIndex === -1) {
      updateRoomState({
        rooms: [room, ...roomState.rooms] // 添加到列表開頭
      });
      // console.log('[RoomStore] 添加新房間到列表:', room.name);
    } else {
      // console.log('[RoomStore] 房間已存在，跳過添加:', room.name);
    }
  },

  // 從列表中移除房間（房間刪除事件）
  removeRoom: (roomId: string) => {
    const originalLength = roomState.rooms.length;
    updateRoomState({
      rooms: roomState.rooms.filter(room => room.id !== roomId),
      // 如果刪除的是當前房間，清除當前房間狀態
      currentRoom: roomState.currentRoom?.id === roomId ? null : roomState.currentRoom,
      users: roomState.currentRoom?.id === roomId ? [] : roomState.users
    });
    
    if (roomState.rooms.length < originalLength) {
      // console.log('[RoomStore] 從列表中移除房間:', roomId);
    }
  },

  // 即時更新房間資訊（房間更新事件）
  updateRoomRealtime: (updatedRoom: Room) => {
    const roomIndex = roomState.rooms.findIndex(r => r.id === updatedRoom.id);
    if (roomIndex >= 0) {
      updateRoomState({
        rooms: roomState.rooms.map(room => 
          room.id === updatedRoom.id ? updatedRoom : room
        ),
        currentRoom: roomState.currentRoom?.id === updatedRoom.id 
          ? updatedRoom 
          : roomState.currentRoom
      });
      // console.log('[RoomStore] 即時更新房間資訊:', updatedRoom.name);
    } else {
      // 如果房間不在列表中，添加它（可能是新的公開房間）
      updateRoomState({
        rooms: [updatedRoom, ...roomState.rooms]
      });
      // console.log('[RoomStore] 添加新房間（通過更新事件）:', updatedRoom.name);
    }
  }
};

// 派生值 - 只讀取當前聊天室
export const currentRoom = () => roomState.currentRoom;

// 派生值 - 只讀取聊天室列表
export const roomList = () => roomState.rooms;

// 派生值 - 只讀取聊天室用戶
export const roomUsers = () => roomState.users;

// 派生值 - 只讀取載入狀態
export const roomLoading = () => roomState.loading;

// 派生值 - 當前用戶角色
export const currentUserRole = () => roomState.currentUserRole;

// 派生值 - 用戶權限
export const userPermissions = () => roomState.permissions;

// 派生值 - 邀請列表
export const roomInvitations = () => roomState.invitations;

// 派生值 - 加入申請列表
export const roomJoinRequests = () => roomState.joinRequests;

// 派生值 - 權限載入狀態
export const permissionsLoading = () => roomState.permissionsLoading;

// 派生值 - 分頁相關狀態
export const hasMoreRooms = () => roomState.hasMoreRooms;
export const loadingMoreRooms = () => roomState.loadingMoreRooms;