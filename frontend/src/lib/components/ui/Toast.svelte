<script lang="ts">
  import { onMount } from 'svelte';
  import { fly, scale, fade } from 'svelte/transition';
  import { bounceOut, elasticOut } from 'svelte/easing';
  
  let { 
    type = 'info',
    message = '',
    duration = 4000,
    dismissible = true,
    show = $bindable(),
    onClose = undefined
  } = $props<{
    type?: 'success' | 'error' | 'warning' | 'info';
    message?: string;
    duration?: number;
    dismissible?: boolean;
    show?: boolean;
    onClose?: () => void;
  }>();
  
  let timeoutId: number;
  
  let typeClasses: Record<string, string> = {
    success: 'alert-success',
    error: 'alert-error',
    warning: 'alert-warning',
    info: 'alert-info',
  };
  
  let iconSvg: Record<string, string> = {
    success: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
    </svg>`,
    error: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
    </svg>`,
    warning: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>`,
    info: `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>`,
  };
  
  function handleClose() {
    show = false;
    if (onClose) {
      onClose();
    }
  }
  
  function startTimer() {
    if (duration > 0) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        handleClose();
      }, duration);
    }
  }
  
  function stopTimer() {
    clearTimeout(timeoutId);
  }
  
  onMount(() => {
    if (show) {
      startTimer();
    }
    
    return () => {
      clearTimeout(timeoutId);
    };
  });
  
  $effect(() => {
    if (show) {
      startTimer();
    } else {
      stopTimer();
    }
  });
</script>

{#if show}
  <div
    class="fixed top-4 right-4 left-4 md:left-auto z-[99999] max-w-sm md:max-w-sm mx-auto md:mx-0"
    role="alert"
    aria-live="polite"
    onmouseenter={stopTimer}
    onmouseleave={startTimer}
    in:fly={{ x: 400, duration: 500, easing: elasticOut }}
    out:fly={{ x: 400, duration: 300, easing: bounceOut }}
  >
    <div 
      class="alert {typeClasses[type]} shadow-lg"
      in:scale={{ duration: 300, delay: 200, easing: elasticOut }}
      out:scale={{ duration: 200 }}
    >
      <div class="flex items-start space-x-3">
        <div 
          class="flex-shrink-0"
          in:scale={{ duration: 400, delay: 400, easing: bounceOut }}
        >
          {@html iconSvg[type]}
        </div>
        
        <div 
          class="flex-1 min-w-0"
          in:fade={{ duration: 300, delay: 300 }}
        >
          <p class="text-sm font-medium break-words">
            {message}
          </p>
        </div>
        
        {#if dismissible}
          <button
            class="btn btn-sm btn-circle btn-ghost ml-2 hover:rotate-90 transition-transform duration-200"
            onclick={handleClose}
            aria-label="關閉通知"
            in:scale={{ duration: 300, delay: 500, easing: elasticOut }}
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .alert {
    @apply transition-all duration-200;
  }
  
  .alert:hover {
    @apply shadow-xl;
  }
</style>