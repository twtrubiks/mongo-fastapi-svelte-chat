<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    padding?: 'none' | 'sm' | 'md' | 'lg';
    shadow?: 'none' | 'sm' | 'md' | 'lg';
    border?: boolean;
    hoverable?: boolean;
    clickable?: boolean;
    onclick?: (event: MouseEvent) => void;
    onkeydown?: (event: KeyboardEvent) => void;
    onmouseenter?: (event: MouseEvent) => void;
    onmouseleave?: (event: MouseEvent) => void;
    children?: Snippet;
    header?: Snippet;
    actions?: Snippet;
    footer?: Snippet;
    [key: string]: any;
  }

  let { 
    padding = 'md',
    shadow = 'md',
    border = true,
    hoverable = false,
    clickable = false,
    onclick = undefined,
    onkeydown = undefined,
    onmouseenter = undefined,
    onmouseleave = undefined,
    children,
    header,
    actions,
    footer,
    ...restProps
  }: Props = $props();

  let paddingClasses = $derived({
    none: '',
    sm: 'p-3',
    md: 'p-4',
    lg: 'p-6',
  });

  let shadowClasses = $derived({
    none: '',
    sm: 'shadow-sm',
    md: 'shadow-md',
    lg: 'shadow-lg',
  });

  let classes = $derived([
    'card bg-base-100',
    paddingClasses[padding],
    shadowClasses[shadow],
    border ? 'border border-base-200' : '',
    hoverable ? 'hover:shadow-lg transition-shadow' : '',
    clickable ? 'cursor-pointer hover:bg-base-50' : '',
  ].filter(Boolean).join(' '));
</script>

<div 
  class={classes}
  {onclick}
  {onkeydown}
  {onmouseenter}
  {onmouseleave}
  role={clickable ? 'button' : undefined}
  tabindex={clickable ? 0 : undefined}
  {...restProps}
>
  <!-- 卡片標題區域 -->
  {#if header}
    <div class="card-header mb-4 pb-3 border-b border-base-200">
      {@render header()}
    </div>
  {/if}

  <!-- 卡片主要內容 -->
  <div class="card-body">
    {@render children?.()}
  </div>

  <!-- 卡片操作區域 -->
  {#if actions}
    <div class="card-actions mt-4 pt-3 border-t border-base-200 flex justify-end space-x-2">
      {@render actions()}
    </div>
  {/if}

  <!-- 卡片底部區域 -->
  {#if footer}
    <div class="card-footer mt-4 pt-3 border-t border-base-200">
      {@render footer()}
    </div>
  {/if}
</div>

<style>
  .card {
    @apply rounded-lg;
  }

  .card-header {
    @apply text-lg font-semibold text-base-content;
  }

  .card-body {
    @apply text-base-content;
  }

  .card-actions {
    @apply text-sm;
  }

  .card-footer {
    @apply text-sm text-base-content opacity-70;
  }
</style>