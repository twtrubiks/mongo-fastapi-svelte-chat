import { getFileType, getFileTypeLabel, inferMimeTypeFromUrl } from '$lib/utils';
import { messageRetryManager } from '$lib/utils/messageRetry';

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
  sendHttpMessage: (
    roomId: string,
    data: { content: string; message_type: 'text' | 'image' | 'file' }
  ) => Promise<void>;
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
      type: messageType as 'text' | 'image',
    });

    // 發送檔案訊息
    if (isWsConnected) {
      sendWsMessage(url, messageType, messageId, fileMetadata);
    } else {
      await sendHttpMessage(roomId, {
        content: url,
        message_type: messageType as 'text' | 'image' | 'file',
      });
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
