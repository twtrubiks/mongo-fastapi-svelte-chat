import type { HandlerContext } from './handlers';
import type { Message, WSMessageHistoryMessage, WSTypingMessage, WSErrorMessage, WSAckMessage, WSMessageEditedMessage, WSMessageDeletedMessage, WSMessageSyncMessage } from '$lib/types';
import { messageStore, typingIndicatorStore, messageStatusStore } from '$lib/stores';
import { extractUserId } from '$lib/utils/userIdNormalizer';

// 處理新訊息
export function handleNewMessage(message: Message) {
  messageStore.addMessage(message);
}

// 處理伺服器 ack（訊息已持久化）
export function handleAck(data: WSAckMessage) {
  const clientId = data.client_id;
  if (!clientId) return;

  // 以伺服器 id/seq 確認樂觀訊息
  messageStore.confirmMessage(clientId, data.message_id, data.seq);

  // 動態載入避免循環 import（messageRetry → manager → messageHandlers）
  void import('$lib/utils/messageRetry').then(({ messageRetryManager }) => {
    // 從重試佇列移除（會一併清除狀態），再標記為已送達供氣泡顯示
    messageRetryManager.removeFromQueue(clientId);
    messageStatusStore.setSent(clientId);
  });
}

// 處理訊息編輯廣播
export function handleMessageEdited(data: WSMessageEditedMessage) {
  messageStore.applyEdit(data.message);
}

// 處理訊息刪除廣播
export function handleMessageDeleted(data: WSMessageDeletedMessage) {
  messageStore.removeMessage(data.message_id);
}

// 處理斷線重連 gap 補發
export function handleMessageSync(data: WSMessageSyncMessage) {
  messageStore.applySync(data.messages, data.full_reload);
}

// 處理歷史訊息
export function handleMessageHistory(data: WSMessageHistoryMessage) {
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
export function handleTypingIndicator(data: WSTypingMessage, ctx: HandlerContext) {
  const { user, is_typing: isTyping, room_id } = data;
  const roomId = room_id || ctx.roomId;
  if (!roomId) return;

  typingIndicatorStore.setTyping(roomId, {
    userId: extractUserId(user) || '',
    username: user.username,
    avatar: user.avatar,
  }, isTyping);
}

// 處理錯誤
export function handleError(data: WSErrorMessage, ctx: HandlerContext) {
  // 如果錯誤包含 temp_id，更新對應訊息的狀態
  if (data.temp_id) {
    messageStatusStore.setFailed(data.temp_id, data.message || '未知錯誤');
  }

  // 觸發錯誤事件
  ctx.emit('message_error', data);
}
