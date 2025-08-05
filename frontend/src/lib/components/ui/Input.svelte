<script lang="ts">
  interface Props {
    type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url';
    value?: string;
    placeholder?: string;
    disabled?: boolean;
    required?: boolean;
    readonly?: boolean;
    error?: string;
    label?: string;
    hint?: string;
    size?: 'sm' | 'md' | 'lg';
    fullWidth?: boolean;
    autofocus?: boolean;
    autocomplete?: AutoFill;
    id?: string;
    maxlength?: number;
    minlength?: number;
    pattern?: string;
    oninput?: (event: Event) => void;
    onchange?: (event: Event) => void;
    onfocus?: (event: FocusEvent) => void;
    onblur?: (event: FocusEvent) => void;
    onkeydown?: (event: KeyboardEvent) => void;
    onkeyup?: (event: KeyboardEvent) => void;
    onkeypress?: (event: KeyboardEvent) => void;
    [key: string]: any;
  }

  let { 
    type = 'text',
    value = $bindable(''),
    placeholder = '',
    disabled = false,
    required = false,
    readonly = false,
    error = '',
    label = '',
    hint = '',
    size = 'md',
    fullWidth = true,
    autofocus = false,
    autocomplete = '',
    id = '',
    maxlength = undefined,
    minlength = undefined,
    pattern = undefined,
    oninput = undefined,
    onchange = undefined,
    onfocus = undefined,
    onblur = undefined,
    onkeydown = undefined,
    onkeyup = undefined,
    onkeypress = undefined,
    ...restProps
  }: Props = $props();

  let inputElement: HTMLInputElement | undefined = $state();
  
  // 使用 autofocus 屬性
  $effect(() => {
    if (autofocus && inputElement) {
      inputElement.focus();
    }
  });
  
  let baseClasses = $derived('input transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary');
  
  let sizeClasses = $derived({
    sm: 'input-sm',
    md: 'input-md',
    lg: 'input-lg',
  });
  
  let classes = $derived([
    baseClasses,
    sizeClasses[size],
    fullWidth ? 'w-full' : '',
    error ? 'input-error' : 'input-bordered',
    disabled ? 'input-disabled' : '',
  ].filter(Boolean).join(' '));

  // 公開 focus 方法
  export function focus() {
    inputElement?.focus();
  }

  // 公開 blur 方法
  export function blur() {
    inputElement?.blur();
  }

  // 公開 select 方法
  export function select() {
    inputElement?.select();
  }

  // 生成穩定的 inputId，只在組件創建時生成一次
  let randomId = `input-${Math.random().toString(36).substr(2, 9)}`;
  let inputId = $derived(id || randomId);
</script>

<div class="form-control w-full">
  {#if label}
    <label class="label" for={inputId}>
      <span class="label-text font-medium">{label}</span>
      {#if required}
        <span class="label-text-alt text-error">*</span>
      {/if}
    </label>
  {/if}
  
  <input
    bind:this={inputElement}
    bind:value
    {type}
    {placeholder}
    {disabled}
    {required}
    {readonly}
    {autocomplete}
    {maxlength}
    {minlength}
    {pattern}
    class={classes}
    id={inputId}
    {oninput}
    {onchange}
    {onfocus}
    {onblur}
    {onkeydown}
    {onkeyup}
    {onkeypress}
    {...restProps}
  />
  
  {#if error}
    <div class="label">
      <span class="label-text-alt text-error">{error}</span>
    </div>
  {:else if hint}
    <div class="label">
      <span class="label-text-alt text-base-content opacity-70">{hint}</span>
    </div>
  {/if}
</div>

<style>
  .form-control :global(.input:focus) {
    box-shadow: 0 0 0 2px hsl(var(--primary) / 0.2);
  }
</style>