<script lang="ts">
  import { scale, fly } from 'svelte/transition';
  import { elasticOut } from 'svelte/easing';
  
  interface Props {
    count?: number;
    maxDisplay?: number;
    size?: 'sm' | 'md' | 'lg';
    variant?: 'default' | 'accent' | 'error';
    animate?: boolean;
    pulse?: boolean;
  }

  let {
    count = 0,
    maxDisplay = 99,
    size = 'md',
    variant = 'default',
    animate = true,
    pulse = false
  }: Props = $props();

  // 響應式計算顯示文字
  let displayText = $derived(count > maxDisplay ? `${maxDisplay}+` : count.toString());
  let hasCount = $derived(count > 0);

  // 樣式映射
  let sizeClasses = $derived({
    sm: 'text-xs px-1 py-0.5 min-w-4 h-4',
    md: 'text-xs px-1.5 py-0.5 min-w-5 h-5',
    lg: 'text-sm px-2 py-1 min-w-6 h-6',
  });

  let variantClasses = $derived({
    default: 'bg-primary text-primary-content',
    accent: 'bg-accent text-accent-content',
    error: 'bg-error text-error-content',
  });

  let classes = $derived([
    'badge rounded-full font-semibold flex items-center justify-center',
    sizeClasses[size],
    variantClasses[variant],
    pulse ? 'animate-pulse' : '',
  ].filter(Boolean).join(' '));
</script>

{#if hasCount}
  <span 
    class="{classes} {hasCount ? 'shadow-lg' : ''} {variant === 'default' && hasCount ? 'shadow-primary-30' : ''} {variant === 'accent' && hasCount ? 'shadow-accent-30' : ''} {variant === 'error' && hasCount ? 'shadow-error-30' : ''}"
    aria-label={`${count} 個未讀`}
    title={`${count} 個未讀項目`}
    in:scale={{ 
      duration: animate ? 300 : 0, 
      easing: elasticOut 
    }}
    out:scale={{ 
      duration: animate ? 200 : 0 
    }}
  >
    {displayText}
  </span>
{/if}

<style>
  .badge {
    @apply transition-all duration-200;
  }
  
  .badge:hover {
    @apply scale-110;
  }
  
  /* 添加脈衝動畫 */
  .animate-pulse {
    animation: pulse-soft 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  
  @keyframes pulse-soft {
    0%, 100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.8;
      transform: scale(1.05);
    }
  }
  
  /* 陰影動畫 */
  .shadow-primary-30 {
    box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3), 0 2px 4px -1px rgba(59, 130, 246, 0.15);
  }
  
  .shadow-accent-30 {
    box-shadow: 0 4px 6px -1px rgba(168, 85, 247, 0.3), 0 2px 4px -1px rgba(168, 85, 247, 0.15);
  }
  
  .shadow-error-30 {
    box-shadow: 0 4px 6px -1px rgba(239, 68, 68, 0.3), 0 2px 4px -1px rgba(239, 68, 68, 0.15);
  }
</style>