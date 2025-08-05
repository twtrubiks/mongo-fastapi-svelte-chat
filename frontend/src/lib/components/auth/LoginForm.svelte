<script lang="ts">
  import { authStore } from '$lib/stores';
  import { validateUsername, formatAuthError } from '$lib/utils';
  import { Button, Input } from '$lib/components/ui';
  import type { LoginData } from '$lib/types';
  
  interface Props {
    onSuccess?: (data: { message: string }) => void;
    onError?: (data: { message: string }) => void;
    onSwitchToRegister?: () => void;
  }
  
  let {
    onSuccess = undefined,
    onError = undefined,
    onSwitchToRegister = undefined
  }: Props = $props();
  
  let credentials = $state<LoginData>({
    username: '',
    password: '',
  });
  
  let errors: Record<string, string> = $state({});
  let isSubmitting = $state(false);
  let submitError = $state('');
  
  function validateForm(): boolean {
    errors = {};
    
    if (!credentials.username.trim()) {
      errors.username = '請輸入用戶名';
    } else {
      const usernameValidation = validateUsername(credentials.username);
      if (!usernameValidation.isValid) {
        errors.username = usernameValidation.errors[0];
      }
    }
    
    if (!credentials.password.trim()) {
      errors.password = '請輸入密碼';
    } else if (credentials.password.length < 6) {
      errors.password = '密碼至少需要 6 個字符';
    }
    
    return Object.keys(errors).length === 0;
  }
  
  async function handleSubmit() {
    if (!validateForm()) return;
    
    isSubmitting = true;
    submitError = '';
    
    try {
      await authStore.login(credentials);
      onSuccess?.({ message: '登入成功！' });
    } catch (error) {
      submitError = formatAuthError(error);
      onError?.({ message: submitError });
    } finally {
      isSubmitting = false;
    }
  }
  
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !isSubmitting) {
      handleSubmit();
    }
  }
</script>

<form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-4">
  <div class="text-center mb-6">
    <h1 class="text-2xl font-bold text-base-content">歡迎回來</h1>
    <p class="text-base-content opacity-60 mt-2">請輸入您的帳號資訊</p>
  </div>
  
  <Input
    label="用戶名"
    type="text"
    bind:value={credentials.username}
    placeholder="請輸入用戶名"
    error={errors.username}
    required
    autocomplete="username"
    onkeydown={handleKeydown}
  />
  
  <Input
    label="密碼"
    type="password"
    bind:value={credentials.password}
    placeholder="請輸入密碼"
    error={errors.password}
    required
    autocomplete="current-password"
    onkeydown={handleKeydown}
  />
  
  {#if submitError}
    <div class="alert alert-error">
      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
      <span>{submitError}</span>
    </div>
  {/if}
  
  <Button
    type="submit"
    variant="primary"
    size="lg"
    fullWidth
    loading={isSubmitting}
    disabled={isSubmitting}
  >
    {isSubmitting ? '登入中...' : '登入'}
  </Button>
  
  <div class="text-center">
    <p class="text-base-content opacity-60">
      還沒有帳號？
      <button
        type="button"
        class="link link-primary"
        onclick={() => onSwitchToRegister?.()}
      >
        立即註冊
      </button>
    </p>
  </div>
</form>

<style>
  form {
    @apply w-full max-w-md mx-auto p-6 bg-base-100 rounded-lg shadow-md;
  }
  
  .link {
    @apply transition-colors duration-200;
  }
  
  .link:hover {
    @apply underline;
  }
</style>