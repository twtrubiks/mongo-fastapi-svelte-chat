<script lang="ts">
  interface Props {
    size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
    type?: 'spinner' | 'dots' | 'ring' | 'ball';
    text?: string;
    fullscreen?: boolean;
    overlay?: boolean;
  }
  
  let {
    size = 'md',
    type = 'spinner',
    text = '',
    fullscreen = false,
    overlay = false
  }: Props = $props();
  
  let sizeClasses = $derived({
    xs: 'loading-xs',
    sm: 'loading-sm',
    md: 'loading-md',
    lg: 'loading-lg',
    xl: 'loading-xl',
  });
  
  let typeClasses = $derived({
    spinner: 'loading-spinner',
    dots: 'loading-dots',
    ring: 'loading-ring',
    ball: 'loading-ball',
  });
  
  let loadingClasses = $derived([
    'loading',
    typeClasses[type],
    sizeClasses[size],
  ].join(' '));
</script>

{#if fullscreen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-base-100">
    <div class="flex flex-col items-center space-y-4">
      <span class={loadingClasses}></span>
      {#if text}
        <p class="text-base-content opacity-70 text-sm">{text}</p>
      {/if}
    </div>
  </div>
{:else if overlay}
  <div class="absolute inset-0 z-10 flex items-center justify-center bg-base-100 opacity-80 backdrop-blur-sm">
    <div class="flex flex-col items-center space-y-4">
      <span class={loadingClasses}></span>
      {#if text}
        <p class="text-base-content opacity-70 text-sm">{text}</p>
      {/if}
    </div>
  </div>
{:else}
  <div class="flex items-center justify-center p-4">
    <div class="flex flex-col items-center space-y-2">
      <span class={loadingClasses}></span>
      {#if text}
        <p class="text-base-content opacity-70 text-sm">{text}</p>
      {/if}
    </div>
  </div>
{/if}

<style>
  .loading {
    @apply text-primary;
  }
</style>