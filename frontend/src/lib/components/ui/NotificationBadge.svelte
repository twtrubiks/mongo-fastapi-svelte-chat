<script lang="ts">
  import { unreadCount, hasUnreadNotifications, notifications } from '$lib/stores/notification.svelte';

  interface Props {
    showZero?: boolean;
    maxCount?: number;
    size?: 'sm' | 'md' | 'lg';
    position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  }

  let { 
    showZero = false, 
    maxCount = 99, 
    size = 'md', 
    position = 'top-right' 
  }: Props = $props();

  // 大小樣式
  const sizeClasses = {
    sm: 'w-4 h-4 text-xs',
    md: 'w-5 h-5 text-xs',
    lg: 'w-6 h-6 text-sm'
  };

  // 位置樣式
  const positionClasses = {
    'top-right': '-top-1 -right-1',
    'top-left': '-top-1 -left-1',
    'bottom-right': '-bottom-1 -right-1',
    'bottom-left': '-bottom-1 -left-1'
  };

  // 直接基於 notifications() $state 計算，確保響應式更新
  let safeUnreadCount = $derived.by(() => {
    const notificationList = notifications();
    return notificationList.filter(n => n.status === 'UNREAD').length || 0;
  });
  let displayCount = $derived(safeUnreadCount > maxCount ? `${maxCount}+` : safeUnreadCount.toString());
  let shouldShow = $derived(safeUnreadCount > 0 || showZero);
  
</script>

{#if shouldShow}
  <span
    class="absolute {positionClasses[position]} {sizeClasses[size]} bg-red-500 text-white rounded-full flex items-center justify-center font-bold animate-pulse"
    aria-label="未讀通知數量"
  >
    {displayCount}
  </span>
{/if}

<style>
  .animate-pulse {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }

  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.7;
    }
  }
</style>