<script lang="ts">
  import { authStore } from '$lib/stores';
  import { validateUsername, validateEmail, validatePassword, formatAuthError } from '$lib/utils';
  import { Button, Input } from '$lib/components/ui';
  import type { RegisterData } from '$lib/types';
  
  interface Props {
    onSuccess?: (data: { message: string }) => void;
    onError?: (data: { message: string }) => void;
    onSwitchToLogin?: () => void;
  }
  
  let {
    onSuccess = undefined,
    onError = undefined,
    onSwitchToLogin = undefined
  }: Props = $props();
  
  let userData = $state<RegisterData>({
    username: '',
    email: '',
    password: '',
  });
  
  let confirmPassword = $state('');
  let errors: Record<string, string> = $state({});
  let isSubmitting = $state(false);
  let submitError = $state('');
  
  function validateForm(): boolean {
    errors = {};
    
    // 用戶名驗證
    if (!userData.username.trim()) {
      errors.username = '請輸入用戶名';
    } else {
      const usernameValidation = validateUsername(userData.username);
      if (!usernameValidation.isValid) {
        errors.username = usernameValidation.errors[0];
      }
    }
    
    // 電子郵件驗證
    if (!userData.email.trim()) {
      errors.email = '請輸入電子郵件';
    } else if (!validateEmail(userData.email)) {
      errors.email = '請輸入有效的電子郵件地址';
    }
    
    // 密碼驗證
    if (!userData.password.trim()) {
      errors.password = '請輸入密碼';
    } else {
      const passwordValidation = validatePassword(userData.password);
      if (!passwordValidation.isValid) {
        errors.password = passwordValidation.errors[0];
      }
    }
    
    // 確認密碼驗證
    if (!confirmPassword.trim()) {
      errors.confirmPassword = '請確認密碼';
    } else if (userData.password !== confirmPassword) {
      errors.confirmPassword = '兩次輸入的密碼不一致';
    }
    
    return Object.keys(errors).length === 0;
  }
  
  async function handleSubmit() {
    if (!validateForm()) return;
    
    isSubmitting = true;
    submitError = '';
    
    try {
      await authStore.register(userData);
      onSuccess?.({ message: '註冊成功！歡迎加入！' });
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
    <h1 class="text-2xl font-bold text-base-content">建立新帳號</h1>
    <p class="text-base-content opacity-60 mt-2">請填寫以下資訊完成註冊</p>
  </div>
  
  <Input
    label="用戶名"
    type="text"
    bind:value={userData.username}
    placeholder="請輸入用戶名"
    error={errors.username}
    hint="3-20 個字符，只能包含字母、數字和下劃線"
    required
    autocomplete="username"
    onkeydown={handleKeydown}
  />
  
  <Input
    label="電子郵件"
    type="email"
    bind:value={userData.email}
    placeholder="請輸入電子郵件"
    error={errors.email}
    required
    autocomplete="email"
    onkeydown={handleKeydown}
  />
  
  <Input
    label="密碼"
    type="password"
    bind:value={userData.password}
    placeholder="請輸入密碼"
    error={errors.password}
    hint="至少 8 個字符，包含大小寫字母和數字"
    required
    autocomplete="new-password"
    onkeydown={handleKeydown}
  />
  
  <Input
    label="確認密碼"
    type="password"
    bind:value={confirmPassword}
    placeholder="請再次輸入密碼"
    error={errors.confirmPassword}
    required
    autocomplete="new-password"
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
    {isSubmitting ? '註冊中...' : '註冊'}
  </Button>
  
  <div class="text-center">
    <p class="text-base-content opacity-60">
      已有帳號？
      <button
        type="button"
        class="link link-primary"
        onclick={() => onSwitchToLogin?.()}
      >
        立即登入
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