<script lang="ts">
  import { wsManager } from '$lib/websocket/manager';
  import { fade } from 'svelte/transition';
  
  interface Props {
    showWhenConnected?: boolean;
    position?: 'top' | 'bottom';
    compact?: boolean;
  }
  
  let {
    showWhenConnected = false,
    position = 'top',
    compact = false
  }: Props = $props();
  
  let connectionState = $state<'disconnected' | 'connecting' | 'connected'>('disconnected');
  let isReconnecting = $state(false);
  let reconnectAttempts = $state(0);
  let maxAttempts = $state(0);
  
  let statusCheckInterval: number | null = null;
  
  // 檢查連接狀態
  function checkConnectionStatus() {
    const ws = wsManager.getInstance();
    connectionState = ws.getConnectionState();
    
    const reconnectInfo = ws.getReconnectInfo();
    isReconnecting = reconnectInfo.isReconnecting;
    reconnectAttempts = reconnectInfo.attempts;
    maxAttempts = reconnectInfo.maxAttempts;
  }
  
  // 手動重連
  function handleManualReconnect() {
    wsManager.getInstance().manualReconnect().catch((error) => {
      console.error('Manual reconnect failed:', error);
    });
  }
  
  // 設置事件監聽器
  function setupEventListeners() {
    const ws = wsManager.getInstance();
    
    ws.on('connected', checkConnectionStatus);
    ws.on('disconnected', checkConnectionStatus);
    ws.on('reconnect_failed', checkConnectionStatus);
  }
  
  // 清理事件監聽器
  function cleanupEventListeners() {
    const ws = wsManager.getInstance();
    
    ws.off('connected', checkConnectionStatus);
    ws.off('disconnected', checkConnectionStatus);
    ws.off('reconnect_failed', checkConnectionStatus);
  }
  
  $effect(() => {
    checkConnectionStatus();
    setupEventListeners();
    
    // 定期檢查連接狀態
    statusCheckInterval = window.setInterval(checkConnectionStatus, 1000);
    
    return () => {
      cleanupEventListeners();
      if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
      }
    };
  });
  
  // 決定是否顯示狀態指示器
  let shouldShow = $derived(showWhenConnected || connectionState !== 'connected');
  
  // 獲取狀態描述
  let statusText = $derived(
    connectionState === 'connected' ? '已連接' :
    connectionState === 'connecting' ? '連接中...' :
    isReconnecting ? `重連中... (${reconnectAttempts}/${maxAttempts})` :
    '連接中斷'
  );
  
  // 獲取狀態類型
  let statusType = $derived(
    connectionState === 'connected' ? 'success' :
    (connectionState === 'connecting' || isReconnecting) ? 'warning' :
    'error'
  );
</script>

{#if shouldShow}
  <div 
    class="connection-status"
    class:compact
    class:top={position === 'top'}
    class:bottom={position === 'bottom'}
    class:success={statusType === 'success'}
    class:warning={statusType === 'warning'}
    class:error={statusType === 'error'}
    transition:fade={{ duration: 200 }}
  >
    <div class="status-content">
      <!-- 狀態圖標 -->
      <div class="status-icon">
        {#if statusType === 'success'}
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r="4"/>
          </svg>
        {:else if statusType === 'warning'}
          <svg class="w-4 h-4 animate-pulse" fill="currentColor" viewBox="0 0 20 20">
            <circle cx="10" cy="10" r="4"/>
          </svg>
        {:else}
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M6 18L18 6M6 6l12 12" />
          </svg>
        {/if}
      </div>
      
      <!-- 狀態文字 -->
      <span class="status-text">{statusText}</span>
      
      <!-- 重連按鈕 -->
      {#if connectionState === 'disconnected' && !isReconnecting}
        <button
          type="button"
          class="reconnect-button"
          onclick={handleManualReconnect}
          title="手動重新連接"
          aria-label="手動重新連接"
        >
          <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      {/if}
    </div>
  </div>
{/if}

<style>
  .connection-status {
    @apply fixed left-4 right-4 z-40;
    @apply bg-white dark:bg-gray-800 border rounded-lg shadow-lg;
    @apply px-3 py-2;
  }
  
  .connection-status.compact {
    @apply px-2 py-1;
  }
  
  .connection-status.top {
    @apply top-4;
  }
  
  .connection-status.bottom {
    @apply bottom-4;
  }
  
  .connection-status.success {
    @apply border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20;
  }
  
  .connection-status.warning {
    @apply border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20;
  }
  
  .connection-status.error {
    @apply border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20;
  }
  
  .status-content {
    @apply flex items-center space-x-2;
  }
  
  .status-icon {
    @apply flex-shrink-0;
  }
  
  .success .status-icon {
    @apply text-green-600 dark:text-green-400;
  }
  
  .warning .status-icon {
    @apply text-yellow-600 dark:text-yellow-400;
  }
  
  .error .status-icon {
    @apply text-red-600 dark:text-red-400;
  }
  
  .status-text {
    @apply text-sm font-medium flex-1;
  }
  
  .success .status-text {
    @apply text-green-800 dark:text-green-200;
  }
  
  .warning .status-text {
    @apply text-yellow-800 dark:text-yellow-200;
  }
  
  .error .status-text {
    @apply text-red-800 dark:text-red-200;
  }
  
  .compact .status-text {
    @apply text-xs;
  }
  
  .reconnect-button {
    @apply flex items-center justify-center w-6 h-6 rounded-full;
    @apply bg-red-100 hover:bg-red-200 dark:bg-red-800 dark:hover:bg-red-700;
    @apply text-red-600 dark:text-red-300;
    @apply transition-colors duration-200;
    @apply focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2;
  }
  
  .compact .reconnect-button {
    @apply w-5 h-5;
  }
  
  /* 響應式設計 */
  @media (min-width: 768px) {
    .connection-status {
      @apply left-auto right-4 w-auto min-w-max;
    }
  }
</style>