<script lang="ts">
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { authStore, isAuthenticated } from '$lib/stores';

  let isChecking = $state(true);

  $effect(async () => {
    if (browser) {
      
      // 先初始化認證狀態
      const restored = authStore.init();
      
      if (restored) {
        try {
          // 如果成功恢復狀態，驗證 token 是否仍然有效
          await authStore.verify();
          // token 有效，跳轉到應用頁面
          goto('/app');
        } catch (error) {
          // token 無效，跳轉到登入頁面
          goto('/login');
        }
      } else {
        // 沒有可恢復的狀態，跳轉到登入頁面
        goto('/login');
      }
      
      isChecking = false;
    }
  });
</script>

<div class="hero min-h-screen bg-base-200">
  <div class="hero-content text-center">
    <div class="max-w-md">
      <div class="loading loading-spinner loading-lg text-primary"></div>
      <h1 class="text-5xl font-bold mt-4">聊天室</h1>
      <p class="py-6">正在載入中...</p>
    </div>
  </div>
</div>
