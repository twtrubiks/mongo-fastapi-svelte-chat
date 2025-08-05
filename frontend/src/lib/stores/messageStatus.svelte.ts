export type MessageStatus = 'idle' | 'sending' | 'sent' | 'failed';

export interface MessageStatusInfo {
  status: MessageStatus;
  timestamp: number;
  error?: string | undefined;
  retryCount?: number | undefined;
}

export interface MessageStatusState {
  [messageId: string]: MessageStatusInfo;
}

// 創建響應式狀態
let messageStatusState = $state<MessageStatusState>({});

export const messageStatusStore = {
  // 暴露狀態的 getter
  get state() {
    return messageStatusState;
  },
  
  // 設置訊息狀態
  setStatus(messageId: string, status: MessageStatus, error?: string) {
    messageStatusState = {
      ...messageStatusState,
      [messageId]: {
        status,
        timestamp: Date.now(),
        error,
        retryCount: messageStatusState[messageId]?.retryCount || 0
      }
    };
  },

  // 設置為發送中
  setSending(messageId: string) {
    this.setStatus(messageId, 'sending');
  },

  // 設置為已發送
  setSent(messageId: string) {
    this.setStatus(messageId, 'sent');
  },

  // 設置為失敗
  setFailed(messageId: string, error: string) {
    messageStatusState = {
      ...messageStatusState,
      [messageId]: {
        status: 'failed',
        timestamp: Date.now(),
        error,
        retryCount: (messageStatusState[messageId]?.retryCount || 0) + 1
      }
    };
  },

  // 增加重試次數
  incrementRetry(messageId: string) {
    const current = messageStatusState[messageId];
    if (current) {
      messageStatusState = {
        ...messageStatusState,
        [messageId]: {
          ...current,
          retryCount: (current.retryCount || 0) + 1
        }
      };
    }
  },

  // 清除特定訊息狀態
  clearStatus(messageId: string) {
    const newState = { ...messageStatusState };
    delete newState[messageId];
    messageStatusState = newState;
  },

  // 清除所有狀態
  clearAll() {
    messageStatusState = {};
  },

  // 獲取訊息狀態
  getStatus(messageId: string): MessageStatusInfo | undefined {
    return messageStatusState[messageId];
  },

  // 檢查是否有失敗的訊息
  hasFailedMessages(): boolean {
    return Object.values(messageStatusState).some(info => info.status === 'failed');
  },

  // 獲取所有失敗的訊息 ID
  getFailedMessageIds(): string[] {
    return Object.entries(messageStatusState)
      .filter(([_, info]) => info.status === 'failed')
      .map(([id, _]) => id);
  }
};