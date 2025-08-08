<script lang="ts">
  import { goto } from '$app/navigation';
  import { authStore, currentUser } from '$lib/stores/auth.svelte';
  import { Avatar, Button, NotificationButton, NotificationSettings } from '$lib/components/ui';

  let showNotificationSettings = $state(false);
  
  // 創建本地的響應式用戶變數
  let user = $derived(currentUser());
  
  $effect(() => {
    // console.log('[AppHeader] 當前用戶:', user);
    // console.log('[AppHeader] 用戶頭像:', user?.avatar);
  });
  
  async function handleLogout() {
    try {
      // 現在 logout 是異步的，需要 await
      await authStore.logout();
      
      // 根據文檔建議使用 invalidateAll
      await goto('/login', { 
        replaceState: true,    // 替換歷史記錄
        invalidateAll: true    // 使所有 load 函數重新執行
      });
    } catch (error) {
      console.error('[AppHeader] 登出失敗:', error);
      // 即使失敗也要嘗試跳轉
      await goto('/login', { replaceState: true });
    }
  }
</script>

<header class="navbar bg-base-100 shadow-md border-b border-base-200">
  <div class="w-full px-3 md:px-6">
    <!-- 左側：聊天室標題 -->
    <div class="flex-1">
      <a href="/app/rooms" class="btn btn-ghost text-lg md:text-xl font-bold text-primary hover:bg-primary hover:bg-opacity-10 hover:text-primary-content transition-all px-2 md:px-4">
        <svg class="w-5 h-5 md:w-6 md:h-6 mr-1 md:mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
        <span class="hidden sm:inline">聊天室</span>
        <span class="sm:hidden">Chat</span>
      </a>
    </div>
    
    {#if currentUser}
      <!-- 右側：通知按鈕和用戶選單 -->
      <div class="flex-none flex items-center gap-1 md:gap-2">
        <NotificationButton />
        
        <div class="dropdown dropdown-start">
          <div tabindex="0" role="button" class="btn btn-ghost btn-circle avatar">
            <Avatar 
              user={user}
              size="xs"
              alt={user?.username}
            />
          </div>
          
          <ul tabindex="0" class="dropdown-content menu bg-base-100 rounded-box z-[1] w-52 p-2 shadow">
            <li class="menu-title px-0 py-2">
              <div class="flex flex-col items-start">
                <span class="font-bold text-base text-base-content">{user?.username}</span>
                <span class="text-xs opacity-70 text-base-content">{user?.email}</span>
              </div>
            </li>
            <li><hr class="my-2 border-base-300" /></li>
            <li>
              <a href="/app/profile" class="flex items-center">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                個人資料
              </a>
            </li>
            <li>
              <a href="/app/dashboard" class="flex items-center">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                儀表板
              </a>
            </li>
            <li>
              <a href="/app/rooms" class="flex items-center">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                聊天室列表
              </a>
            </li>
            <li>
              <button onclick={() => showNotificationSettings = true} class="flex items-center w-full">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
                通知設置
              </button>
            </li>
            <li><hr class="my-2" /></li>
            <li>
              <button onclick={handleLogout} class="flex items-center text-error">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                登出
              </button>
            </li>
          </ul>
        </div>
      </div>
    {/if}
  </div>
</header>

<!-- 通知設置模態框 -->
<NotificationSettings 
  bind:open={showNotificationSettings}
  onClose={() => showNotificationSettings = false}
/>

<style>
  /* 使用更具體的選擇器，避免全域汙染 */
  header.navbar {
    position: sticky;
    top: 0;
    z-index: 40;
  }
</style>