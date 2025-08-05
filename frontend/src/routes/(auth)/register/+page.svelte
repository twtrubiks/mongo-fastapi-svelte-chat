<script lang="ts">
  import { goto } from '$app/navigation';
  import { RegisterForm } from '$lib/components/auth';
  import { Toast } from '$lib/components/ui';

  let showToast = $state(false);
  let toastMessage = $state('');
  let toastType: 'success' | 'error' = $state('success');

  function handleRegisterSuccess(data: { message: string }) {
    toastMessage = data.message;
    toastType = 'success';
    showToast = true;
    
    // 註冊成功後跳轉到登入頁面
    setTimeout(() => {
      goto('/login');
    }, 1500); // 給用戶時間看到成功訊息
  }

  function handleRegisterError(data: { message: string }) {
    toastMessage = data.message;
    toastType = 'error';
    showToast = true;
  }

  function handleSwitchToLogin() {
    goto('/login');
  }
</script>

<div class="hero min-h-screen bg-base-200">
  <div class="hero-content flex-col lg:flex-row-reverse">
    <div class="text-center lg:text-left">
      <h1 class="text-5xl font-bold">立即註冊</h1>
      <p class="py-6">加入聊天室，開始與朋友們聊天吧！</p>
    </div>
    <div class="card shrink-0 w-full max-w-sm shadow-2xl bg-base-100">
      <div class="card-body">
        <RegisterForm
          onSuccess={handleRegisterSuccess}
          onError={handleRegisterError}
          onSwitchToLogin={handleSwitchToLogin}
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