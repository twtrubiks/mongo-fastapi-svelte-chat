<script lang="ts">
  import '../app.postcss';
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { authStore } from '$lib/stores';

  onMount(() => {
    if (browser) {
      // 初始化認證狀態 - 這很重要，用於在頁面重新整理時恢復登入狀態
      authStore.init();
      
      // 初始化主題
      const theme = localStorage.getItem('theme') || 'light';
      document.documentElement.setAttribute('data-theme', theme);
    }
  });
</script>

<main class="min-h-screen bg-base-100">
  <slot />
</main>