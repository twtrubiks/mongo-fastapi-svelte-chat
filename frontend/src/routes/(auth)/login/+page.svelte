<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { LoginForm } from '$lib/components/auth';
  import { Toast } from '$lib/components/ui';
  import { safeReturnPath } from '$lib/utils/loginRedirect';

  let showToast = $state(false);
  let toastMessage = $state('');
  let toastType: 'success' | 'error' = $state('success');

  function handleLoginSuccess(data: { message: string }) {
    toastMessage = data.message;
    toastType = 'success';
    showToast = true;
    
    // 給瀏覽器一點時間設置 cookie，然後跳轉；有 redirect 就回到登入前的頁面
    const returnTo = safeReturnPath(page.url.searchParams.get('redirect')) ?? '/app';
    setTimeout(() => {
      goto(returnTo);
    }, 100);
  }

  function handleLoginError(data: { message: string }) {
    toastMessage = data.message;
    toastType = 'error';
    showToast = true;
  }

  function handleSwitchToRegister() {
    goto('/register');
  }
</script>

<div class="hero min-h-screen bg-base-200">
  <div class="hero-content flex-col lg:flex-row-reverse">
    <div class="text-center lg:text-left">
      <h1 class="text-5xl font-bold">立即登入</h1>
      <p class="py-6">歡迎回到聊天室！請輸入您的帳號資料來登入。</p>
    </div>
    <div class="card shrink-0 w-full max-w-sm shadow-2xl bg-base-100">
      <div class="card-body">
        <LoginForm
          onSuccess={handleLoginSuccess}
          onError={handleLoginError}
          onSwitchToRegister={handleSwitchToRegister}
        />
      </div>
    </div>
  </div>
</div>

<Toast
  bind:show={showToast}
  type={toastType}
  message={toastMessage}
  onClose={() => showToast = false}
/>