<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { bffApiClient, isSuccessResponse, isErrorResponse } from '$lib/bff-api-client';
  import type { DashboardData } from '$lib/bff-types';
  import { Loading, Toast } from '$lib/components/ui';
  import { currentUser } from '$lib/stores/auth.svelte';

  // Svelte 5 響應式狀態
  let dashboardData: DashboardData | null = $state(null);
  let loading = $state(true);
  let error: string | null = $state(null);
  
  // Toast 狀態
  let toastState = $state({
    show: false,
    message: '',
    type: 'success' as 'success' | 'error' | 'warning' | 'info'
  });

  // 創建本地響應式變數，避免重複調用函數
  let user = $derived(currentUser());

  // 響應式派生狀態
  let hasData = $derived(!!dashboardData);
  let roomCount = $derived(dashboardData?.rooms?.length || 0);
  let unreadCount = $derived(dashboardData?.unreadCount || 0);
  let onlineUsers = $derived(dashboardData?.onlineUsers || 0);
  let totalMessages = $derived(dashboardData?.totalMessages || 0);

  // 顯示 Toast 通知
  function showToast(message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') {
    toastState = {
      show: true,
      message,
      type
    };
  }

  // 載入儀表板資料
  async function loadDashboardData() {
    loading = true;
    error = null;

    try {
      const response = await bffApiClient.dashboard.get();
      
      if (isSuccessResponse(response)) {
        dashboardData = response.data;
      } else if (isErrorResponse(response)) {
        error = response.error.message;
      }
    } catch (err) {
      error = '載入儀表板失敗';
    } finally {
      loading = false;
    }
  }

  // 刷新儀表板
  async function refreshDashboard() {
    try {
      const response = await bffApiClient.dashboard.refresh();
      
      if (isSuccessResponse(response)) {
        showToast('儀表板已刷新', 'success');
        
        // 重新載入資料
        await loadDashboardData();
      } else if (isErrorResponse(response)) {
        showToast(response.error.message, 'error');
      }
    } catch (err) {
      showToast('刷新失敗', 'error');
    }
  }

  // 使用批量請求載入資料
  async function loadBatchData() {
    loading = true;
    
    try {
      const batchResults = await bffApiClient.batch({
        dashboard: () => bffApiClient.dashboard.get(),
        auth: () => bffApiClient.auth.getAggregate(),
      });

      if (isSuccessResponse(batchResults.dashboard)) {
        dashboardData = batchResults.dashboard.data;
        showToast('批量載入完成', 'success');
      }
      
      if (isSuccessResponse(batchResults.auth)) {
        // 處理額外的認證聚合資料（如需要）
      }
    } catch (err) {
      error = '批量載入失敗';
      showToast('批量載入失敗', 'error');
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadDashboardData();
  });
</script>

<svelte:head>
  <title>儀表板 - 聊天室應用</title>
</svelte:head>

<div class="dashboard-container" in:fade={{ duration: 300 }}>
  <!-- 頁面標題和操作 -->
  <div class="dashboard-header" in:fly={{ y: -20, duration: 400 }}>
    <div class="flex justify-between items-center">
      <div>
        <h1 class="dashboard-title">📊 儀表板</h1>
        <p class="dashboard-subtitle">查看您的聊天室統計資訊和最近活動</p>
      </div>
      <div class="dashboard-actions">
        <button 
          class="btn btn-primary btn-sm gap-2" 
          onclick={refreshDashboard}
          disabled={loading}
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          刷新
        </button>
        <button 
          class="btn btn-secondary btn-sm gap-2" 
          onclick={loadBatchData}
          disabled={loading}
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          批量載入
        </button>
      </div>
    </div>
  </div>

  <!-- 載入狀態 -->
  {#if loading}
    <div class="loading-container" in:fade>
      <Loading size="lg" />
      <p class="loading-text">正在載入儀表板資料...</p>
    </div>
  {:else if error}
    <!-- 錯誤狀態 -->
    <div class="error-container" in:fly={{ y: 20, duration: 300 }}>
      <div class="alert alert-error">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>錯誤：{error}</span>
        <button class="btn btn-sm btn-outline" onclick={loadDashboardData}>重試</button>
      </div>
    </div>
  {:else if hasData}
    <!-- 主要內容 -->
    <div class="dashboard-content" in:fade={{ duration: 400, delay: 100 }}>
      <!-- 歡迎區塊 -->
      <div class="welcome-card" in:fly={{ y: 20, duration: 400, delay: 200 }}>
        <div class="card bg-gradient-to-r from-primary to-secondary text-primary-content shadow-xl">
          <div class="card-body">
            <h2 class="card-title text-2xl">
              👋 歡迎回來，{user?.username || dashboardData.user.username}！
            </h2>
            <p class="opacity-90">以下是您的最新統計資訊</p>
          </div>
        </div>
      </div>

      <!-- 統計卡片 -->
      <div class="stats-grid" in:fly={{ y: 20, duration: 400, delay: 300 }}>
        <div class="stats stats-vertical lg:stats-horizontal shadow bg-base-100">
          <div class="stat">
            <div class="stat-figure text-primary">
              <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-4m-5 0H9m0 0H5m0 0v-4a2 2 0 011-1h1m0 0V9a2 2 0 011-1h2a1 1 0 011 1v10M9 21h10M9 21v-4a2 2 0 011-1h4a2 2 0 011 1v4" />
              </svg>
            </div>
            <div class="stat-title">聊天室</div>
            <div class="stat-value text-primary">{roomCount}</div>
            <div class="stat-desc">已加入的房間</div>
          </div>
          
          <div class="stat">
            <div class="stat-figure text-secondary">
              <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293L16 14H8l-2.707-1.707A1 1 0 004.586 13H2" />
              </svg>
            </div>
            <div class="stat-title">未讀訊息</div>
            <div class="stat-value text-secondary">{unreadCount}</div>
            <div class="stat-desc">待處理訊息</div>
          </div>
          
          <div class="stat">
            <div class="stat-figure text-accent">
              <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
              </svg>
            </div>
            <div class="stat-title">在線用戶</div>
            <div class="stat-value text-accent">{onlineUsers}</div>
            <div class="stat-desc">目前活躍</div>
          </div>
          
          <div class="stat">
            <div class="stat-figure text-info">
              <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <div class="stat-title">總訊息數</div>
            <div class="stat-value text-info">{totalMessages.toLocaleString()}</div>
            <div class="stat-desc">歷史記錄</div>
          </div>
        </div>
      </div>

      <!-- 內容網格 -->
      <div class="content-grid" in:fly={{ y: 20, duration: 400, delay: 400 }}>
        <!-- 聊天室列表 -->
        <div class="card bg-base-100 shadow-xl">
          <div class="card-body">
            <h2 class="card-title flex items-center gap-2">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-4m-5 0H9m0 0H5m0 0v-4a2 2 0 011-1h1m0 0V9a2 2 0 011-1h2a1 1 0 011 1v10M9 21h10M9 21v-4a2 2 0 011-1h4a2 2 0 011 1v4" />
              </svg>
              我的聊天室
            </h2>
            <div class="space-y-3">
              {#each dashboardData.rooms.slice(0, 5) as room, index}
                <div class="room-item" in:fly={{ x: -20, duration: 300, delay: 100 + index * 50 }}>
                  <div class="flex items-center justify-between p-4 rounded-lg bg-base-200 hover:bg-base-300 transition-colors">
                    <div class="flex-1">
                      <div class="font-semibold text-base-content">{room.name}</div>
                      <div class="text-sm text-base-content opacity-70 line-clamp-1">
                        {room.description || '無描述'}
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <div class="badge badge-primary badge-sm">{room.members.length} 成員</div>
                      <button class="btn btn-ghost btn-xs">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        </div>

        <!-- 最近活動 -->
        <div class="card bg-base-100 shadow-xl">
          <div class="card-body">
            <h2 class="card-title flex items-center gap-2">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              最近活動
            </h2>
            <div class="space-y-4">
              {#each dashboardData.recentActivity.slice(0, 5) as activity, index}
                <div class="activity-item" in:fly={{ x: 20, duration: 300, delay: 100 + index * 50 }}>
                  <div class="flex items-start gap-3">
                    <div class="avatar placeholder">
                      <div class="bg-primary text-primary-content rounded-full w-10 text-sm">
                        <span>{activity.user.username.charAt(0).toUpperCase()}</span>
                      </div>
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="text-sm">
                        <span class="font-semibold text-primary">{activity.user.username}</span>
                        {#if activity.room}
                          在 <span class="font-medium text-secondary">{activity.room.name}</span>
                        {/if}
                        <span class="text-base-content opacity-80">{activity.content}</span>
                      </div>
                      <div class="text-xs text-base-content opacity-50 mt-1">
                        {new Date(activity.timestamp).toLocaleString('zh-TW')}
                      </div>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        </div>

        <!-- 通知列表 -->
        {#if dashboardData.notifications.length > 0}
          <div class="card bg-base-100 shadow-xl col-span-full" in:fly={{ y: 20, duration: 400, delay: 500 }}>
            <div class="card-body">
              <h2 class="card-title flex items-center gap-2">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-5 5v-5z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7H6a2 2 0 00-2 2v9a2 2 0 002 2h8a2 2 0 002-2V9a2 2 0 00-2-2h-3" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2" />
                </svg>
                未讀通知
              </h2>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {#each dashboardData.notifications.slice(0, 6) as notification, index}
                  <div class="notification-item" in:fly={{ scale: 0.8, duration: 300, delay: 100 + index * 50 }}>
                    <div class="alert alert-info">
                      <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div class="flex-1">
                        <div class="font-medium text-sm">{notification.content}</div>
                        <div class="text-xs text-base-content opacity-70 mt-1">
                          {new Date(notification.created_at).toLocaleString('zh-TW')}
                        </div>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/if}
      </div>
    </div>
  {:else}
    <!-- 無資料狀態 -->
    <div class="no-data-container" in:fade>
      <div class="alert alert-info">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>沒有可顯示的儀表板資料</span>
        <button class="btn btn-sm btn-primary" onclick={loadDashboardData}>重新載入</button>
      </div>
    </div>
  {/if}
</div>

<!-- Toast 通知 -->
<Toast
  bind:show={toastState.show}
  type={toastState.type}
  message={toastState.message}
  onClose={() => {
    toastState.show = false;
  }}
/>

<style>
  .dashboard-container {
    @apply p-4 md:p-6 max-w-7xl mx-auto min-h-screen;
  }

  .dashboard-header {
    @apply mb-8;
  }

  .dashboard-title {
    @apply text-3xl md:text-4xl font-bold text-base-content mb-2;
  }

  .dashboard-subtitle {
    @apply text-base-content opacity-70 text-lg;
  }

  .dashboard-actions {
    @apply flex gap-2 flex-wrap;
  }

  .loading-container {
    @apply flex flex-col items-center justify-center py-16;
  }

  .loading-text {
    @apply text-base-content opacity-70 mt-4;
  }

  .error-container {
    @apply py-8;
  }

  .dashboard-content {
    @apply space-y-8;
  }

  .welcome-card {
    @apply mb-8;
  }

  .stats-grid {
    @apply mb-8;
  }

  .content-grid {
    @apply grid grid-cols-1 lg:grid-cols-2 gap-6;
  }

  .room-item:hover {
    @apply transform scale-[1.02] transition-transform duration-200;
  }

  .activity-item {
    @apply border-b border-base-200 last:border-b-0 pb-4 last:pb-0;
  }

  .notification-item {
    @apply h-full;
  }

  .no-data-container {
    @apply py-16;
  }

  /* 響應式優化 */
  @media (max-width: 768px) {
    .dashboard-container {
      @apply p-3;
    }
    
    .dashboard-title {
      @apply text-2xl;
    }
    
    .dashboard-actions {
      @apply flex-col w-full;
    }
    
    .content-grid {
      @apply grid-cols-1 gap-4;
    }
  }

  /* 深色模式優化 */
  @media (prefers-color-scheme: dark) {
    .welcome-card .card {
      @apply shadow-2xl;
    }
  }

  /* 文字截斷 */
  .line-clamp-1 {
    @apply overflow-hidden;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
  }
</style>