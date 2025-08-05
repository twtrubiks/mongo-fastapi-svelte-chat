import { messageStore } from '$lib/stores/message.svelte';
import type { Message } from '$lib/types';

/**
 * 樂觀訊息更新工具
 * 在發送訊息時立即更新 UI，不等待服務器確認
 */

/**
 * 創建臨時訊息對象
 * @param content 訊息內容
 * @param messageType 訊息類型
 * @param roomId 房間 ID
 * @param userId 用戶 ID
 * @param username 用戶名
 * @returns 臨時訊息對象
 */
export function createOptimisticMessage(
  content: string,
  messageType: 'text' | 'image',
  roomId: string,
  userId: string,
  username: string
): Message {
  const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
  return {
    id: tempId,
    room_id: roomId,
    user_id: userId,
    content,
    message_type: messageType,
    created_at: new Date().toISOString(),
    user: {
      id: userId,
      username,
      email: '',
      created_at: new Date().toISOString(),
    }
  };
}

/**
 * 發送訊息並進行樂觀更新
 * @param content 訊息內容
 * @param messageType 訊息類型
 * @param roomId 房間 ID
 * @param userId 用戶 ID
 * @param username 用戶名
 * @param sendFunction 實際發送函數
 * @returns 是否成功
 */
export async function sendMessageWithOptimisticUpdate(
  content: string,
  messageType: 'text' | 'image',
  roomId: string,
  userId: string,
  username: string,
  sendFunction: () => Promise<boolean> | boolean
): Promise<boolean> {
  // 1. 創建樂觀訊息
  const optimisticMessage = createOptimisticMessage(
    content,
    messageType,
    roomId,
    userId,
    username
  );

  // 2. 立即添加到 UI
  messageStore.addMessage(optimisticMessage);

  try {
    // 3. 發送實際訊息
    const success = await sendFunction();
    
    if (!success) {
      // 4. 如果發送失敗，移除樂觀訊息
      messageStore.removeMessage(optimisticMessage.id);
      return false;
    }

    // 5. 發送成功，樂觀訊息會被服務器的真實訊息替換（如果服務器有回顯）
    // 或者我們可以將臨時 ID 更新為真實 ID（如果服務器返回真實訊息）
    
    return true;
  } catch (error) {
    // 發送失敗，移除樂觀訊息
    messageStore.removeMessage(optimisticMessage.id);
    console.error('Failed to send message:', error);
    return false;
  }
}

/**
 * 處理服務器回顯訊息
 * 如果收到的訊息是自己發送的，且存在對應的樂觀訊息，則替換它
 * @param serverMessage 服務器返回的訊息
 * @param userId 當前用戶 ID
 */
export function handleServerMessageEcho(serverMessage: Message, userId: string) {
  // 只處理自己發送的訊息
  if (serverMessage.user_id !== userId) {
    return;
  }

  // 檢查是否有對應的樂觀訊息需要替換
  const currentMessages = messageStore.getMessages();
  const optimisticMessage = currentMessages.find(msg => 
    msg.id.startsWith('temp_') &&
    msg.content === serverMessage.content &&
    msg.user_id === serverMessage.user_id &&
    // 時間差在 10 秒內
    Math.abs(new Date(msg.created_at).getTime() - new Date(serverMessage.created_at).getTime()) < 10000
  );

  if (optimisticMessage) {
    // 替換樂觀訊息
    messageStore.removeMessage(optimisticMessage.id);
    messageStore.addMessage(serverMessage);
  } else {
    // 沒有找到對應的樂觀訊息，直接添加（可能是其他設備發送的）
    messageStore.addMessage(serverMessage);
  }
}