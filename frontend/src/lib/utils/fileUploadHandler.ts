import { getFileType, getFileTypeLabel, inferMimeTypeFromUrl } from '$lib/utils';
import { messageRetryManager } from '$lib/utils/messageRetry';
import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
import type { MessageCreate } from '$lib/types';

export interface FileUploadParams {
  file: File;
  url: string;
  filename: string;
  roomId: string;
  isWsConnected: boolean;
  /** WebSocket 發送函式（由呼叫端注入，避免模組直接耦合 wsManager） */
  sendWsMessage: (
    content: string,
    type: 'text' | 'image' | 'file',
    messageId: string,
    metadata: Record<string, unknown>
  ) => boolean;
  /** HTTP fallback 發送函式 */
  sendHttpMessage: (roomId: string, data: MessageCreate) => Promise<void>;
}

export interface FileUploadResult {
  success: boolean;
  message: string;
  messageType: 'success' | 'error';
}

/**
 * 處理檔案上傳後的訊息發送邏輯：
 * 決定訊息類型、準備元數據、加入重試佇列、透過 WS 或 HTTP 發送。
 */
export async function processFileUpload(
  params: FileUploadParams
): Promise<FileUploadResult> {
  const {
    file,
    url,
    filename,
    roomId,
    isWsConnected,
    sendWsMessage,
    sendHttpMessage,
  } = params;

  try {
    if (!url) {
      throw new Error('上傳回應中沒有檔案URL');
    }

    // 決定訊息類型
    const fileType = getFileType(file);
    const messageType = fileType === 'image' ? 'image' : 'file';

    // 生成訊息 ID 用於重試追蹤
    const messageId = `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // 準備檔案元數據
    const fileMetadata: Record<string, unknown> = {
      filename,
      fileSize: file.size,
      mimeType: file.type || inferMimeTypeFromUrl(url),
      originalName: file.name,
      uploadedAt: new Date().toISOString(),
    };

    // 添加到重試佇列
    messageRetryManager.addToRetryQueue({
      id: messageId,
      content: url,
      type: messageType,
      metadata: fileMetadata,
    });

    // 發送檔案訊息
    if (isWsConnected) {
      sendWsMessage(url, messageType, messageId, fileMetadata);
    } else {
      // 帶上 client_id：之後以 WebSocket 重送時，後端才能認出是同一則而不重複存
      try {
        await sendHttpMessage(roomId, {
          content: url,
          message_type: messageType,
          client_id: messageId,
          metadata: fileMetadata,
        });
      } catch (error) {
        // 標記失敗才會出現在重試提示，重新連上 WebSocket 時也會自動重送
        messageStatusStore.setFailed(messageId, '訊息未送出，請重試');
        throw error;
      }
      // HTTP 送出不會收到 ack，成功即移出重試佇列
      messageRetryManager.removeFromQueue(messageId);
    }

    return {
      success: true,
      message: `${getFileTypeLabel(file)}上傳成功`,
      messageType: 'success',
    };
  } catch (error) {
    console.error('發送檔案訊息失敗:', error);
    return {
      success: false,
      message: '發送檔案訊息失敗',
      messageType: 'error',
    };
  }
}
