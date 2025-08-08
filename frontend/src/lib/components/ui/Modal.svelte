<script lang="ts">
  import type { Snippet } from 'svelte';

  let { 
    open = $bindable(),
    title = '',
    closeable = true,
    size = 'md',
    backdrop = true,
    onClose = undefined,
    children,
    actions
  } = $props<{
    open?: boolean;
    title?: string;
    closeable?: boolean;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    backdrop?: boolean;
    onClose?: () => void;
    children?: Snippet;
    actions?: Snippet;
  }>();
  
  let sizeClasses: Record<string, string> = {
    sm: 'modal-box w-96 max-w-sm',
    md: 'modal-box w-11/12 max-w-md',
    lg: 'modal-box w-11/12 max-w-2xl',
    xl: 'modal-box w-11/12 max-w-5xl',
  };
  
  function handleClose() {
    if (closeable) {
      open = false;
      if (onClose) {
        onClose();
      }
    }
  }
  
  function handleBackdropClick(event: MouseEvent) {
    if (backdrop && event.target === event.currentTarget) {
      handleClose();
    }
  }
  
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && closeable) {
      handleClose();
    }
  }
  
  // 防止背景滾動
  $effect(() => {
    if (typeof document !== 'undefined') {
      if (open) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    }
  });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div 
    class="modal modal-open"
    class:modal-backdrop={backdrop}
    onclick={handleBackdropClick}
    onkeydown={handleKeydown}
    role="dialog"
    aria-modal="true"
    aria-labelledby={title ? 'modal-title' : undefined}
    tabindex="-1"
  >
    <div class={sizeClasses[size]} class:relative={true}>
      {#if closeable}
        <button
          class="btn btn-sm btn-circle absolute right-2 top-2 z-10 bg-base-100 hover:bg-base-200 active:bg-base-300 border border-base-300 min-h-[44px] min-w-[44px] sm:min-h-[32px] sm:min-w-[32px] shadow-sm"
          onclick={handleClose}
          aria-label="關閉"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      {/if}
      
      {#if title}
        <h2 id="modal-title" class="text-lg font-semibold mb-4 pr-8">{title}</h2>
      {/if}
      
      <div class="modal-content">
        {@render children?.()}
      </div>
      
      {#if actions}
        <div class="modal-action">
          {@render actions()}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .modal {
    @apply z-50;
  }
  
  .modal-backdrop {
    background-color: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(2px);
  }
  
  .modal-box {
    @apply shadow-xl;
    animation: modalOpen 0.2s ease-out;
  }
  
  @keyframes modalOpen {
    from {
      opacity: 0;
      transform: scale(0.95) translateY(-10px);
    }
    to {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }
  
  .modal-content {
    @apply min-h-0;
  }
  
  .modal-action {
    @apply flex justify-end space-x-2 mt-6 pt-4 border-t border-base-200;
  }
</style>