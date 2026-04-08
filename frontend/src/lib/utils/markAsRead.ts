import { apiClient } from '$lib/api/client';
import { notificationStore } from '$lib/stores/notification.svelte';
import { wsManager } from '$lib/websocket/manager';
import type { Notification } from '$lib/types';

/**
 * 執行已讀操作：透過 WebSocket + API 標記房間通知為已讀
 */
export async function executeMarkAsRead(
  roomId: string,
  options?: { forceRefresh?: boolean }
): Promise<void> {
  const forceRefresh = options?.forceRefresh ?? false;

  // 先嘗試通過 WebSocket 標記已讀
  wsManager.getInstance().markRoomMessagesRead(roomId);

  try {
    // 從 API 獲取最新通知
    const data = await apiClient.notifications.list();
    const allNotifications = data.notifications || [];

    notificationStore.setNotifications(allNotifications);

    // 找到與當前房間相關的未讀通知
    const roomNotifications = allNotifications.filter(
      (n: Notification) => n.room_id === roomId && n.status === 'UNREAD'
    );

    // 逐個標記為已讀
    for (const notification of roomNotifications) {
      try {
        await apiClient.notifications.markAsRead(notification.id);
        notificationStore.markAsRead(notification.id);
        // 給一點時間讓響應式更新生效
        await new Promise((resolve) => setTimeout(resolve, 50));
      } catch (err) {
        console.error('標記通知已讀失敗:', err);
      }
    }

    // 如果是強制刷新，再次從 API 獲取最新狀態
    if (forceRefresh) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        const refreshData = await apiClient.notifications.list();
        notificationStore.setNotifications(refreshData.notifications || []);
      } catch {
        // 靜默處理刷新失敗
      }
    }
  } catch (error) {
    console.error('處理已讀通知失敗:', error);
  }
}

/**
 * 建立已讀狀態追蹤器，封裝進房間/收新訊息時的自動已讀邏輯。
 * 內部管理 debounce timeout 與已處理房間記錄，元件只需呼叫對應方法。
 */
export function createMarkAsReadTracker() {
  let processedRoomId: string | null = null;
  let lastMessageCount = -1;
  let markAsReadTimeoutId: ReturnType<typeof setTimeout> | null = null;
  let roomEnterTimeoutId: ReturnType<typeof setTimeout> | null = null;

  return {
    /**
     * 進入房間時觸發已讀（延遲 500ms 確保訊息已載入）
     * @returns cleanup 函式，供 $effect 清理時呼叫；若已處理過則回傳 undefined
     */
    onRoomEnter(roomId: string, messageCount: number): (() => void) | undefined {
      // 如果已經處理過這個房間，跳過
      if (processedRoomId === roomId) {
        return undefined;
      }

      roomEnterTimeoutId = setTimeout(async () => {
        roomEnterTimeoutId = null;
        await executeMarkAsRead(roomId);
        processedRoomId = roomId;
        lastMessageCount = messageCount;
      }, 500);

      return () => {
        if (roomEnterTimeoutId !== null) {
          clearTimeout(roomEnterTimeoutId);
          roomEnterTimeoutId = null;
        }
      };
    },

    /**
     * 訊息數量變化時觸發已讀（debounce 3 秒 + forceRefresh）
     */
    onNewMessage(roomId: string, messageCount: number): void {
      if (messageCount > lastMessageCount && lastMessageCount >= 0) {
        if (markAsReadTimeoutId !== null) {
          clearTimeout(markAsReadTimeoutId);
        }

        markAsReadTimeoutId = setTimeout(async () => {
          await executeMarkAsRead(roomId, { forceRefresh: true });
          markAsReadTimeoutId = null;
        }, 3000);
      }

      lastMessageCount = messageCount;
    },

    /** 初始化訊息計數（loadRoom 完成後呼叫，避免首次 onNewMessage 誤觸） */
    initMessageCount(count: number): void {
      lastMessageCount = count;
    },

    /** 清理所有 pending timeout */
    destroy(): void {
      if (roomEnterTimeoutId !== null) {
        clearTimeout(roomEnterTimeoutId);
        roomEnterTimeoutId = null;
      }
      if (markAsReadTimeoutId !== null) {
        clearTimeout(markAsReadTimeoutId);
        markAsReadTimeoutId = null;
      }
    },
  };
}
