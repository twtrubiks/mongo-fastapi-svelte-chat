<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { notifications, notificationStore, type Notification } from '$lib/stores/notification.svelte';
  import { formatDistanceToNow } from 'date-fns';
  import { zhTW } from 'date-fns/locale';
  import { formatDateTime } from '$lib/utils/datetime';
  import Button from './Button.svelte';
  import Loading from './Loading.svelte';

  interface Props {
    isOpen?: boolean;
    onClose?: () => void;
  }

  let { isOpen = false, onClose = undefined }: Props = $props();

  let loading = $state(false);
  let error: string | null = $state(null);
  
  // 創建本地的響應式變數，避免重複調用函數
  let notificationList = $derived(notifications());
  // 直接從 store 獲取統計資訊
  let stats = $derived(notificationStore.stats);

  // 通知類型的顯示名稱和圖標
  const notificationTypeConfig = {
    MESSAGE: { name: '新訊息', icon: '💬', color: 'bg-blue-100 text-blue-800' },
    ROOM_INVITE: { name: '房間邀請', icon: '📧', color: 'bg-green-100 text-green-800' },
    ROOM_JOIN: { name: '加入房間', icon: '👋', color: 'bg-yellow-100 text-yellow-800' },
    ROOM_LEAVE: { name: '離開房間', icon: '👋', color: 'bg-gray-100 text-gray-800' },
    SYSTEM: { name: '系統通知', icon: '⚙️', color: 'bg-purple-100 text-purple-800' },
    MENTION: { name: '提及', icon: '🔔', color: 'bg-red-100 text-red-800' }
  };

  async function loadNotifications() {
    loading = true;
    error = null;
    
    try {
      const response = await fetch('/api/notifications/', {
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('載入通知失敗');
      }

      const data = await response.json();
      // console.log('[NotificationPanel] 載入的通知數據:', data);
      // console.log('[NotificationPanel] 通知數量:', data.notifications?.length || 0);
      // console.log('[NotificationPanel] 未讀通知:', data.notifications?.filter(n => n.status === 'UNREAD') || []);
      
      // 檢查第一個通知的詳細內容
      if (data.notifications && data.notifications.length > 0) {
      }
      
      notificationStore.setNotifications(data.notifications || []);
    } catch (e) {
      error = e instanceof Error ? e.message : '載入通知時發生錯誤';
    } finally {
      loading = false;
    }
  }

  async function markAsRead(notificationId: string) {
    try {
      
      const response = await fetch(`/api/notifications/${notificationId}/read`, {
        method: 'POST',
        credentials: 'include'
      });

      
      if (response.ok) {
        notificationStore.markAsRead(notificationId);
      } else {
        const errorText = await response.text();
      }
    } catch (e) {
    }
  }

  async function markAllAsRead() {
    try {
      
      // 樂觀更新：立即更新本地狀態
      notificationStore.markAllAsRead();
      
      
      // 發送 API 請求
      const response = await fetch('/api/notifications/read-all', {
        method: 'POST',
        credentials: 'include'
      });

      if (response.ok) {
        // 樂觀更新已經完成，不需要再次更新
      } else {
        // TODO: 如果 API 失敗，應該回滾樂觀更新
      }
    } catch (e) {
      // TODO: 同樣應該回滾樂觀更新
    }
  }

  async function deleteNotification(notificationId: string) {
    try {
      const response = await fetch(`/api/notifications/${notificationId}`, {
        method: 'DELETE',
        credentials: 'include'
      });


      if (response.ok) {
        notificationStore.removeNotification(notificationId);
      } else {
        const errorData = await response.json().catch(() => null);
      }
    } catch (e) {
    }
  }

  function handleNotificationClick(notification: Notification) {
    
    // 先標記為已讀（現在所有通知狀態都是統一的大寫格式）
    if (notification.status === 'UNREAD') {
      markAsRead(notification.id);
    }

    // 現在所有通知資料都已經標準化，直接使用
    const notificationData = notification.data || notification.metadata || {};
    const roomId = notification.room_id;
    

    // 根據通知類型執行不同的導航邏輯（類型已經標準化為大寫）
    if (notification.type === 'MESSAGE' && roomId) {
      // 訊息通知：跳轉到聊天室並定位到特定訊息
      const messageId = notificationData.message_id;
      
      if (messageId) {
        // 帶上訊息 ID 參數，以便自動定位
        const targetUrl = `/app/room/${roomId}?message=${messageId}`;
        // console.log('[NotificationPanel] 跳轉到訊息:', targetUrl);
        goto(targetUrl);
        onClose?.(); // 關閉通知面板
      } else {
        // 沒有訊息 ID 時，只跳轉到聊天室
        const targetUrl = `/app/room/${roomId}`;
        // console.log('[NotificationPanel] 跳轉到聊天室:', targetUrl);
        goto(targetUrl);
        onClose?.(); // 關閉通知面板
      }
    } else if (notification.type === 'ROOM_INVITE' && roomId) {
      // 房間邀請：跳轉到房間
      const targetUrl = `/app/room/${roomId}`;
      // console.log('[NotificationPanel] 跳轉到邀請房間:', targetUrl);
      goto(targetUrl);
      onClose?.(); // 關閉通知面板
    } else if (notification.type === 'MENTION' && roomId) {
      // 提及通知：跳轉到聊天室並定位
      const messageId = notificationData.message_id;
      
      if (messageId) {
        const targetUrl = `/app/room/${roomId}?message=${messageId}`;
        // console.log('[NotificationPanel] 跳轉到提及訊息:', targetUrl);
        goto(targetUrl);
        onClose?.(); // 關閉通知面板
      } else {
        const targetUrl = `/app/room/${roomId}`;
        // console.log('[NotificationPanel] 跳轉到提及房間:', targetUrl);
        goto(targetUrl);
        onClose?.(); // 關閉通知面板
      }
    } else {
      // 系統通知或其他不需要跳轉的通知類型
      if (notification.type !== 'SYSTEM') {
        console.warn('[NotificationPanel] 無法處理的通知類型或缺少 room_id:', {
          type: notification.type,
          roomId,
          hasData: !!notificationData
        });
      }
      // 系統通知不需要特別處理，因為它們通常不需要跳轉
    }
  }

  function formatNotificationTime(createdAt: string): string {
    try {
      // 檢查輸入是否有效
      if (!createdAt || typeof createdAt !== 'string') {
        console.warn(`[NotificationPanel] 無效的時間輸入: ${createdAt}`);
        return '時間未知';
      }
      
      // console.log(`[NotificationPanel] 處理通知時間: ${createdAt}`);
      
      // 使用我們的安全時間處理
      let normalizedTime = createdAt;
      
      // 如果沒有時區標識，假設為 UTC 時間
      if (!createdAt.includes('+') && !createdAt.includes('-') && !createdAt.endsWith('Z')) {
        normalizedTime = createdAt + 'Z';
        // console.log(`[NotificationPanel] 修復時間格式: ${createdAt} -> ${normalizedTime}`);
      }
      
      const date = new Date(normalizedTime);
      
      // console.log(`[NotificationPanel] Date 對象: ${date.toString()}, getTime: ${date.getTime()}, isValid: ${!isNaN(date.getTime())}`);
      
      // 檢查日期是否有效
      if (isNaN(date.getTime())) {
        console.warn(`[NotificationPanel] 無效的時間格式: ${createdAt} (標準化: ${normalizedTime})`);
        return '時間未知';
      }
      
      const result = formatDistanceToNow(date, {
        addSuffix: true,
        locale: zhTW
      });
      
      // console.log(`[NotificationPanel] 格式化結果: ${result}`);
      return result;
    } catch (error) {
      console.error(`[NotificationPanel] 格式化通知時間失敗:`, error, '原始時間:', createdAt);
      return '時間未知';
    }
  }

  onMount(() => {
    // console.log('[NotificationPanel] onMount, isOpen:', isOpen);
    if (isOpen) {
      loadNotifications();
    }
  });

  $effect(() => {
    // console.log('[NotificationPanel] $effect 觸發, isOpen:', isOpen);
    if (isOpen) {
      loadNotifications();
      
      // 自動標記所有未讀通知為已讀 - 暫時註解掉以測試
      // setTimeout(() => {
      //   const unreadNotifications = notificationList.filter((n: Notification) => n.status === 'UNREAD');
      //   if (unreadNotifications.length > 0) {
      //     // 自動標記所有未讀通知為已讀
      //     markAllAsRead();
      //   }
      // }, 1000); // 延遲1秒，讓用戶看到通知
    }
  });
</script>

{#if isOpen}
  <!-- 背景遮罩 -->
  <div 
    class="fixed inset-0 bg-black bg-opacity-50 z-40"
    onclick={onClose}
    onkeydown={(e) => e.key === 'Escape' && onClose?.()}
    role="button"
    tabindex="0"
  ></div>

  <!-- 通知面板 -->
  <div class="fixed top-16 right-4 w-96 max-w-[calc(100vw-2rem)] bg-base-100 rounded-lg shadow-xl z-50 max-h-[80vh] flex flex-col border border-base-300">
    <!-- 標題列 -->
    <div class="flex items-center justify-between p-4 border-b border-base-200">
      <h3 class="text-lg font-semibold text-base-content">通知</h3>
      <div class="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          onclick={markAllAsRead}
          disabled={notificationList.length === 0}
        >
          全部已讀
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onclick={onClose}
        >
          ✕
        </Button>
      </div>
    </div>

    <!-- 通知列表 -->
    <div class="flex-1 overflow-y-auto">
      {#if loading}
        <div class="flex items-center justify-center p-8">
          <Loading size="lg" />
        </div>
      {:else if error}
        <div class="p-4 text-center text-error">
          <p>{error}</p>
          <Button
            variant="outline"
            size="sm"
            onclick={loadNotifications}
            class="mt-2"
          >
            重試
          </Button>
        </div>
      {:else if notificationList.length === 0}
        <div class="p-8 text-center text-base-content opacity-60">
          <div class="text-4xl mb-2">🔔</div>
          <p>暫無通知</p>
        </div>
      {:else}
        {#each notificationList as notification, index (notification.id + '_' + index)}
          <div
            class="p-4 border-b border-base-200 hover:bg-base-200 cursor-pointer transition-colors {notification.status === 'UNREAD' ? 'bg-blue-50 border-l-4 border-l-primary' : ''}"
            onclick={() => handleNotificationClick(notification)}
            onkeydown={(e) => e.key === 'Enter' && handleNotificationClick(notification)}
            role="button"
            tabindex="0"
          >
            <div class="flex items-start gap-3">
              <!-- 通知圖標 -->
              <div class="flex-shrink-0">
                <span class="text-xl">
                  {notificationTypeConfig[notification.type]?.icon || '🔔'}
                </span>
              </div>

              <!-- 通知內容 -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="px-2 py-1 text-xs rounded-full {notificationTypeConfig[notification.type]?.color || 'bg-gray-100 text-gray-800'}">
                    {notificationTypeConfig[notification.type]?.name || notification.type}
                  </span>
                  {#if notification.status === 'UNREAD'}
                    <span class="w-2 h-2 bg-primary rounded-full"></span>
                  {/if}
                </div>
                
                <h4 class="font-medium text-base-content text-sm mb-1">
                  {notification.title}
                </h4>
                
                <p class="text-base-content opacity-70 text-sm mb-2 line-clamp-2">
                  {notification.message}
                </p>
                
                <div class="flex items-center justify-between">
                  <span class="text-xs text-base-content opacity-50">
                    {formatNotificationTime(notification.created_at)}
                  </span>
                  
                  <Button
                    variant="ghost"
                    size="sm"
                    onclick={(e) => {
                      e.stopPropagation();
                      deleteNotification(notification.id);
                    }}
                    class="text-base-content opacity-40 hover:opacity-100 hover:text-error"
                  >
                    刪除
                  </Button>
                </div>
              </div>
            </div>
          </div>
        {/each}
      {/if}
    </div>
  </div>
{/if}

<style>
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
</style>