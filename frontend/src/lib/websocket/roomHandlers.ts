import type { HandlerContext } from './handlers';
import type { Message, User, WSUserStatusChangedMessage, WSRoomUsersMessage, WSRoomCreatedMessage, WSRoomDeletedMessage, WSRoomUpdatedMessage } from '$lib/types';
import { currentUser, roomStore, messageStore } from '$lib/stores';

// 追蹤最後收到 room_users 事件的時間（模組級共享狀態）
let lastRoomUsersTime = 0;

/** 重置 lastRoomUsersTime，由 manager.disconnect() 呼叫 */
export function resetLastRoomUsersTime(): void {
  lastRoomUsersTime = 0;
}

/** 建立系統訊息物件並寫入 messageStore */
function addSystemMessage(content: string, roomId: string, timestamp: string, idSuffix = ''): void {
  const systemMessage: Message = {
    id: `system_${Date.now()}${idSuffix}`,
    room_id: roomId,
    user_id: 'system',
    content,
    message_type: 'system',
    created_at: timestamp,
    updated_at: timestamp,
    user: { id: 'system', username: 'System', created_at: timestamp },
  };
  messageStore.addMessage(systemMessage);
}

// 處理用戶加入
export function handleUserJoined(user: User, eventTimestamp: string | undefined, ctx: HandlerContext) {
  const currentUserData = currentUser();
  if (currentUserData && user.id === currentUserData.id) {
    return;
  }

  // 檢查最近是否收到了 room_users 事件（3秒內）
  // 如果是，則跳過此 user_joined 事件，避免重複添加
  const timeSinceRoomUsers = Date.now() - lastRoomUsersTime;
  if (timeSinceRoomUsers < 3000) {
    if (eventTimestamp) {
      addSystemMessage(`${user.username} 加入了聊天室`, ctx.roomId!, eventTimestamp, `_${user.username}`);
    }
    return;
  }

  // 檢查用戶是否已經在列表中
  const currentRoomState = roomStore.state;
  const existingUser = currentRoomState.users.find(u => u.id === user.id);
  if (existingUser) {
    // 已在列表中但離線 → 標記為在線
    if (!existingUser.is_active) {
      roomStore.setUsers(
        currentRoomState.users.map(u =>
          u.id === user.id ? { ...u, is_active: true } : u
        )
      );
    }
    if (eventTimestamp) {
      addSystemMessage(`${user.username} 加入了聊天室`, ctx.roomId!, eventTimestamp, `_${user.username}`);
    }
    return;
  }

  roomStore.addUser(user);

  // 只有當後端提供事件時間戳時才創建系統訊息
  // 這確保時間戳來自後端的 UTC 時間
  if (eventTimestamp) {
    addSystemMessage(`${user.username} 加入了聊天室`, ctx.roomId!, eventTimestamp, `_${user.username}`);
  }
}

// 處理用戶離開
export function handleUserLeft(user: User, eventTimestamp: string | undefined, ctx: HandlerContext, removed?: boolean) {
  const userId = user.id;
  const username = user.username;

  if (userId) {
    const currentRoomState = roomStore.state;
    if (removed) {
      // 成員離開房間（membership 移除）：從陣列移除，避免 user_status_changed 再將其設回在線
      roomStore.setUsers(currentRoomState.users.filter(u => u.id !== userId));
    } else {
      const existingUser = currentRoomState.users.find(u => u.id === userId);
      if (existingUser && existingUser.is_active) {
        roomStore.setUsers(
          currentRoomState.users.map(u =>
            u.id === userId ? { ...u, is_active: false } : u
          )
        );
      }
    }
  }

  // 只有當後端提供事件時間戳時才創建系統訊息
  // 這確保時間戳來自後端的 UTC 時間
  if (eventTimestamp) {
    addSystemMessage(`${username} 離開了聊天室`, ctx.roomId!, eventTimestamp);
  }
}

// 處理全局在線狀態變更
export function handleUserStatusChanged(data: WSUserStatusChangedMessage) {
  const { user_id, is_online } = data;
  if (!user_id) return;

  // 跳過自己
  const currentUserData = currentUser();
  if (currentUserData && user_id === currentUserData.id) return;

  // 更新該使用者的在線狀態
  const currentRoomState = roomStore.state;
  const existingUser = currentRoomState.users.find(u => u.id === user_id);
  if (existingUser) {
    roomStore.setUsers(
      currentRoomState.users.map(u =>
        u.id === user_id ? { ...u, is_active: is_online } : u
      )
    );
  }
}

// 處理房間用戶列表
export function handleRoomUsers(data: WSRoomUsersMessage) {
  try {
    // 記錄收到 room_users 事件的時間
    lastRoomUsersTime = Date.now();

    // 獲取當前的用戶列表
    const currentRoomState = roomStore.state;
    const existingUsers = currentRoomState.users || [];

    // 創建一個 Map 來合併用戶列表
    const userMap = new Map<string, User>();

    // 先添加現有的用戶（保留完整資訊）
    existingUsers.forEach(user => {
      if (user.id) {
        userMap.set(user.id, user);
      }
    });

    // 使用全局在線 ID（如有）來判斷在線狀態
    const globalOnlineIds = data.global_online_user_ids
      ? new Set<string>(data.global_online_user_ids)
      : null;

    if (globalOnlineIds) {
      // 先將 data.users 中的新使用者加入 map
      data.users.forEach((user) => {
        if (user.id && !userMap.has(user.id)) {
          userMap.set(user.id, { ...user });
        }
      });

      // 統一設定所有成員的在線狀態
      userMap.forEach((user, userId) => {
        userMap.set(userId, { ...user, is_active: globalOnlineIds.has(userId) });
      });
    } else {
      // 向下相容：使用 per-room 在線邏輯
      const onlineUserIds = new Set(data.users.map((u) => u.id).filter((id): id is string => !!id));

      data.users.forEach((user) => {
        if (!user.id) return;
        const existingUser = userMap.get(user.id);
        if (existingUser) {
          userMap.set(user.id, { ...existingUser, is_active: true });
        } else {
          userMap.set(user.id, { ...user, is_active: true });
        }
      });

      userMap.forEach((user, userId) => {
        if (!onlineUserIds.has(userId)) {
          userMap.set(userId, { ...user, is_active: false });
        }
      });
    }

    // 轉換回陣列
    const mergedUsers = Array.from(userMap.values());

    roomStore.setUsers(mergedUsers);
  } catch (error) {
    console.error('[WebSocket] 處理房間用戶列表失敗:', error);
  }
}

// 處理房間創建事件
export function handleRoomCreated(data: WSRoomCreatedMessage, ctx: HandlerContext) {
  ctx.emit('room_created', data);
}

// 處理房間刪除事件（store 更新由 roomListSync 統一處理）
export function handleRoomDeleted(data: WSRoomDeletedMessage, ctx: HandlerContext) {
  ctx.emit('room_deleted', data);
}

// 處理房間更新事件（store 更新由 roomListSync 統一處理）
export function handleRoomUpdated(data: WSRoomUpdatedMessage, ctx: HandlerContext) {
  ctx.emit('room_updated', data);
}
