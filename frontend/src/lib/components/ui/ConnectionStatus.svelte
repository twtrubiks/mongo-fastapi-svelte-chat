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
  <!-- 使用 DaisyUI 的 toast 和 alert 組件 -->
  <div 
    class="fixed z-30 {position === 'top' ? 'top-4' : 'bottom-4'} right-4"
    transition:fade={{ duration: 200 }}
  >
    <div 
      class="alert shadow-lg"
      class:alert-success={statusType === 'success'}
      class:alert-warning={statusType === 'warning'}
      class:alert-error={statusType === 'error'}
      class:alert-sm={compact}
      role="alert"
      aria-live="polite"
    >
      <div class="flex items-center gap-2">
        <!-- 狀態圖標 -->
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
        
        <!-- 狀態文字 -->
        <span class="text-sm font-medium">{statusText}</span>
        
        <!-- 重連按鈕 -->
        {#if connectionState === 'disconnected' && !isReconnecting}
          <button
            type="button"
            class="btn btn-ghost btn-xs btn-circle"
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
  </div>
{/if}

<style>
  /* 使用 DaisyUI 的 toast 和 alert 組件，只需要少量自定義樣式 */
  .alert-sm {
    @apply py-2 px-3 min-h-0;
  }
  
  .alert-sm .text-sm {
    @apply text-xs;
  }
  
  /* 響應式設計 - 移動端更緊湊 */
  @media (max-width: 767px) {
    .fixed {
      @apply left-2 right-2;
    }
    
    .alert {
      @apply text-xs;
    }
    
    .alert svg {
      @apply w-3 h-3;
    }
  }
</style>