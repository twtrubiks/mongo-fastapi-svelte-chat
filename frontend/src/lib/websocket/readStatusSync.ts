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

  /**
   * 設置已讀狀態同步
   * @param wsInstance WebSocket 管理器實例
   */
  setup(wsInstance?: WebSocketManager) {
    if (this.isSetup) {
      return;
    }

    this.wsInstance = wsInstance || wsManager.getInstance();
    
    // 監聽已讀狀態變更事件
    this.wsInstance.on('read_status_updated', this.handleReadStatusUpdated.bind(this));
    
    // 監聽操作成功事件
    this.wsInstance.on('read_operation_success', this.handleOperationSuccess.bind(this));
    
    // 監聽操作失敗事件
    this.wsInstance.on('read_operation_failed', this.handleOperationFailed.bind(this));

    // 監聽連接狀態變化
    this.wsInstance.on('connected', this.handleConnected.bind(this));
    this.wsInstance.on('disconnected', this.handleDisconnected.bind(this));

    this.isSetup = true;
  }

  /**
   * 處理已讀狀態更新（來自其他設備的同步）
   */
  private handleReadStatusUpdated(data: any) {
    
    try {
      const { type, id, status, timestamp } = data;
      
      if (status === 'read') {
        if (type === 'notification') {
          // 同步單個通知已讀狀態
          notificationStore.markAsRead(id);
        } else if (type === 'room') {
          // 處理房間消息已讀狀態同步
          // 如果將來有房間消息已讀的 store，可以在這裡處理
        } else if (type === 'all') {
          // 同步所有通知已讀狀態
          notificationStore.markAllAsRead();
        }
      }
    } catch (error) {
    }
  }

  /**
   * 處理操作成功響應
   */
  private handleOperationSuccess(data: any) {
    
    // 可以在這裡添加成功的 UI 反饋
    // 例如顯示 toast 通知或更新 UI 狀態
  }

  /**
   * 處理操作失敗響應
   */
  private handleOperationFailed(data: any) {
    
    // UI 層面的錯誤處理已經在 notificationStore.handleOperationFailure 中處理
    // 這裡可以添加額外的用戶反饋
    
    // 可以顯示錯誤提示
    this.showErrorMessage(data.error || '標記已讀失敗，請重試');
  }

  /**
   * 處理 WebSocket 連接成功
   */
  private handleConnected() {
    
    // 連接成功後可以考慮同步狀態
    // 但由於我們使用樂觀更新，通常不需要額外同步
  }

  /**
   * 處理 WebSocket 連接斷開
   */
  private handleDisconnected(data: any) {
    
    // 連接斷開時，可以考慮暫停某些操作
    // 或者提示用戶連接狀態
  }

  /**
   * 顯示錯誤訊息（簡單實現）
   * 在實際應用中，這應該整合到全域的通知系統中
   */
  private showErrorMessage(message: string) {
    // 簡單的控制台輸出，實際應用中可以使用 toast 組件
    
    // 如果有全域 toast 或通知系統，可以在這裡調用
    // 例如：toast.error(message);
  }

  /**
   * 清理資源
   */
  cleanup() {
    if (this.wsInstance && this.isSetup) {
      this.wsInstance.off('read_status_updated', this.handleReadStatusUpdated.bind(this));
      this.wsInstance.off('read_operation_success', this.handleOperationSuccess.bind(this));
      this.wsInstance.off('read_operation_failed', this.handleOperationFailed.bind(this));
      this.wsInstance.off('connected', this.handleConnected.bind(this));
      this.wsInstance.off('disconnected', this.handleDisconnected.bind(this));
    }
    
    this.isSetup = false;
    this.wsInstance = null;
  }

  /**
   * 檢查是否已設置
   */
  isReady(): boolean {
    return this.isSetup && this.wsInstance !== null;
  }
}

// 全域實例
let _readStatusSync: ReadStatusSync | null = null;

/**
 * 獲取已讀狀態同步管理器實例
 */
export function getReadStatusSync(): ReadStatusSync {
  if (!_readStatusSync) {
    _readStatusSync = new ReadStatusSync();
  }
  return _readStatusSync;
}

/**
 * 便捷函數：設置已讀狀態同步
 * 可以在應用初始化時調用
 */
export function setupReadStatusSync(wsInstance?: WebSocketManager) {
  const sync = getReadStatusSync();
  sync.setup(wsInstance);
  return sync;
}

/**
 * 便捷函數：清理已讀狀態同步
 * 可以在應用清理時調用
 */
export function cleanupReadStatusSync() {
  if (_readStatusSync) {
    _readStatusSync.cleanup();
    _readStatusSync = null;
  }
}