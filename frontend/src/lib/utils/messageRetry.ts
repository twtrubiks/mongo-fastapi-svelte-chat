import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
import { wsManager } from '$lib/websocket/manager';

export interface RetryableMessage {
  id: string;
  content: string;
  type: 'text' | 'image';
  maxRetries?: number;
}

class MessageRetryManager {
  private retryQueue: Map<string, RetryableMessage> = new Map();
  private retryTimeouts: Map<string, number> = new Map();
  private readonly DEFAULT_MAX_RETRIES = 3;
  private readonly RETRY_DELAYS = [1000, 2000, 5000]; // 1s, 2s, 5s

  /**
   * 添加訊息到重試佇列
   */
  addToRetryQueue(message: RetryableMessage) {
    this.retryQueue.set(message.id, message);
  }

  /**
   * 重試發送訊息
   */
  async retryMessage(messageId: string): Promise<boolean> {
    const message = this.retryQueue.get(messageId);
    if (!message) {
      console.warn(`Message ${messageId} not found in retry queue`);
      return false;
    }

    const currentStatus = messageStatusStore.getStatus(messageId);
    const retryCount = currentStatus?.retryCount || 0;
    const maxRetries = message.maxRetries || this.DEFAULT_MAX_RETRIES;

    if (retryCount >= maxRetries) {
      console.error(`Message ${messageId} exceeded max retries (${maxRetries})`);
      messageStatusStore.setFailed(messageId, `重試次數已達上限 (${maxRetries})`);
      this.removeFromQueue(messageId);
      return false;
    }

    // 檢查 WebSocket 連線狀態
    const wsInstance = wsManager.getInstance();
    if (!wsInstance.isConnected()) {
      console.warn(`[MessageRetry] WebSocket 未連接，延遲重試訊息 ${messageId}`);
      // 如果未連接，直接安排下次重試
      this.scheduleRetry(messageId);
      return false;
    }

    // 增加重試次數
    messageStatusStore.incrementRetry(messageId);

    try {
      // 嘗試重新發送
      console.debug(`[MessageRetry] 正在重試訊息 ${messageId}, 第 ${retryCount + 1} 次`);
      const success = wsInstance.sendMessage(message.content, message.type, messageId);
      
      if (success) {
        // 發送成功，從佇列中移除
        console.debug(`[MessageRetry] 訊息 ${messageId} 重試成功`);
        this.removeFromQueue(messageId);
        return true;
      } else {
        // 發送失敗，安排下次重試
        console.warn(`[MessageRetry] 訊息 ${messageId} 重試失敗，安排下次重試`);
        this.scheduleRetry(messageId);
        return false;
      }
    } catch (error) {
      console.error(`[MessageRetry] 重試訊息 ${messageId} 時發生錯誤:`, error);
      messageStatusStore.setFailed(messageId, `重試失敗: ${error.message || '未知錯誤'}`);
      this.scheduleRetry(messageId);
      return false;
    }
  }

  /**
   * 安排自動重試
   */
  private scheduleRetry(messageId: string) {
    const currentStatus = messageStatusStore.getStatus(messageId);
    const retryCount = currentStatus?.retryCount || 0;
    
    if (retryCount >= this.RETRY_DELAYS.length) {
      // 超過重試次數，不再自動重試
      return;
    }

    const delay = this.RETRY_DELAYS[retryCount - 1] || this.RETRY_DELAYS[this.RETRY_DELAYS.length - 1];
    
    // 清除之前的重試計時器
    this.clearRetryTimeout(messageId);
    
    // 設置新的重試計時器
    const timeoutId = window.setTimeout(() => {
      this.retryMessage(messageId);
    }, delay);
    
    this.retryTimeouts.set(messageId, timeoutId);
  }

  /**
   * 手動重試訊息
   */
  async manualRetry(messageId: string): Promise<boolean> {
    // 清除自動重試計時器
    this.clearRetryTimeout(messageId);
    
    // 重置重試次數（手動重試從 0 開始）
    messageStatusStore.setStatus(messageId, 'idle');
    
    return await this.retryMessage(messageId);
  }

  /**
   * 重試所有失敗的訊息
   */
  async retryAllFailed(): Promise<void> {
    const failedIds = messageStatusStore.getFailedMessageIds();
    console.log(`[MessageRetry] 開始重試 ${failedIds.length} 則失敗訊息`);
    
    for (const messageId of failedIds) {
      // 確保訊息在重試佇列中
      if (!this.retryQueue.has(messageId)) {
        console.warn(`[MessageRetry] 訊息 ${messageId} 不在重試佇列中，跳過`);
        continue;
      }
      
      await this.manualRetry(messageId);
      // 加入小延遲避免同時發送太多訊息
      await new Promise(resolve => setTimeout(resolve, 100));
    }
  }

  /**
   * 從重試佇列中移除訊息
   */
  removeFromQueue(messageId: string) {
    this.retryQueue.delete(messageId);
    this.clearRetryTimeout(messageId);
    messageStatusStore.clearStatus(messageId);
  }

  /**
   * 清除重試計時器
   */
  private clearRetryTimeout(messageId: string) {
    const timeoutId = this.retryTimeouts.get(messageId);
    if (timeoutId) {
      clearTimeout(timeoutId);
      this.retryTimeouts.delete(messageId);
    }
  }

  /**
   * 清除所有重試
   */
  clearAll() {
    // 清除所有計時器
    for (const timeoutId of this.retryTimeouts.values()) {
      clearTimeout(timeoutId);
    }
    
    this.retryQueue.clear();
    this.retryTimeouts.clear();
    messageStatusStore.clearAll();
  }

  /**
   * 獲取佇列中的訊息數量
   */
  getQueueSize(): number {
    return this.retryQueue.size;
  }

  /**
   * 檢查訊息是否在重試佇列中
   */
  isInQueue(messageId: string): boolean {
    return this.retryQueue.has(messageId);
  }
}

// 導出單例實例
export const messageRetryManager = new MessageRetryManager();

// 監聽 WebSocket 連線狀態變化
if (typeof window !== 'undefined') {
  const ws = wsManager.getInstance();
  
  // 當連線成功時，自動重試所有失敗的訊息
  ws.on('connection_state_changed', (state: string) => {
    if (state === 'connected') {
      // console.log('[MessageRetry] WebSocket 已連接，檢查是否有需要重試的訊息');
      const failedMessages = messageStatusStore.getFailedMessageIds();
      if (failedMessages.length > 0) {
        console.log(`[MessageRetry] 發現 ${failedMessages.length} 則失敗訊息，開始重試`);
        // 延遲一點時間讓連線穩定
        setTimeout(() => {
          messageRetryManager.retryAllFailed();
        }, 1000);
      }
    }
  });
}