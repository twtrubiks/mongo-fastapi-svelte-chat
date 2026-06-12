import { apiClient } from '../api/client';
import type { MessageState, Message, MessageCreate } from '../types';

// 初始狀態
const initialState: MessageState = {
  messages: [],
  loading: false,
  hasMore: true,
};

// 創建響應式狀態
let messageState = $state<MessageState>(initialState);

export const messageStore = {
  // 暴露狀態的 getter
  get state() {
    return messageState;
  },

  get messages() {
    return messageState.messages;
  },

  get loading() {
    return messageState.loading;
  },

  get hasMore() {
    return messageState.hasMore;
  },
  
  // 載入訊息
  loadMessages: async (roomId: string, limit: number = 50) => {
    messageState = {
      messages: messageState.messages,
      loading: true,
      hasMore: messageState.hasMore
    };

    try {
      const messages = await apiClient.messages.list(roomId, limit);
      messageState = {
        messages: messages, // 後端已經按正確順序返回（最舊到最新）
        loading: false,
        hasMore: messages.length === limit, // 如果返回的訊息數量等於限制，說明可能還有更多
      };
      return messages;
    } catch (error) {
      console.error('[MessageStore] 載入訊息失敗:', error);
      messageState = {
        messages: messageState.messages,
        loading: false,
        hasMore: messageState.hasMore
      };
      throw error;
    }
  },

  // 載入更多訊息 (分頁)
  loadMoreMessages: async (roomId: string, limit: number = 50) => {
    if (messageState.loading || !messageState.hasMore) return;
    
    messageState = {
      messages: messageState.messages,
      loading: true,
      hasMore: messageState.hasMore
    };
    
    try {
      const currentMessages = messageState.messages;

      // 使用最早的訊息作為游標參考點
      const oldestMessage = currentMessages[0];
      if (!oldestMessage) return;

      // 游標分頁：以最早訊息的 seq 為游標（不受訊息增刪造成的偏移影響）
      // 舊資料無 seq 時 fallback 到 skip/limit
      const skip = currentMessages.length;
      const messages = await apiClient.messages.list(
        roomId, limit, skip, oldestMessage.seq
      );

      // 過濾掉已經存在的訊息
      const newMessages = messages.filter(msg =>
        !currentMessages.some(existing => existing.id === msg.id)
      );

      messageState = {
        messages: [...newMessages, ...messageState.messages], // 後端已按正確順序返回，新訊息在前面
        loading: false,
        hasMore: messages.length === limit,
      };
      
      return newMessages;
    } catch (error) {
      messageState = {
        messages: messageState.messages,
        loading: false,
        hasMore: messageState.hasMore
      };
      throw error;
    }
  },

  // 發送訊息
  sendMessage: async (roomId: string, messageData: MessageCreate) => {
    const message = await apiClient.messages.send(roomId, messageData);

    // 通常訊息會通過 WebSocket 收到，這裡只是備用
    // addMessage 內建去重與樂觀訊息取代（依 id / client_id）
    messageStore.addMessage(message);

    return message;
  },

  // 添加訊息 (WebSocket 事件)
  addMessage: (message: Message) => {
    // 避免重複添加
    const exists = messageState.messages.some(msg => msg.id === message.id);
    if (exists) {
      return;
    }

    // 樂觀 UI：若帶相同 client_id 的 pending 訊息已存在，以伺服器版本原地取代
    if (message.client_id) {
      const pendingIndex = messageState.messages.findIndex(
        msg => msg.client_id === message.client_id
      );
      if (pendingIndex !== -1) {
        const newMessages = [...messageState.messages];
        newMessages[pendingIndex] = { ...message, pending: false };
        messageState = { ...messageState, messages: newMessages };
        return;
      }
    }

    // 根據時間戳正確插入訊息
    const newMessages = [...messageState.messages, message];
    newMessages.sort((a, b) => {
      const timeA = new Date(a.created_at).getTime();
      const timeB = new Date(b.created_at).getTime();
      return timeA - timeB; // 從舊到新排序
    });

    // 在 Svelte 5 中，需要創建全新的狀態對象來觸發響應式更新
    messageState = {
      messages: newMessages,
      loading: messageState.loading,
      hasMore: messageState.hasMore
    };
  },

  // 加入樂觀訊息（發送當下立即顯示，等待 ack/廣播確認）
  addPendingMessage: (message: Message) => {
    if (messageState.messages.some(msg => msg.client_id === message.client_id)) {
      return; // 重試時已存在，不重複插入
    }
    messageState = {
      ...messageState,
      messages: [...messageState.messages, { ...message, pending: true }],
    };
  },

  // 收到 ack：以伺服器 id/seq 確認樂觀訊息
  confirmMessage: (clientId: string, serverId: string, seq?: number) => {
    const index = messageState.messages.findIndex(msg => msg.client_id === clientId);
    if (index === -1) return;
    const newMessages = [...messageState.messages];
    const confirmed = { ...newMessages[index]!, id: serverId, pending: false };
    if (seq !== undefined) confirmed.seq = seq;
    newMessages[index] = confirmed;
    messageState = { ...messageState, messages: newMessages };
  },

  // 套用編輯事件（message_edited：依 id 合併部分欄位）
  applyEdit: (partial: Partial<Message> & { id: string }) => {
    const index = messageState.messages.findIndex(msg => msg.id === partial.id);
    if (index === -1) return;
    const newMessages = [...messageState.messages];
    newMessages[index] = { ...newMessages[index]!, ...partial };
    messageState = { ...messageState, messages: newMessages };
  },

  // 移除訊息（message_deleted：與歷史載入過濾已刪除訊息的行為一致）
  removeMessage: (messageId: string) => {
    const newMessages = messageState.messages.filter(msg => msg.id !== messageId);
    if (newMessages.length === messageState.messages.length) return;
    messageState = { ...messageState, messages: newMessages };
  },

  // 套用斷線重連補發（message_sync）
  applySync: (messages: Message[], fullReload: boolean) => {
    if (fullReload) {
      // gap 過大：以本批訊息（最新 50 條）整批重載
      messageState = {
        messages: [...messages],
        loading: false,
        hasMore: true,
      };
      return;
    }
    // 增量補發：逐筆合併（addMessage 內建 id/client_id 去重）
    messages.forEach(msg => messageStore.addMessage(msg));
  },

  // 取得目前已知的最大序號（重連時帶給後端精確補 gap）
  getMaxSeq: (roomId: string): number | null => {
    let max = 0;
    for (const msg of messageState.messages) {
      if (msg.room_id === roomId && typeof msg.seq === 'number' && msg.seq > max) {
        max = msg.seq;
      }
    }
    return max > 0 ? max : null;
  },

  // 清除訊息 (切換聊天室時)
  clearMessages: () => {
    messageState = initialState;
  },

};

// 派生值 - 轉換為 getter 函數以支援 SSR
export const messageList = () => messageState.messages;

export const messageLoading = () => messageState.loading;

