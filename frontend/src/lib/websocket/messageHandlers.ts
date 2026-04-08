import type { HandlerContext } from './handlers';
import type { Message, WebSocketMessage } from '$lib/types';
import { messageStore, typingIndicatorStore, messageStatusStore } from '$lib/stores';
import { extractUserId } from '$lib/utils/userIdNormalizer';

// 處理新訊息
export function handleNewMessage(message: Message) {
  messageStore.addMessage(message);
}

// 處理歷史訊息
export function handleMessageHistory(data: any) {
  if (data.messages && Array.isArray(data.messages)) {
    // 批量添加歷史訊息到 store，但過濾掉系統訊息
    // 系統訊息應該由實時事件生成，而不是從歷史記錄載入
    data.messages.forEach((message: Message) => {
      if (message.message_type !== 'system') {
        messageStore.addMessage(message);
      }
    });
  }
}

// 處理打字指示器
export function handleTypingIndicator(data: WebSocketMessage, ctx: HandlerContext) {
  const user = data.user;
  const isTyping = data.is_typing ?? false;
  const roomId = data.room_id || ctx.roomId;
  if (!user || !roomId) return;

  typingIndicatorStore.setTyping(roomId, {
    userId: extractUserId(user) || '',
    username: user.username,
    avatar: user.avatar,
  }, isTyping);
}

// 處理錯誤
export function handleError(error: any, ctx: HandlerContext) {
  // 如果錯誤包含 temp_id，更新對應訊息的狀態
  if (error.temp_id) {
    messageStatusStore.setFailed(error.temp_id, error.message || '未知錯誤');
  }

  // 觸發錯誤事件
  ctx.emit('message_error', error);
}
