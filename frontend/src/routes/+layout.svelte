<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { browser } from '$app/environment';
  import { authStore } from '$lib/stores';
  import type { Snippet } from 'svelte';

  let { children }: { children?: Snippet } = $props();

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
  {@render children?.()}
</main>