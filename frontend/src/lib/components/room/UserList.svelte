<script lang="ts">
  import { Avatar, Loading } from '$lib/components/ui';
  import { formatDateTime } from '$lib/utils';
  import type { User } from '$lib/types';
  
  interface Props {
    users?: User[];
    loading?: boolean;
    currentUserId?: string | null;
    compact?: boolean;
    hasMore?: boolean;
    loadingMore?: boolean;
    onUserClick?: (event: { user: User }) => void;
    onLoadMore?: () => void;
  }

  let {
    users = [],
    loading = false,
    currentUserId = null,
    compact = false,
    hasMore = false,
    loadingMore = false,
    onUserClick,
    onLoadMore
  }: Props = $props();

  // 按狀態分組用戶 - 使用 $derived，確保 users 是陣列
  let onlineUsers = $derived(Array.isArray(users) ? users.filter(user => user.is_active) : []);
  let offlineUsers = $derived(Array.isArray(users) ? users.filter(user => !user.is_active) : []);

  function handleUserClick(user: User) {
    onUserClick?.({ user });
  }

  function handleScroll(e: Event) {
    if (!hasMore || loadingMore || !onLoadMore) return;
    const el = e.target as HTMLElement;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 100) {
      onLoadMore();
    }
  }
</script>

<div class="user-list" class:compact>
  <div class="user-list-header">
    <h3 class="user-list-title">
      成員 ({users.length})
    </h3>
  </div>
  
  <div class="user-list-content" onscroll={handleScroll}>
    {#if loading}
      <Loading size="sm" text="載入成員..." />
    {:else if users.length === 0}
      <div class="empty-state">
        <div class="empty-state-icon">
          <svg class="w-6 h-6 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
          </svg>
        </div>
        <p class="empty-state-text">暫無成員</p>
      </div>
    {:else}
      <div class="user-sections">
        <!-- 在線用戶 -->
        {#if onlineUsers.length > 0}
          <div class="user-section">
            <div class="section-header">
              <span class="section-title">在線 ({onlineUsers.length})</span>
            </div>
            <div class="user-items">
              {#each onlineUsers as user (user.id)}
                <button
                  class="user-item"
                  class:current={currentUserId === user.id}
                  onclick={() => handleUserClick(user)}
                >
                  <div class="user-avatar">
                    <Avatar {user} size="sm" online={true} />
                  </div>
                  
                  {#if !compact}
                    <div class="user-info">
                      <div class="user-name">
                        <span class="user-name-text">{user.username}</span>
                        {#if currentUserId === user.id}
                          <span class="user-badge">（你）</span>
                        {/if}
                      </div>
                      <div class="user-status">在線</div>
                    </div>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        {/if}
        
        <!-- 離線用戶 -->
        {#if offlineUsers.length > 0}
          <div class="user-section">
            <div class="section-header">
              <span class="section-title">離線 ({offlineUsers.length})</span>
            </div>
            <div class="user-items">
              {#each offlineUsers as user (user.id)}
                <button
                  class="user-item offline"
                  class:current={currentUserId === user.id}
                  onclick={() => handleUserClick(user)}
                >
                  <div class="user-avatar">
                    <Avatar {user} size="sm" online={false} />
                  </div>
                  
                  {#if !compact}
                    <div class="user-info">
                      <div class="user-name">
                        <span class="user-name-text">{user.username}</span>
                        {#if currentUserId === user.id}
                          <span class="user-badge">（你）</span>
                        {/if}
                      </div>
                      <div class="user-status">
                        {formatDateTime(user.created_at ?? '')}
                      </div>
                    </div>
                  {/if}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      {#if loadingMore}
        <div class="flex justify-center py-3">
          <span class="loading loading-dots loading-sm"></span>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
	@reference "$lib/styles/tailwind.css";
  .user-list {
    @apply flex flex-col h-full bg-base-100 border-l border-base-200;
  }
  
  .user-list.compact {
    @apply w-16;
  }
  
  .user-list-header {
    @apply px-4 py-3 bg-base-100 border-b border-base-200 shadow-sm;
  }
  
  .user-list-title {
    @apply text-sm font-bold text-base-content uppercase tracking-wide flex items-center;
  }
  
  .user-list-title::before {
    content: "👥";
    @apply mr-2 text-base;
  }
  
  .user-list.compact .user-list-title {
    @apply hidden;
  }
  
  .user-list-content {
    @apply flex-1 overflow-y-auto p-3;
  }
  
  .empty-state {
    @apply flex flex-col items-center justify-center h-32 p-6 text-center bg-base-200 rounded-lg mx-2;
  }
  
  .empty-state-icon {
    @apply mb-3 p-2 bg-base-300 rounded-full;
  }
  
  .empty-state-text {
    @apply text-sm text-base-content opacity-60 font-medium;
  }
  
  .user-sections {
    @apply space-y-4;
  }
  
  .user-section {
    @apply bg-base-200 rounded-lg p-3;
  }
  
  .section-header {
    @apply px-2 py-1 mb-3;
  }
  
  .section-title {
    @apply text-xs font-bold text-base-content opacity-70 uppercase tracking-wide flex items-center;
  }
  
  .section-title::before {
    content: "🟢";
    @apply mr-2;
  }
  
  .user-section:last-child .section-title::before {
    content: "⚫";
  }
  
  .user-list.compact .section-header {
    @apply hidden;
  }
  
  .user-items {
    @apply space-y-2;
  }
  
  .user-item {
    @apply flex items-center w-full p-3 rounded-xl text-left transition-all duration-200 hover:bg-base-200 hover:shadow-sm focus:bg-base-200 focus:outline-none focus:ring-2 focus:ring-primary/20 bg-base-100;
  }
  
  .user-item.current {
    @apply bg-gradient-to-r from-primary to-primary text-primary-content shadow-md;
    filter: brightness(0.95);
  }
  
  .user-item.offline {
    @apply opacity-60 hover:opacity-80;
  }
  
  .user-list.compact .user-item {
    @apply justify-center p-3 rounded-xl;
  }
  
  .user-avatar {
    @apply flex-shrink-0 mr-3 overflow-visible;
  }
  
  .user-list.compact .user-avatar {
    @apply mr-0;
  }
  
  .user-info {
    @apply flex-1 min-w-0;
  }
  
  .user-list.compact .user-info {
    @apply hidden;
  }
  
  .user-name {
    @apply text-sm font-semibold text-current flex items-center min-w-0;
  }

  .user-name-text {
    @apply truncate;
  }
  
  .user-badge {
    @apply text-xs font-bold text-white ml-2 bg-purple-600 px-2 py-1 rounded-full shadow-sm flex-shrink-0;
  }
  
  .user-status {
    @apply text-xs text-current opacity-60 mt-1 flex items-center;
  }
  
  .user-status::before {
    content: "⏰";
    @apply mr-1;
  }
  
  .user-item:not(.offline) .user-status::before {
    content: "🟢";
  }
  
  .user-item.current .user-name {
    @apply text-primary-content font-bold;
  }
  
  .user-item.current .user-badge {
    @apply text-white bg-white/90 font-bold shadow-sm;
    color: #4338ca; /* 深紫色文字確保在白色背景上有良好對比度 */
  }
  
  .user-item.current .user-status {
    @apply text-primary-content opacity-80;
  }
  
  /* Hover 效果增強 */
  .user-item:not(.current):hover {
    @apply transform scale-[1.02];
  }
  
  /* 動畫效果 */
  .user-item {
    animation: user-appear 0.2s ease-out;
  }
  
  @keyframes user-appear {
    from {
      opacity: 0;
      transform: translateX(10px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
  
  /* 滾動條美化 */
  .user-list-content::-webkit-scrollbar {
    @apply w-1;
  }
  
  .user-list-content::-webkit-scrollbar-track {
    @apply bg-transparent;
  }
  
  .user-list-content::-webkit-scrollbar-thumb {
    @apply bg-base-300 rounded-full;
  }
  
  .user-list-content::-webkit-scrollbar-thumb:hover {
    @apply bg-primary opacity-60;
  }
  
  /* 響應式設計 */
  @media (max-width: 768px) {
    .user-list-content {
      @apply p-2;
    }
    
    .user-item {
      @apply p-2;
    }
  }
</style>