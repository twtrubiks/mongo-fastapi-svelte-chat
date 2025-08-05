<script lang="ts">
  import { notificationStore } from '$lib/stores/notification.svelte';
  import type { Notification } from '$lib/stores/notification.svelte';
  import { goto } from '$app/navigation';

  interface Props {
    notification: Notification;
    showMarkReadButton?: boolean;
  }
  
  let { 
    notification,
    showMarkReadButton = true
  }: Props = $props();

  // 本地狀態管理
  let isMarkingRead = $state(false);

  // 處理通知點擊事件
  async function handleNotificationClick() {
    
    // 先標記為已讀（現在所有通知狀態都是統一的大寫格式）
    if (notification.status !== 'READ') {
      await handleMarkAsRead();
    }

    // 現在所有通知資料都已經標準化，直接使用
    const notificationData = notification.data || {};
    const roomId = notification.room_id;

    // 根據通知類型執行不同的導航邏輯（現在類型都是大寫）
    if (notification.type === 'MESSAGE' && roomId) {
      // 訊息通知：跳轉到聊天室並定位到特定訊息
      const messageId = notificationData['message_id'];
      
      if (messageId) {
        // 帶上訊息 ID 參數，以便自動定位
        const targetUrl = `/app/room/${roomId}?message=${messageId}`;
        goto(targetUrl);
      } else {
        // 沒有訊息 ID 時，只跳轉到聊天室
        const targetUrl = `/app/room/${roomId}`;
        goto(targetUrl);
      }
    } else if (notification.type === 'ROOM_INVITE' && roomId) {
      // 房間邀請：跳轉到房間
      const targetUrl = `/app/room/${roomId}`;
      goto(targetUrl);
    } else if (notification.type === 'MENTION' && roomId) {
      // 提及通知：跳轉到聊天室並定位
      const messageId = notificationData['message_id'];
      
      if (messageId) {
        const targetUrl = `/app/room/${roomId}?message=${messageId}`;
        goto(targetUrl);
      } else {
        const targetUrl = `/app/room/${roomId}`;
        goto(targetUrl);
      }
    }
  }

  // 處理標記已讀
  async function handleMarkAsRead() {
    if (isMarkingRead || notification.status === 'READ') {
      return;
    }

    isMarkingRead = true;

    try {
      // 標記為已讀
      await notificationStore.markAsRead(notification.id);
      
      // 成功或失敗的處理已由 store 內部處理
    } catch (error) {
      // 錯誤處理已由 store 內部處理
    } finally {
      isMarkingRead = false;
    }
  }

  // 格式化通知時間
  function formatTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (minutes < 1) return '剛剛';
    if (minutes < 60) return `${minutes}分鐘前`;
    if (hours < 24) return `${hours}小時前`;
    if (days < 7) return `${days}天前`;
    
    return date.toLocaleDateString('zh-TW');
  }

  // 獲取通知類型的顯示名稱
  function getTypeDisplayName(type: string): string {
    const typeMap = {
      'MESSAGE': '新訊息',
      'ROOM_INVITE': '房間邀請',
      'ROOM_JOIN': '加入房間',
      'ROOM_LEAVE': '離開房間',
      'SYSTEM': '系統通知',
      'MENTION': '提及'
    };
    return typeMap[type as keyof typeof typeMap] || type;
  }

  // 獲取通知類型的顏色
  function getTypeColor(type: string): string {
    const colorMap = {
      'MESSAGE': 'badge-primary',
      'ROOM_INVITE': 'badge-secondary',
      'ROOM_JOIN': 'badge-success',
      'ROOM_LEAVE': 'badge-warning',
      'SYSTEM': 'badge-info',
      'MENTION': 'badge-accent'
    };
    return colorMap[type as keyof typeof colorMap] || 'badge-neutral';
  }
</script>

<div 
  class="notification-item card card-compact {notification.status === 'READ' ? 'bg-white opacity-60' : 'bg-blue-50'} shadow-sm border transition-all duration-300 hover:shadow-md cursor-pointer"
  class:border-l-4={notification.status !== 'READ'}
  class:border-l-primary={notification.status !== 'READ'}
  onclick={handleNotificationClick}
  role="button"
  tabindex="0"
  onkeydown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleNotificationClick();
    }
  }}
>
  <div class="card-body">
    <!-- 通知標頭 -->
    <div class="flex items-start justify-between gap-3">
      <div class="flex-1 min-w-0">
        <!-- 標題與類型 -->
        <div class="flex items-center gap-2 mb-1">
          <h3 class="font-semibold text-sm truncate">
            {notification.title}
          </h3>
          <div class="badge badge-xs {getTypeColor(notification.type)}">
            {getTypeDisplayName(notification.type)}
          </div>
        </div>
        
        <!-- 訊息內容 -->
        <p class="text-sm text-gray-600 line-clamp-2">
          {notification.message}
        </p>
        
        <!-- 時間戳 -->
        <div class="text-xs text-gray-400 mt-2">
          {formatTime(notification.created_at)}
        </div>
      </div>

      <!-- 未讀指示器 -->
      {#if notification.status !== 'READ'}
        <div class="flex-shrink-0">
          <div class="w-2 h-2 bg-primary rounded-full"></div>
        </div>
      {/if}
    </div>

    <!-- 操作按鈕 -->
    {#if showMarkReadButton && notification.status !== 'READ'}
      <div class="card-actions justify-end mt-3">
        <button 
          class="btn btn-xs btn-ghost"
          class:loading={isMarkingRead}
          disabled={isMarkingRead}
          onclick={(e) => { e.stopPropagation(); handleMarkAsRead(); }}
        >
          {#if isMarkingRead}
            處理中...
          {:else}
            標記已讀
          {/if}
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  .notification-item {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .notification-item:hover {
    transform: translateY(-1px);
  }

  /* 未讀通知的背景色強化 */
  .notification-item:not(.opacity-60) {
    background-color: rgb(239 246 255); /* bg-blue-50 */
    border-left: 4px solid oklch(var(--p));
  }
  
  /* 已讀狀態的視覺處理 */
  .notification-item.opacity-60 {
    background: #fafafa;
  }

  /* 文本截斷樣式 */
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* 未讀通知的左邊框動畫 */
  .border-l-4 {
    border-left-width: 4px;
  }

  .border-l-primary {
    border-left-color: oklch(var(--p));
  }

  /* 加載動畫 */
  .loading {
    pointer-events: none;
  }

  .loading::after {
    content: "";
    position: absolute;
    width: 16px;
    height: 16px;
    margin: auto;
    border: 2px solid transparent;
    border-top-color: currentColor;
    border-radius: 50%;
    animation: button-loading-spinner 1s ease infinite;
  }

  @keyframes button-loading-spinner {
    from {
      transform: rotate(0turn);
    }
    to {
      transform: rotate(1turn);
    }
  }
</style>