import { apiClient } from '../api/client';
import { bffApiClient, isSuccessResponse } from '../bff-api-client';
import type {
  RoomState, Room, RoomSummary, User, RoomCreate, RoomJoinRequest
} from '../types';
import { normalizeUser, normalizeUserList, addUserToList, extractUserId } from '../utils/userIdNormalizer';
import { withRetry, roomRetryOptions } from '../utils/retry';

const MEMBERS_PAGE_LIMIT = 50;
const ROOMS_PAGE_LIMIT = 25;

// 初始狀態
const initialState: RoomState = {
  currentRoom: null,
  rooms: [],
  myRooms: [],
  activeTab: 'joined',
  searchQuery: '',
  users: [],
  loading: false,
  // 探索聊天室分頁狀態
  hasMoreRooms: true,
  roomsOffset: 0,
  loadingMoreRooms: false,
  // 已加入聊天室分頁狀態
  hasMoreMyRooms: true,
  myRoomsOffset: 0,
  loadingMoreMyRooms: false,
  // 成員分頁狀態
  hasMoreMembers: true,
  membersOffset: 0,
  loadingMoreMembers: false,
};

// 創建響應式狀態
let roomState = $state<RoomState>(initialState);

// 輔助函數：更新 roomState 的部分屬性
function updateRoomState(updates: Partial<RoomState>) {
  Object.assign(roomState, updates);
}

// 輔助函數：構建房間列表 API 請求參數
function buildListOptions(limit: number, offset: number, excludeJoined = false): { limit: number; offset: number; search?: string; exclude_joined?: boolean } {
  const opts: { limit: number; offset: number; search?: string; exclude_joined?: boolean } = { limit, offset };
  const trimmed = roomState.searchQuery.trim();
  if (trimmed) opts.search = trimmed;
  if (excludeJoined) opts.exclude_joined = true;
  return opts;
}

// 輔助函數：upsert 房間到列表（存在則更新，不存在則插入）
function upsertIntoList(list: RoomSummary[], room: RoomSummary, prepend = false): RoomSummary[] {
  if (list.some(r => r.id === room.id)) {
    return list.map(r => r.id === room.id ? room : r);
  }
  return prepend ? [room, ...list] : [...list, room];
}

// 輔助函數：合併房間列表並去重（新房間覆蓋舊房間）
function mergeRoomLists(existing: RoomSummary[], incoming: RoomSummary[]): RoomSummary[] {
  const roomMap = new Map<string, RoomSummary>();
  existing.forEach(room => roomMap.set(room.id, room));
  incoming.forEach(room => roomMap.set(room.id, room));
  return Array.from(roomMap.values());
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

  get hasMoreRooms() {
    return roomState.hasMoreRooms;
  },

  get loadingMoreRooms() {
    return roomState.loadingMoreRooms;
  },

  get hasMoreMyRooms() {
    return roomState.hasMoreMyRooms;
  },

  get loadingMoreMyRooms() {
    return roomState.loadingMoreMyRooms;
  },

  get hasMoreMembers() {
    return roomState.hasMoreMembers;
  },

  get loadingMoreMembers() {
    return roomState.loadingMoreMembers;
  },

  get activeTab() {
    return roomState.activeTab;
  },

  get searchQuery() {
    return roomState.searchQuery;
  },

  get myRooms() {
    return roomState.myRooms;
  },

  // 初始化 store（用於 server-side loaded rooms）
  initializeWithServerRooms: (serverRooms: RoomSummary[]) => {
    // 直接更新屬性以保持響應式
    roomState.rooms = serverRooms;
    roomState.roomsOffset = serverRooms.length;
    roomState.hasMoreRooms = serverRooms.length >= ROOMS_PAGE_LIMIT;
    roomState.loading = false;
    roomState.loadingMoreRooms = false;
  },
  
  // 載入探索聊天室（排除已加入，支援分頁）
  loadRooms: async (reset: boolean = false) => {

    // 直接更新屬性以保持響應式
    roomState.loading = reset;
    roomState.loadingMoreRooms = !reset;

    try {
      const offset = reset ? 0 : roomState.roomsOffset;
      const limit = ROOMS_PAGE_LIMIT;

      const newRooms = await withRetry(
        () => apiClient.rooms.list(buildListOptions(limit, offset, true)),
        roomRetryOptions
      );


      let updatedRooms: RoomSummary[];

      if (reset) {
        updatedRooms = newRooms;
      } else {
        updatedRooms = mergeRoomLists(roomState.rooms, newRooms);
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
      const limit = ROOMS_PAGE_LIMIT;

      const newRooms = await withRetry(
        () => apiClient.rooms.list(buildListOptions(limit, offset, true)),
        roomRetryOptions
      );

      updateRoomState({
        rooms: mergeRoomLists(roomState.rooms, newRooms),
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

  // 載入用戶已加入的聊天室（支援分頁）
  loadMyRooms: async (reset: boolean = false) => {
    roomState.loading = reset;
    roomState.loadingMoreMyRooms = !reset;

    try {
      const offset = reset ? 0 : roomState.myRoomsOffset;
      const limit = ROOMS_PAGE_LIMIT;

      const newRooms = await apiClient.rooms.myRooms({ limit, offset });

      let updatedMyRooms: RoomSummary[];
      if (reset) {
        updatedMyRooms = newRooms;
      } else {
        updatedMyRooms = mergeRoomLists(roomState.myRooms, newRooms);
      }

      roomState.myRooms = updatedMyRooms;
      roomState.loading = false;
      roomState.loadingMoreMyRooms = false;
      roomState.myRoomsOffset = offset + newRooms.length;
      roomState.hasMoreMyRooms = newRooms.length === limit;

      return newRooms;
    } catch (error) {
      roomState.loading = false;
      roomState.loadingMoreMyRooms = false;
      throw error;
    }
  },

  // 載入更多已加入的聊天室
  loadMoreMyRooms: async () => {
    if (!roomState.hasMoreMyRooms || roomState.loadingMoreMyRooms) {
      return;
    }
    await roomStore.loadMyRooms(false);
  },

  searchRooms: async (query: string) => {
    roomState.searchQuery = query;
    await roomStore.loadRooms(true);
  },

  // 切換 tab（含資料載入，已載入則跳過）
  switchTab: async (tab: 'joined' | 'explore') => {
    if (roomState.activeTab === tab) return;
    // 清除搜尋狀態；若 explore tab 有搜尋結果則一併清除，避免返回時顯示過期資料
    if (roomState.searchQuery) {
      const wasExploreSearch = roomState.activeTab === 'explore';
      roomState.searchQuery = '';
      if (wasExploreSearch) {
        roomState.rooms = [];
      }
    }
    updateRoomState({ activeTab: tab });
    if (tab === 'joined') {
      if (roomState.myRooms.length === 0) {
        await roomStore.loadMyRooms(true);
      }
    } else {
      if (roomState.rooms.length === 0) {
        await roomStore.loadRooms(true);
      }
    }
  },

  // 載入特定聊天室
  loadRoom: async (roomId: string) => {
    updateRoomState({ loading: true });

    try {
      const [room, rawUsers] = await Promise.all([
        apiClient.rooms.get(roomId),
        apiClient.rooms.getMembers(roomId, { limit: MEMBERS_PAGE_LIMIT, offset: 0 }),
      ]);

      // API 的 is_active 代表帳號啟用，非在線狀態；預設離線，等 WebSocket room_users 修正
      const users = rawUsers.map(u => ({ ...u, is_active: false }));

      updateRoomState({
        currentRoom: room,
        users,
        loading: false,
        membersOffset: users.length,
        hasMoreMembers: users.length === MEMBERS_PAGE_LIMIT,
        loadingMoreMembers: false,
      });

      return { room, users };
    } catch (error) {
      console.error('[RoomStore] 載入房間失敗:', error);
      updateRoomState({ loading: false });
      throw error;
    }
  },

  // 載入更多成員（分頁）
  loadMoreMembers: async (roomId: string) => {
    if (!roomState.hasMoreMembers || roomState.loadingMoreMembers) {
      return;
    }

    updateRoomState({ loadingMoreMembers: true });

    try {
      const offset = roomState.membersOffset;

      const newUsers = await apiClient.rooms.getMembers(roomId, { limit: MEMBERS_PAGE_LIMIT, offset });

      // 已知在線的使用者 ID（來自 WebSocket 事件）
      const onlineIds = new Set(
        roomState.users.filter(u => u.is_active).map(u => extractUserId(u))
      );

      // 去重合併，並修正在線狀態（API 的 is_active 代表帳號啟用，非在線）
      const existingIds = new Set(roomState.users.map(u => extractUserId(u)));
      const deduped = newUsers
        .filter(u => !existingIds.has(extractUserId(u)))
        .map(u => ({ ...u, is_active: onlineIds.has(extractUserId(u)) }));

      updateRoomState({
        users: [...roomState.users, ...deduped],
        loadingMoreMembers: false,
        membersOffset: offset + newUsers.length,
        hasMoreMembers: newUsers.length === MEMBERS_PAGE_LIMIT,
      });

      return newUsers;
    } catch (error) {
      updateRoomState({ loadingMoreMembers: false });
      throw error;
    }
  },

  // 創建聊天室
  createRoom: async (roomData: RoomCreate) => {
    updateRoomState({ loading: true });
    
    try {
      const room = await apiClient.rooms.create(roomData);

      // 創建者是成員，只加進 myRooms；探索列表（rooms）由後端 exclude_joined 管理
      updateRoomState({
        myRooms: [room, ...roomState.myRooms],
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
            const [room, users] = await Promise.all([
              apiClient.rooms.get(roomId),
              apiClient.rooms.getMembers(roomId, { limit: MEMBERS_PAGE_LIMIT, offset: 0 }),
            ]);

            updateRoomState({
              currentRoom: room,
              users,
              rooms: roomState.rooms.filter(r => r.id !== roomId),
              myRooms: upsertIntoList(roomState.myRooms, room, true),
              loading: false,
              membersOffset: users.length,
              hasMoreMembers: users.length === MEMBERS_PAGE_LIMIT,
              loadingMoreMembers: false,
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
        
        // 重新載入聊天室資料（帶重試機制，平行請求）
        const [room, users] = await Promise.all([
          withRetry(() => apiClient.rooms.get(roomId), roomRetryOptions),
          withRetry(() => apiClient.rooms.getMembers(roomId, { limit: MEMBERS_PAGE_LIMIT, offset: 0 }), roomRetryOptions),
        ]);

        updateRoomState({
          currentRoom: room,
          users,
          rooms: roomState.rooms.filter(r => r.id !== roomId),
          myRooms: upsertIntoList(roomState.myRooms, room, true),
          loading: false,
          membersOffset: users.length,
          hasMoreMembers: users.length === MEMBERS_PAGE_LIMIT,
          loadingMoreMembers: false,
        });

        return { success: true, room, users };
      }
    } catch (error: unknown) {
      // 如果房間不存在（404），自動從列表中移除
      const err = error as { status?: number; response?: { status?: number } };
      if (err.status === 404 || err.response?.status === 404) {
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
        myRooms: roomState.myRooms.filter(room => room.id !== roomId),
        currentRoom: roomState.currentRoom?.id === roomId ? null : roomState.currentRoom,
        users: roomState.currentRoom?.id === roomId ? [] : roomState.users,
        loading: false,
      });

      // 背景刷新探索列表（離開的房間應出現在探索中）
      roomStore.loadRooms(true).catch(() => {});
      
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
    } catch {
      // 靜默處理錯誤
    }
  },

  // 設置用戶列表 (WebSocket 事件)
  setUsers: (users: User[]) => {
    const normalizedUsers = normalizeUserList(users);

    updateRoomState({
      users: normalizedUsers,
    });
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
  addNewRoom: (room: RoomSummary) => {
    // 檢查是否已存在，避免重複添加
    const existingIndex = roomState.rooms.findIndex(r => r.id === room.id);
    if (existingIndex === -1) {
      updateRoomState({
        rooms: [room, ...roomState.rooms] // 添加到列表開頭
      });
    }
  },

  // 從列表中移除房間（房間刪除事件）
  removeRoom: (roomId: string) => {
    updateRoomState({
      rooms: roomState.rooms.filter(room => room.id !== roomId),
      myRooms: roomState.myRooms.filter(room => room.id !== roomId),
      currentRoom: roomState.currentRoom?.id === roomId ? null : roomState.currentRoom,
      users: roomState.currentRoom?.id === roomId ? [] : roomState.users
    });
    
  },

  // 即時更新房間資訊（房間更新事件）
  updateRoomRealtime: (updatedRoom: RoomSummary) => {
    const inMyRooms = roomState.myRooms.some(r => r.id === updatedRoom.id);
    const inRooms = roomState.rooms.some(r => r.id === updatedRoom.id);

    updateRoomState({
      // 探索列表：僅更新已存在的項目，不新增（避免已加入的房間被 WS 事件塞回探索）
      rooms: inRooms
        ? roomState.rooms.map(room => room.id === updatedRoom.id ? updatedRoom : room)
        : roomState.rooms,
      myRooms: inMyRooms
        ? roomState.myRooms.map(room => room.id === updatedRoom.id ? updatedRoom : room)
        : roomState.myRooms,
      // 同步更新當前房間（保留 Room-only 欄位如 members、invite_code）
      currentRoom: roomState.currentRoom?.id === updatedRoom.id
        ? { ...roomState.currentRoom, ...updatedRoom }
        : roomState.currentRoom,
    });
  }
};

// 派生值 - 只讀取聊天室列表
export const roomList = () => roomState.rooms;

// 派生值 - 只讀取聊天室用戶
export const roomUsers = () => roomState.users;

// 派生值 - 只讀取載入狀態
export const roomLoading = () => roomState.loading;

// 派生值 - 分頁相關狀態
export const hasMoreRooms = () => roomState.hasMoreRooms;
export const loadingMoreRooms = () => roomState.loadingMoreRooms;
export const hasMoreMyRooms = () => roomState.hasMoreMyRooms;
export const loadingMoreMyRooms = () => roomState.loadingMoreMyRooms;

// 派生值 - tab 相關
export const activeTab = () => roomState.activeTab;
export const searchQuery = () => roomState.searchQuery;
export const myRoomIds = () => new Set(roomState.myRooms.map(r => r.id));