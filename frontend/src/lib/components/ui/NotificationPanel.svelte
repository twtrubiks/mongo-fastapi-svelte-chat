<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { fly } from 'svelte/transition';
  import { notifications, notificationStore } from '$lib/stores/notification.svelte';
  import { apiClient } from '$lib/api/client';
  import type { Notification } from '$lib/types';
  import { formatDistanceToNow } from 'date-fns';
  import { zhTW } from 'date-fns/locale';
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
    SYSTEM: { name: '系統通知', icon: '⚙️', color: 'bg-purple-100 text-purple-800' },
  };

  async function loadNotifications() {
    loading = true;
    error = null;

    try {
      const data = await apiClient.notifications.list();
      notificationStore.setNotifications(data.notifications || []);
    } catch (e) {
      error = e instanceof Error ? e.message : '載入通知時發生錯誤';
    } finally {
      loading = false;
    }
  }

  async function markAsRead(notificationId: string) {
    try {
      await apiClient.notifications.markAsRead(notificationId);
      notificationStore.markAsRead(notificationId);
    } catch {
      // 靜默處理：標記已讀失敗不影響主流程
    }
  }

  async function markAllAsRead() {
    try {
      // 樂觀更新：立即更新本地狀態
      notificationStore.markAllAsRead();

      // 發送 API 請求
      await apiClient.notifications.markAllAsRead();
    } catch {
      // TODO: 如果 API 失敗，應該回滾樂觀更新
    }
  }

  async function clearAllNotifications() {
    try {
      notificationStore.clearAll();
      await apiClient.notifications.clearAll();
    } catch {
      await loadNotifications();
    }
  }

  async function deleteNotification(notificationId: string) {
    try {
      await apiClient.notifications.delete(notificationId);
      notificationStore.removeNotification(notificationId);
    } catch {
      // 靜默處理：刪除通知失敗不影響主流程
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
      const messageId = notificationData['message_id'];

      if (messageId) {
        // 帶上訊息 ID 參數，以便自動定位
        const targetUrl = `/app/room/${roomId}?message=${messageId}`;
        goto(targetUrl);
        onClose?.(); // 關閉通知面板
      } else {
        // 沒有訊息 ID 時，只跳轉到聊天室
        const targetUrl = `/app/room/${roomId}`;
        goto(targetUrl);
        onClose?.(); // 關閉通知面板
      }
    } else {
      // 系統通知不需要跳轉
    }
  }

  function formatNotificationTime(createdAt: string): string {
    try {
      // 檢查輸入是否有效
      if (!createdAt || typeof createdAt !== 'string') {
        console.warn(`[NotificationPanel] 無效的時間輸入: ${createdAt}`);
        return '時間未知';
      }
      
      // 使用我們的安全時間處理
      let normalizedTime = createdAt;
      
      // 如果沒有時區標識，假設為 UTC 時間
      if (!createdAt.includes('+') && !createdAt.includes('-') && !createdAt.endsWith('Z')) {
        normalizedTime = createdAt + 'Z';
      }
      
      const date = new Date(normalizedTime);
      
      // 檢查日期是否有效
      if (isNaN(date.getTime())) {
        console.warn(`[NotificationPanel] 無效的時間格式: ${createdAt} (標準化: ${normalizedTime})`);
        return '時間未知';
      }
      
      const result = formatDistanceToNow(date, {
        addSuffix: true,
        locale: zhTW
      });
      
      return result;
    } catch (error) {
      console.error(`[NotificationPanel] 格式化通知時間失敗:`, error, '原始時間:', createdAt);
      return '時間未知';
    }
  }

  onMount(() => {
    if (isOpen) {
      loadNotifications();
    }
  });

  $effect(() => {
    if (isOpen) {
      loadNotifications();
    }
  });
</script>

{#if isOpen}
  <!-- 通知面板（dropdown 下拉式） -->
  <div
    class="absolute top-full left-0 mt-2 w-96 max-w-[calc(100vw-2rem)] bg-base-100 rounded-lg shadow-xl z-50 max-h-[calc(100vh-5rem)] flex flex-col border border-base-300"
    transition:fly={{ y: -8, duration: 150 }}
    role="dialog"
    aria-label="通知面板"
  >
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
          onclick={clearAllNotifications}
          disabled={notificationList.length === 0}
        >
          清除全部
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onclick={() => onClose?.()}
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