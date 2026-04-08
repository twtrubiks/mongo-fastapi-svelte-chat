<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { authStore } from '$lib/stores';

  onMount(async () => {
    const restored = authStore.init();

    if (restored) {
      try {
        await authStore.verify();
        goto('/app');
      } catch {
        goto('/login');
      }
    } else {
      goto('/login');
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
