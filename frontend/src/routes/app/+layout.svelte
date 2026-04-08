<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { AppHeader } from '$lib/components/layout';
  import { authStore } from '$lib/stores/auth.svelte';
  import { setupReadStatusSync, cleanupReadStatusSync } from '$lib/websocket/readStatusSync';
  import { setupRoomListSync, cleanupRoomListSync } from '$lib/websocket/roomListSync';

  import type { Snippet } from 'svelte';

  let { data, children } = $props<{
    data: { user: any };
    children?: Snippet;
  }>();

  onMount(() => {
    // 同步服務端載入的認證狀態到前端 store（不含 token）
    if (data.user) {
      authStore.setAuthState({
        user: data.user,
        loading: false,
      });

      // 設置已讀狀態同步
      try {
        setupReadStatusSync();
      } catch (error) {
        console.error('[App Layout] 設置已讀狀態同步失敗:', error);
      }

      // 設置房間列表同步
      try {
        setupRoomListSync();
      } catch (error) {
        console.error('[App Layout] 設置房間列表同步失敗:', error);
      }
    }
  });

  onDestroy(() => {
    try {
      cleanupReadStatusSync();
    } catch (error) {
      console.error('[App Layout] 清理已讀狀態同步失敗:', error);
    }

    try {
      cleanupRoomListSync();
    } catch (error) {
      console.error('[App Layout] 清理房間列表同步失敗:', error);
    }
  });
</script>

<!-- 移除 AuthGuard，因為已經有服務端的認證檢查 -->
<div class="h-screen bg-base-200 flex flex-col">
  <AppHeader />
  <main class="flex-1 overflow-hidden">
    {@render children?.()}
  </main>
</div>
