<script lang="ts">
  import { Avatar, Loading } from '$lib/components/ui';
  import { formatDateTime } from '$lib/utils';
  import { aiStatus, loadAIStatus } from '$lib/stores/aiStatus.svelte';
  import { BOT_COMMANDS } from '$lib/constants/botCommands';
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
    onInsertCommand?: (text: string) => void;
  }

  let {
    users = [],
    loading = false,
    currentUserId = null,
    compact = false,
    hasMore = false,
    loadingMore = false,
    onUserClick,
    onLoadMore,
    onInsertCommand
  }: Props = $props();

  // AI 助理狀態（登入後查一次；元件掛載時觸發，store 內部去重）
  $effect(() => {
    loadAIStatus();
  });
  let ai = $derived(aiStatus());

  // 用法小卡開關：點右側「AI 助理」項目時彈出，提醒 @bot / /summary 用法
  let showAIHelp = $state(false);

  // 點選小卡裡的指令 → 填入輸入框等使用者補字，並關閉小卡
  function handlePickCommand(insert: string) {
    onInsertCommand?.(insert);
    showAIHelp = false;
  }

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

<svelte:window onkeydown={(e) => { if (showAIHelp && e.key === 'Escape') showAIHelp = false; }} />

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
        <!-- AI 助理（獨立置頂；狀態 = 後端是否配置 API key，非 WebSocket 連線） -->
        <div class="user-section ai-section">
          <div class="section-header">
            <span class="section-title">AI 助理</span>
          </div>
          <div class="user-items">
            <div class="ai-item-wrapper">
              <button
                type="button"
                class="user-item ai-item"
                class:offline={!ai.enabled}
                class:active={showAIHelp}
                onclick={() => (showAIHelp = !showAIHelp)}
                aria-haspopup="dialog"
                aria-expanded={showAIHelp}
                title="點我看 AI 助理用法"
              >
                <div class="user-avatar ai-avatar">🤖</div>

                {#if !compact}
                  <div class="user-info">
                    <div class="user-name">
                      <span class="user-name-text">{ai.botUsername}</span>
                    </div>
                    <div class="user-status">{ai.enabled ? '在線' : '未啟用'}</div>
                  </div>
                  <span class="ai-hint" aria-hidden="true">💡</span>
                {/if}
              </button>

              {#if showAIHelp}
                <!-- 點外部關閉小卡 -->
                <button
                  type="button"
                  class="ai-help-backdrop"
                  aria-label="關閉用法說明"
                  onclick={() => (showAIHelp = false)}
                ></button>

                <div class="ai-help-card" role="dialog" aria-label="AI 助理用法">
                  <div class="ai-help-title">🤖 AI 助理 · 用法</div>
                  {#if ai.enabled}
                    <ul class="ai-help-list">
                      {#each BOT_COMMANDS as cmd (cmd.label)}
                        <li>
                          <button
                            type="button"
                            class="ai-help-item"
                            onclick={() => handlePickCommand(cmd.insert)}
                          >
                            <span class="ai-help-label">{cmd.label}</span>
                            <span class="ai-help-desc">{cmd.description}</span>
                          </button>
                        </li>
                      {/each}
                    </ul>
                    <div class="ai-help-foot">點一下即填入輸入框</div>
                  {:else}
                    <div class="ai-help-disabled">AI 助理目前未啟用</div>
                  {/if}
                </div>
              {/if}
            </div>
          </div>
        </div>

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

  /* AI 助理區塊：圖示獨立於既有 online/offline 規則 */
  .ai-section .section-title::before {
    content: "🤖";
  }

  .ai-avatar {
    @apply flex items-center justify-center w-8 h-8 text-base bg-base-300 rounded-full;
  }

  .ai-item.offline .user-status::before {
    content: "⚪";
  }

  /* AI 助理用法小卡 */
  .ai-item-wrapper {
    @apply relative;
  }

  .ai-hint {
    @apply ml-2 text-base opacity-70 flex-shrink-0;
  }

  .ai-item.active {
    @apply ring-2 ring-primary/30;
  }

  .ai-help-backdrop {
    @apply fixed inset-0 z-40 cursor-default;
  }

  .ai-help-card {
    @apply absolute left-0 right-0 top-full z-50 mt-2 p-2;
    @apply bg-base-100 border border-base-300 rounded-lg shadow-lg;
  }

  .ai-help-title {
    @apply px-2 py-1 text-xs font-bold text-base-content opacity-70;
  }

  .ai-help-list {
    @apply list-none p-0 m-0 space-y-1;
  }

  .ai-help-item {
    @apply w-full flex flex-col items-start gap-0.5 px-2 py-2 rounded-md text-left transition-colors hover:bg-base-200;
  }

  .ai-help-label {
    @apply font-semibold text-sm text-base-content;
  }

  .ai-help-desc {
    @apply text-xs text-base-content opacity-60;
  }

  .ai-help-foot {
    @apply px-2 pt-2 mt-1 text-[11px] text-base-content opacity-50 border-t border-base-200;
  }

  .ai-help-disabled {
    @apply px-2 py-3 text-sm text-base-content opacity-60 text-center;
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