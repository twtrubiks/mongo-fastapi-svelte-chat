/**
 * 房間列表 WebSocket 同步
 * 處理房間創建等需要在全局范圍內監聽的事件
 */

import { wsManager } from './manager';
import { roomStore } from '$lib/stores/room.svelte';

let isInitialized = false;
let eventHandlers: { [key: string]: Function } = {};

/**
 * 設置房間列表 WebSocket 同步
 */
export function setupRoomListSync() {
  if (isInitialized) {
    return;
  }


  try {
    const manager = wsManager.getInstance();

    // 監聽房間創建事件
    const handleRoomCreated = (data: any) => {
      try {
        if (data && data.room) {
          // 將新房間添加到房間列表
          roomStore.addNewRoom(data.room);
        } else {
          console.warn('[RoomListSync] 房間創建事件數據無效:', data);
        }
      } catch (error) {
        console.error('[RoomListSync] 處理房間創建事件失敗:', error);
      }
    };

    // 監聽房間刪除事件
    const handleRoomDeleted = (data: any) => {
      try {
        if (data && data.room_id) {
          // 從房間列表中移除被刪除的房間
          roomStore.removeRoom(data.room_id);
        } else {
          console.warn('[RoomListSync] 房間刪除事件數據無效:', data);
        }
      } catch (error) {
        console.error('[RoomListSync] 處理房間刪除事件失敗:', error);
      }
    };

    // 監聽房間更新事件
    const handleRoomUpdated = (data: any) => {
      try {
        if (data && data.room) {
          // 即時更新房間資訊
          roomStore.updateRoomRealtime(data.room);
        } else {
          console.warn('[RoomListSync] 房間更新事件數據無效:', data);
        }
      } catch (error) {
        console.error('[RoomListSync] 處理房間更新事件失敗:', error);
      }
    };

    // 監聽連接狀態變化，確保重連後重新設置監聽器
    const handleConnectionStateChange = (state: string) => {
      if (state === 'connected' && isInitialized) {
        // 重連後重新設置所有事件監聽器
        manager.on('room_created', handleRoomCreated);
        manager.on('room_deleted', handleRoomDeleted);
        manager.on('room_updated', handleRoomUpdated);
      }
    };

    // 保存事件處理器引用以便後續清理
    eventHandlers.handleRoomCreated = handleRoomCreated;
    eventHandlers.handleRoomDeleted = handleRoomDeleted;
    eventHandlers.handleRoomUpdated = handleRoomUpdated;
    eventHandlers.handleConnectionStateChange = handleConnectionStateChange;

    // 設置事件監聽器
    manager.on('room_created', handleRoomCreated);
    manager.on('room_deleted', handleRoomDeleted);
    manager.on('room_updated', handleRoomUpdated);
    manager.on('connection_state_changed', handleConnectionStateChange);

    isInitialized = true;
    
  } catch (error) {
    isInitialized = false;
  }
}

/**
 * 清理房間列表 WebSocket 同步
 */
export function cleanupRoomListSync() {
  if (!isInitialized) {
    return;
  }


  try {
    const manager = wsManager.getInstance();

    // 移除事件監聽器 - 使用保存的引用
    if (eventHandlers.handleRoomCreated) {
      manager.off('room_created', eventHandlers.handleRoomCreated);
    }
    
    if (eventHandlers.handleRoomDeleted) {
      manager.off('room_deleted', eventHandlers.handleRoomDeleted);
    }
    
    if (eventHandlers.handleRoomUpdated) {
      manager.off('room_updated', eventHandlers.handleRoomUpdated);
    }
    
    if (eventHandlers.handleConnectionStateChange) {
      manager.off('connection_state_changed', eventHandlers.handleConnectionStateChange);
    }

    // 清空事件處理器引用
    eventHandlers = {};

    isInitialized = false;
    
  } catch (error) {
    isInitialized = false;
    eventHandlers = {};
  }
}

/**
 * 檢查是否已初始化
 */
export function isRoomListSyncInitialized(): boolean {
  return isInitialized;
}