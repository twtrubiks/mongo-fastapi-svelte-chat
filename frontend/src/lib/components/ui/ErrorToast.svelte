<script lang="ts">
  import { fade, fly } from 'svelte/transition';
  
  interface Props {
    show?: boolean;
    title?: string;
    message?: string;
    type?: 'error' | 'warning' | 'info';
    action?: { label: string; handler: () => void } | null;
    autoHide?: boolean;
    duration?: number;
    onHide?: () => void;
  }

  let { 
    show = $bindable(false),
    title = '錯誤',
    message = '',
    type = 'error',
    action = null,
    autoHide = true,
    duration = 5000,
    onHide = undefined
  }: Props = $props();

  let timeoutId: number | null = $state(null);

  // 當 show 為 true 時，設置自動隱藏
  $effect(() => {
    if (show && autoHide) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      timeoutId = window.setTimeout(() => {
        hide();
      }, duration);
    }
  });

  function hide() {
    show = false;
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    onHide?.();
  }

  function handleAction() {
    if (action?.handler) {
      action.handler();
    }
  }

  // 清理計時器
  function onDestroy() {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
  }
</script>

{#if show}
  <div 
    class="error-toast-overlay"
    transition:fade={{ duration: 200 }}
    onclick={(e) => { if (e.target === e.currentTarget) hide(); }}
    onkeydown={(e) => { if (e.key === 'Escape') hide(); }}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
  >
    <div 
      class="error-toast"
      class:error={type === 'error'}
      class:warning={type === 'warning'}
      class:info={type === 'info'}
      transition:fly={{ y: -50, duration: 300 }}
    >
      <!-- 圖標 -->
      <div class="toast-icon">
        {#if type === 'error'}
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        {:else if type === 'warning'}
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        {:else}
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        {/if}
      </div>
      
      <!-- 內容 -->
      <div class="toast-content">
        <h4 class="toast-title">{title}</h4>
        <p class="toast-message">{message}</p>
      </div>
      
      <!-- 動作按鈕 -->
      <div class="toast-actions">
        {#if action}
          <button
            type="button"
            class="action-button"
            onclick={handleAction}
          >
            {action.label}
          </button>
        {/if}
        
        <button
          type="button"
          class="close-button"
          onclick={hide}
          aria-label="關閉"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .error-toast-overlay {
    @apply fixed inset-0 z-50 flex items-start justify-center pt-4 px-4;
    @apply pointer-events-auto;
  }
  
  .error-toast {
    @apply flex items-start space-x-3 max-w-md w-full;
    @apply bg-white dark:bg-gray-800 rounded-lg shadow-lg border;
    @apply p-4 relative;
    @apply pointer-events-auto;
  }
  
  .error-toast.error {
    @apply border-red-200 dark:border-red-800;
  }
  
  .error-toast.warning {
    @apply border-yellow-200 dark:border-yellow-800;
  }
  
  .error-toast.info {
    @apply border-blue-200 dark:border-blue-800;
  }
  
  .toast-icon {
    @apply flex-shrink-0;
  }
  
  .error .toast-icon {
    @apply text-red-600 dark:text-red-400;
  }
  
  .warning .toast-icon {
    @apply text-yellow-600 dark:text-yellow-400;
  }
  
  .info .toast-icon {
    @apply text-blue-600 dark:text-blue-400;
  }
  
  .toast-content {
    @apply flex-1 min-w-0;
  }
  
  .toast-title {
    @apply text-sm font-medium text-gray-900 dark:text-gray-100;
    @apply mb-1;
  }
  
  .toast-message {
    @apply text-sm text-gray-700 dark:text-gray-300;
    @apply break-words;
  }
  
  .toast-actions {
    @apply flex items-start space-x-2 flex-shrink-0;
  }
  
  .action-button {
    @apply inline-flex items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded;
    @apply text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500;
    @apply transition-colors duration-200;
  }
  
  .error .action-button {
    @apply bg-red-600 hover:bg-red-700 focus:ring-red-500;
  }
  
  .warning .action-button {
    @apply bg-yellow-600 hover:bg-yellow-700 focus:ring-yellow-500;
  }
  
  .close-button {
    @apply flex items-center justify-center w-6 h-6 rounded-full;
    @apply text-gray-400 hover:text-gray-600 hover:bg-gray-100;
    @apply dark:text-gray-500 dark:hover:text-gray-300 dark:hover:bg-gray-700;
    @apply transition-colors duration-200;
    @apply focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500;
  }
</style>