/**
 * 房間列表 WebSocket 同步
 * 處理房間創建等需要在全局范圍內監聽的事件
 */

import { wsManager } from './manager';
import { roomStore } from '$lib/stores/room.svelte';

let isInitialized = false;
let eventHandlers: {
  handleRoomCreated?: (data: any) => void;
  handleRoomDeleted?: (data: any) => void;
  handleRoomUpdated?: (data: any) => void;
} = {};

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

    // 保存事件處理器引用以便後續清理
    eventHandlers.handleRoomCreated = handleRoomCreated;
    eventHandlers.handleRoomDeleted = handleRoomDeleted;
    eventHandlers.handleRoomUpdated = handleRoomUpdated;

    // 設置事件監聽器（listener 在 manager 上持久存在，重連時無需重新註冊）
    manager.on('room_created', handleRoomCreated);
    manager.on('room_deleted', handleRoomDeleted);
    manager.on('room_updated', handleRoomUpdated);

    isInitialized = true;
    
  } catch {
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
    
    // 清空事件處理器引用
    eventHandlers = {};

    isInitialized = false;
    
  } catch {
    isInitialized = false;
    eventHandlers = {};
  }
}

