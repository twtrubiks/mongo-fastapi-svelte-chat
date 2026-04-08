<script lang="ts">
  interface Props {
    id?: string;
    value: string;
    placeholder?: string;
    disabled?: boolean;
    maxlength?: number;
    onkeydown?: (e: KeyboardEvent) => void;
  }

  let {
    id,
    value = $bindable(''),
    placeholder = '',
    disabled = false,
    maxlength,
    onkeydown
  }: Props = $props();

  let showPassword = $state(false);
</script>

<div class="relative">
  <input
    {id}
    type={showPassword ? 'text' : 'password'}
    {placeholder}
    class="input input-bordered w-full pr-12"
    bind:value
    {disabled}
    {maxlength}
    {onkeydown}
  />
  <button
    type="button"
    class="absolute inset-y-0 right-0 flex items-center pr-3"
    onclick={() => showPassword = !showPassword}
    {disabled}
    aria-label={showPassword ? '隱藏密碼' : '顯示密碼'}
  >
    {#if showPassword}
      <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L5.636 5.636m4.242 4.242L15.12 15.12m-4.242-4.242L5.636 5.636m9.484 9.484L15.12 15.12M9.878 9.878l4.242 4.242" />
      </svg>
    {:else}
      <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
      </svg>
    {/if}
  </button>
</div>
