<script lang="ts">
  import type { Snippet } from 'svelte';

  let { 
    variant = 'primary',
    size = 'md',
    disabled = false,
    loading = false,
    type = 'button',
    href = undefined,
    fullWidth = false,
    onclick = undefined,
    children,
    ...restProps
  } = $props<{
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    loading?: boolean;
    type?: 'button' | 'submit' | 'reset';
    href?: string;
    fullWidth?: boolean;
    onclick?: (event: MouseEvent) => void;
    children?: Snippet;
    [key: string]: any;
  }>();

  let baseClasses = 'btn font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2';
  
  let variantClasses: Record<string, string> = {
    primary: 'btn-primary',
    secondary: 'btn-secondary',
    ghost: 'btn-ghost',
    danger: 'btn-error',
  };
  
  let sizeClasses: Record<string, string> = {
    sm: 'btn-sm',
    md: 'btn-md',
    lg: 'btn-lg',
  };
  
  let classes = $derived([
    baseClasses,
    variantClasses[variant],
    sizeClasses[size],
    fullWidth ? 'w-full' : '',
    disabled || loading ? 'btn-disabled' : '',
    loading ? 'loading' : '',
  ].filter(Boolean).join(' '));
</script>

{#if href}
  <a
    {href}
    class={classes}
    class:btn-disabled={disabled}
    aria-disabled={disabled}
    {onclick}
    {...restProps}
  >
    {#if loading}
      <span class="loading loading-spinner loading-sm mr-2"></span>
    {/if}
    {@render children?.()}
  </a>
{:else}
  <button
    {type}
    class={classes}
    {disabled}
    aria-disabled={disabled || loading}
    {onclick}
    {...restProps}
  >
    {#if loading}
      <span class="loading loading-spinner loading-sm mr-2"></span>
    {/if}
    {@render children?.()}
  </button>
{/if}