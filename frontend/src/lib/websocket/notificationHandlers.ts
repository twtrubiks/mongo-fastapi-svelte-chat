import type { HandlerContext } from './handlers';
import type { Notification, WebSocketMessage } from '$lib/types';
import { transformNotification } from '$lib/bff-utils';
import { notificationStore, notificationSettings, browserNotificationManager, soundNotificationManager } from '$lib/stores';
import { apiClient } from '$lib/api/client';

// 分派通知類型的 WebSocket 訊息（從 handleMessage switch 的 'notification' case 抽出）
export function dispatchNotification(data: WebSocketMessage, ctx: HandlerContext) {
  const notificationData = data.data || data.payload;

  // 確保通知資料存在且有效
  if (!notificationData) {
    console.warn('[WebSocket] 收到空的通知資料:', data);
    return;
  }

  if (notificationData.type === 'room_created') {
    // 這是房間創建事件，觸發 room_created 事件
    ctx.emit('room_created', notificationData);
  } else {
    // 轉換通知資料格式
    const transformedNotification = transformNotification(notificationData);

    // 只處理有效的通知
    if (transformedNotification && transformedNotification.title && transformedNotification.message) {
      handleNotification(transformedNotification);
    } else {
      console.warn('[WebSocket] 通知資料格式不正確:', notificationData);
    }
  }
}

// 處理通知
export function handleNotification(notification: Notification) {
  // 檢查通知是否有效
  if (!notification || !notification.title || !notification.message) {
    console.warn('[WebSocket] 收到無效通知:', notification);
    return;
  }

  // 檢查是否為新通知（避免重複播放音效）
  const existingNotifications = notificationStore.notifications;
  const isExistingNotification = existingNotifications.some(n => n.id === notification.id);

  // 無論是否為當前房間，都添加到通知 store
  notificationStore.addNotification(notification);

  // 獲取當前通知設置
  const currentSettings = notificationSettings.value;

  // 播放聲音通知 - 只有新通知才播放音效
  if (currentSettings.sound && !isExistingNotification && notification.status === 'UNREAD') {
    soundNotificationManager.playNotificationSound();
  }

  // 顯示瀏覽器通知
  if (currentSettings.browserNotifications && typeof window !== 'undefined') {
    // 檢查頁面是否可見，如果不可見才顯示瀏覽器通知
    if (document.hidden || document.visibilityState === 'hidden') {
      browserNotificationManager.showNotification(notification.title, {
        body: notification.message,
        icon: '/favicon.svg',
        badge: '/favicon.svg',
        tag: notification.id, // 避免重複通知
        requireInteraction: false,
        data: {
          notificationId: notification.id,
          roomId: notification.data?.['room_id']
        }
      });
    }
  }
}

// 延遲刷新通知列表的計時器，避免頁面切換後 fire-and-forget 寫入 stale store
let refreshTimer: ReturnType<typeof setTimeout> | null = null;

/** 清除待執行的通知刷新計時器，由 manager.disconnect() 呼叫 */
export function cancelPendingNotificationRefresh(): void {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

// 處理通知狀態變更
export function handleNotificationStatusChanged(data: any, ctx: HandlerContext) {
  try {
    const { type, id, status, timestamp, room_id } = data;

    if (status === 'read') {
      if (type === 'notification') {
        notificationStore.markAsRead(id);
      } else if (type === 'room' && room_id) {
        // 延遲 500ms 確保後端已經處理完成，並取消前一次未執行的刷新
        cancelPendingNotificationRefresh();
        refreshTimer = setTimeout(async () => {
          refreshTimer = null;
          try {
            const refreshedData = await apiClient.notifications.list();
            notificationStore.setNotifications(refreshedData.notifications || []);
          } catch (error) {
            console.error('[WebSocket] 刷新通知列表失敗:', error);
          }
        }, 500);
      } else if (type === 'all') {
        notificationStore.markAllAsRead();
      }
    }

    ctx.emit('read_status_updated', { type, id, status, timestamp });

  } catch (error) {
    console.error('[WebSocket] 處理已讀狀態更新失敗:', error);
  }
}
