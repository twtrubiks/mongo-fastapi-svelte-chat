import { wsManager } from '$lib/websocket/manager';
import { notificationStore } from '$lib/stores/notification.svelte';
import type { WebSocketManager } from '$lib/websocket/manager';

/**
 * 已讀狀態同步管理器
 * 負責監聽 WebSocket 事件並同步已讀狀態到本地 stores
 */
export class ReadStatusSync {
  private wsInstance: WebSocketManager | null = null;
  private isSetup = false;

  // 保存 bound 方法引用，確保 on/off 使用同一 reference
  private boundHandleReadStatusUpdated = this.handleReadStatusUpdated.bind(this);

  setup(wsInstance?: WebSocketManager) {
    if (this.isSetup) {
      return;
    }

    this.wsInstance = wsInstance || wsManager.getInstance();

    // 監聽已讀狀態變更事件
    this.wsInstance.on('read_status_updated', this.boundHandleReadStatusUpdated);

    this.isSetup = true;
  }

  private handleReadStatusUpdated(data: any) {
    try {
      const { type, id, status } = data;

      if (status === 'read') {
        if (type === 'notification') {
          notificationStore.markAsRead(id);
        } else if (type === 'all') {
          notificationStore.markAllAsRead();
        }
      }
    } catch {
      // 靜默處理：已讀同步失敗不影響主流程
    }
  }

  cleanup() {
    if (this.wsInstance && this.isSetup) {
      this.wsInstance.off('read_status_updated', this.boundHandleReadStatusUpdated);
    }

    this.isSetup = false;
    this.wsInstance = null;
  }

  isReady(): boolean {
    return this.isSetup && this.wsInstance !== null;
  }
}

// 全域實例
let _readStatusSync: ReadStatusSync | null = null;

export function getReadStatusSync(): ReadStatusSync {
  if (!_readStatusSync) {
    _readStatusSync = new ReadStatusSync();
  }
  return _readStatusSync;
}

export function setupReadStatusSync(wsInstance?: WebSocketManager) {
  const sync = getReadStatusSync();
  sync.setup(wsInstance);
  return sync;
}

export function cleanupReadStatusSync() {
  if (_readStatusSync) {
    _readStatusSync.cleanup();
    _readStatusSync = null;
  }
}
