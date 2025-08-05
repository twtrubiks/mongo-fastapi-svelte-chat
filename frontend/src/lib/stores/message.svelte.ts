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
    // console.log('[MessageStore] 開始載入訊息:', { roomId, limit });
    messageState = {
      messages: messageState.messages,
      loading: true,
      hasMore: messageState.hasMore
    };
    // console.log('[MessageStore] 設置 loading = true');
    
    try {
      const messages = await apiClient.messages.list(roomId, limit);
      // console.log('[MessageStore] API 調用完成，收到訊息數量:', messages.length);
      
      messageState = {
        messages: messages, // 後端已經按正確順序返回（最舊到最新）
        loading: false,
        hasMore: messages.length === limit, // 如果返回的訊息數量等於限制，說明可能還有更多
      };
      // console.log('[MessageStore] 設置 loading = false，訊息載入完成');
      
      return messages;
    } catch (error) {
      console.error('[MessageStore] 載入訊息失敗:', error);
      messageState = {
        messages: messageState.messages,
        loading: false,
        hasMore: messageState.hasMore
      };
      // console.log('[MessageStore] 錯誤情況下設置 loading = false');
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

      // 使用最早的訊息時間作為參考點
      const oldestMessage = currentMessages[0];
      if (!oldestMessage) return;

      const messages = await apiClient.messages.list(roomId, limit);
      
      // 過濾掉已經存在的訊息
      const newMessages = messages.filter(msg => 
        !currentMessages.some(existing => existing.id === msg.id)
      );
      
      messageState = {
        messages: [...newMessages, ...messageState.messages], // 後端已按正確順序返回，新訊息在前面
        loading: false,
        hasMore: newMessages.length === limit,
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
    try {
      const message = await apiClient.messages.send(roomId, messageData);
      
      // 通常訊息會通過 WebSocket 收到，這裡只是備用
      // 避免重複添加，如果 WebSocket 正常工作的話
      const exists = messageState.messages.some(msg => msg.id === message.id);
      if (!exists) {
        messageState = {
          messages: [...messageState.messages, message],
          loading: messageState.loading,
          hasMore: messageState.hasMore
        };
      }
      
      return message;
    } catch (error) {
      throw error;
    }
  },

  // 添加訊息 (WebSocket 事件)
  addMessage: (message: Message) => {
    // 避免重複添加
    const exists = messageState.messages.some(msg => msg.id === message.id);
    if (exists) {
      return;
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

  // 更新訊息
  updateMessage: (messageId: string, updates: Partial<Message>) => {
    // 在 Svelte 5 中，需要創建全新的狀態對象
    messageState = {
      messages: messageState.messages.map(msg => 
        msg.id === messageId ? { ...msg, ...updates } : msg
      ),
      loading: messageState.loading,
      hasMore: messageState.hasMore
    };
  },

  // 刪除訊息
  removeMessage: (messageId: string) => {
    // 在 Svelte 5 中，需要創建全新的狀態對象
    messageState = {
      messages: messageState.messages.filter(msg => msg.id !== messageId),
      loading: messageState.loading,
      hasMore: messageState.hasMore
    };
  },

  // 清除訊息 (切換聊天室時)
  clearMessages: () => {
    messageState = initialState;
  },

  // 設置載入狀態
  setLoading: (loading: boolean) => {
    messageState = {
      messages: messageState.messages,
      loading: loading,
      hasMore: messageState.hasMore
    };
  },

  // 按房間 ID 篩選訊息
  getMessagesByRoom: (roomId: string) => {
    return messageState.messages.filter(msg => msg.room_id === roomId);
  },
};

// 派生值 - 轉換為 getter 函數以支援 SSR
export const messageList = () => messageState.messages;

export const messageLoading = () => messageState.loading;

export const hasMoreMessages = () => messageState.hasMore;

export const latestMessage = () =>
  messageState.messages.length > 0 
    ? messageState.messages[messageState.messages.length - 1] 
    : null;