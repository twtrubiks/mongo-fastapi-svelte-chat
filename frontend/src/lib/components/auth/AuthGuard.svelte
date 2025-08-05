<script lang="ts">
  import { goto } from '$app/navigation';
  import { authStore, isAuthenticated } from '$lib/stores';
  import { Loading } from '$lib/components/ui';
  
  import type { Snippet } from 'svelte';

  interface Props {
    requireAuth?: boolean;
    redirectTo?: string;
    fallbackTo?: string;
    children?: Snippet;
  }
  
  let {
    requireAuth = true,
    redirectTo = '/login',
    fallbackTo = '/',
    children
  }: Props = $props();
  
  let isLoading = $state(true);
  let isInitialized = $state(false);
  let isRedirecting = $state(false);
  
  // 創建本地的響應式認證變數，避免重複調用函數
  let isAuth = $derived(isAuthenticated());
  
  $effect(async () => {
    // 確保在瀏覽器環境中執行
    if (typeof window === 'undefined') {
      return;
    }
    
    // 檢查 localStorage 和 cookie 的同步狀態
    const localToken = localStorage.getItem('auth_token');
    const cookieToken = document.cookie.split('; ').find(row => row.startsWith('auth_token='))?.split('=')[1];
    
    // 檢查不同步狀態並修復
    if (localToken && !cookieToken) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user');
      authStore.logout();
    } else if (!localToken && cookieToken) {
      document.cookie = 'auth_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT;';
    }
    
    // 重新檢查最終狀態
    const finalToken = localStorage.getItem('auth_token');
    
    // 如果需要認證但沒有 token，進行 client-side 重定向
    if (requireAuth && !finalToken) {
      // 設置重定向狀態
      isRedirecting = true;
      isLoading = false;
      
      // 測試多種重定向方法
      setTimeout(() => {
        try {
          window.location.replace(redirectTo);
        } catch (error1) {
          try {
            window.location.href = redirectTo;
          } catch (error2) {
            try {
              window.location.assign(redirectTo);
            } catch (error3) {
              // 所有重定向方法都失敗
            }
          }
        }
      }, 50);
      return;
    }
    
    // 如果需要認證且有 token 但未認證，嘗試驗證
    if (requireAuth && finalToken && !isAuth) {
      try {
        await authStore.verify();
        
        // 驗證後仍未認證，重定向
        if (!isAuth) {
          await goto(redirectTo, { replaceState: true });
          return;
        }
      } catch (error) {
        await goto(redirectTo, { replaceState: true });
        return;
      }
    }
    
    isInitialized = true;
    isLoading = false;
  });
  
  
  // 決定是否顯示內容
  let shouldShowContent = $derived(
    isInitialized && !isLoading && !isRedirecting
      ? (requireAuth ? isAuth : true)
      : false
  );
</script>

{#if isLoading}
  <Loading fullscreen text="載入中..." />
{:else if isRedirecting}
  <Loading fullscreen text="重定向中..." />
{:else if shouldShowContent}
  {@render children?.()}
{:else}
  <!-- 重定向中，顯示載入畫面 -->
  <Loading fullscreen text="驗證中..." />
{/if}