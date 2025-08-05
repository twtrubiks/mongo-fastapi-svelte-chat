<script lang="ts">
  import { flip } from 'svelte/animate';
  import { fly, scale } from 'svelte/transition';
  import { notifications, unreadCount, notificationStore } from '$lib/stores/notification.svelte';
  import NotificationItem from './NotificationItem.svelte';

  interface Props {
    showMarkAllButton?: boolean;
    hideReadNotifications?: boolean;
    maxItems?: number;
  }
  
  let {
    showMarkAllButton = true,
    hideReadNotifications = false,
    maxItems = 50
  }: Props = $props();

  // 本地狀態
  let isMarkingAllRead = $state(false);
  let showReadToggle = $state(false);

  // 過濾通知
  // 創建本地的響應式變數
  let notificationList = $derived(notifications());
  let unreadCountValue = $derived(unreadCount());
  
  let filteredNotifications = $derived(
    notificationList
      .filter(notification => !hideReadNotifications || notification.status !== 'READ')
      .slice(0, maxItems)
  );

  // 處理標記所有為已讀
  async function handleMarkAllAsRead() {
    if (isMarkingAllRead || unreadCountValue === 0) {
      return;
    }

    isMarkingAllRead = true;

    try {
      await notificationStore.markAllAsRead();
      
      // 成功或失敗的處理已由 store 內部處理
    } catch (error) {
      // 錯誤處理已由 store 內部處理
    } finally {
      isMarkingAllRead = false;
    }
  }

  // 切換顯示已讀通知
  function toggleShowRead() {
    hideReadNotifications = !hideReadNotifications;
  }
</script>

<div class="notification-list">
  <!-- 標頭控制區 -->
  {#if showMarkAllButton || notificationList.length > 0}
    <div class="flex items-center justify-between mb-4 p-4 bg-base-100 rounded-lg border">
      <div class="flex items-center gap-3">
        <h2 class="font-semibold text-lg">通知</h2>
        {#if unreadCountValue > 0}
          <div class="badge badge-primary badge-sm">
            {unreadCountValue} 未讀
          </div>
        {/if}
      </div>

      <div class="flex items-center gap-2">
        <!-- 顯示/隱藏已讀通知切換 -->
        {#if notificationList.some(n => n.status === 'READ')}
          <button 
            class="btn btn-xs btn-ghost"
            onclick={toggleShowRead}
          >
            {hideReadNotifications ? '顯示已讀' : '隱藏已讀'}
          </button>
        {/if}

        <!-- 標記所有為已讀按鈕 -->
        {#if showMarkAllButton && unreadCountValue > 0}
          <button 
            class="btn btn-xs btn-primary"
            class:loading={isMarkingAllRead}
            disabled={isMarkingAllRead}
            onclick={handleMarkAllAsRead}
          >
            {#if isMarkingAllRead}
              處理中...
            {:else}
              全部已讀
            {/if}
          </button>
        {/if}
      </div>
    </div>
  {/if}

  <!-- 通知列表 -->
  {#if filteredNotifications.length > 0}
    <div class="space-y-3">
      {#each filteredNotifications as notification (notification.id)}
        <div
          animate:flip={{ duration: 300 }}
          in:fly={{ y: -20, duration: 300 }}
          out:scale={{ start: 0.95, opacity: 0, duration: 200 }}
        >
          <NotificationItem {notification} />
        </div>
      {/each}
    </div>

    <!-- 載入更多提示（如果有超過 maxItems 的通知） -->
    {#if notificationList.length > maxItems}
      <div class="text-center mt-6">
        <div class="text-sm text-gray-500">
          顯示 {maxItems} / {notificationList.length} 條通知
        </div>
        <button class="btn btn-ghost btn-xs mt-2">
          載入更多
        </button>
      </div>
    {/if}
  {:else if notificationList.length === 0}
    <!-- 空狀態 -->
    <div class="empty-state text-center py-12">
      <div class="text-6xl mb-4">🔔</div>
      <h3 class="text-lg font-semibold text-gray-600 mb-2">沒有通知</h3>
      <p class="text-sm text-gray-400">
        當有新的通知時，會在這裡顯示
      </p>
    </div>
  {:else}
    <!-- 所有通知都被隱藏 -->
    <div class="empty-state text-center py-8">
      <div class="text-4xl mb-3">✅</div>
      <h3 class="text-md font-semibold text-gray-600 mb-2">所有通知都已讀取</h3>
      <p class="text-sm text-gray-400">
        <button class="btn btn-ghost btn-xs" onclick={toggleShowRead}>
          點擊顯示已讀通知
        </button>
      </p>
    </div>
  {/if}

  <!-- 連接狀態指示器（可選） -->
  <div class="connection-status mt-6 text-center">
    <div class="text-xs text-gray-400">
      🟢 即時同步已啟用
    </div>
  </div>
</div>

<style>
  .notification-list {
    max-width: 600px;
    margin: 0 auto;
  }

  .empty-state {
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    border-radius: 1rem;
    border: 1px solid #e2e8f0;
  }

  /* 動畫優化 */
  .space-y-3 > * {
    transform-origin: center;
  }

  /* 連接狀態指示器樣式 */
  .connection-status {
    opacity: 0.7;
    transition: opacity 0.3s ease;
  }

  .connection-status:hover {
    opacity: 1;
  }

  /* 響應式設計 */
  @media (max-width: 640px) {
    .notification-list {
      max-width: 100%;
      padding: 0 1rem;
    }

    .flex.items-center.justify-between {
      flex-direction: column;
      align-items: stretch;
      gap: 1rem;
    }

    .flex.items-center.gap-2 {
      justify-content: center;
    }
  }

  /* 載入狀態樣式 */
  .loading {
    pointer-events: none;
  }

  /* 批量操作按鈕特殊樣式 */
  .btn-primary.loading::after {
    border-top-color: white;
  }
</style>