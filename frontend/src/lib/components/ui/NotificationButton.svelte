<script lang="ts">
  import { notificationStore } from '$lib/stores/notification.svelte';
  import { apiClient } from '$lib/api/client';
  import Button from './Button.svelte';
  import NotificationBadge from './NotificationBadge.svelte';
  import NotificationPanel from './NotificationPanel.svelte';

  let isOpen = $state(false);
  let buttonRef: HTMLButtonElement = $state(null!);
  let wrapperRef: HTMLDivElement = $state(null!);

  // 創建本地的響應式變數，使用 $derived.by 確保正確追蹤依賴
  let unreadCountValue = $derived.by(() => {
    // 直接訪問 notificationStore 的 notifications 來確保響應式追蹤
    const notifications = notificationStore.notifications;
    return notifications.filter(n => n.status === 'UNREAD').length;
  });

  function togglePanel(e: MouseEvent) {
    e.stopPropagation();
    isOpen = !isOpen;
  }

  function closePanel() {
    isOpen = false;
  }

  function handleClickOutside(event: MouseEvent) {
    if (wrapperRef && !wrapperRef.contains(event.target as Node) && isOpen) {
      closePanel();
    }
  }

  $effect(() => {
    // WebSocket 連接由 wsManager 統一管理，不需要重複初始化
    
    // 載入通知統計
    (async () => {
      try {
        const stats = await apiClient.notifications.stats();

        // 檢查本地通知列表中的實際未讀數量
        try {
          const { notifications } = await import('$lib/stores/notification.svelte');
          const currentNotifications = notifications();
          const actualUnreadCount = currentNotifications.filter(n => n.status === 'UNREAD').length;
          const serverUnread = stats.unread ?? 0;

          // 如果本地實際未讀數量與伺服器不符，優先使用本地實際數量
          if (actualUnreadCount !== serverUnread) {
            return;
          }
        } catch (error) {
          console.warn('[NotificationButton] 檢查本地實際未讀數量失敗:', error);
        }

        notificationStore.updateStats(stats);
      } catch (error) {
        console.error('[NotificationButton] 載入統計時發生錯誤:', error);
      }
    })();
    
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape' && isOpen) closePanel();
    }

    document.addEventListener('click', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('click', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  });
</script>

<div class="relative z-50" bind:this={wrapperRef}>
  <Button
    bind:ref={buttonRef}
    variant="ghost"
    size="md"
    onclick={togglePanel}
    class="relative p-2 hover:bg-base-200 rounded-full transition-colors btn-circle"
    aria-label="通知 {unreadCountValue > 0 ? `(${unreadCountValue} 則未讀)` : ''}"
  >
    <!-- 通知圖標 -->
    <svg
      class="w-5 h-5 text-base-content opacity-70 hover:opacity-100 transition-opacity"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
      ></path>
    </svg>

    <!-- 未讀數量徽章 -->
    <NotificationBadge />
  </Button>

  <!-- 通知面板 -->
  <NotificationPanel 
    {isOpen} 
    onClose={closePanel}
  />
</div>