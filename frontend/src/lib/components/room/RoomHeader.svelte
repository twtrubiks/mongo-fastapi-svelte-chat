<script lang="ts">
  import { Button } from '$lib/components/ui';
  import type { Room } from '$lib/types';
  
  interface Props {
    room?: Room | null;
    onlineCount?: number;
    showMenu?: boolean;
    currentUserId?: string | null;
    onToggleMenu?: (data: { showMenu: boolean }) => void;
    onSettings?: (data: { room: Room | null }) => void;
    onLeave?: (data: { room: Room | null }) => void;
    onMembers?: () => void;
    onSearch?: () => void;
    onDelete?: (data: { room: Room | null }) => void;
  }
  
  let {
    room = null,
    onlineCount = 0,
    showMenu = false,
    currentUserId = null,
    onToggleMenu = undefined,
    onSettings = undefined,
    onLeave = undefined,
    onMembers = undefined,
    onSearch = undefined,
    onDelete = undefined
  }: Props = $props();
  
  function toggleMenu() {
    const newShowMenu = !showMenu;
    onToggleMenu?.({ showMenu: newShowMenu });
  }
  
  function handleSettings() {
    onSettings?.({ room });
  }
  
  function handleLeave() {
    onLeave?.({ room });
  }
  
  function handleDelete() {
    onDelete?.({ room });
  }
  
  // 判斷是否為房間擁有者
  let isOwner = $derived(room && currentUserId && room.owner_id === currentUserId);
</script>

<div class="room-header">
  <div class="room-header-content">
    <!-- 左側：聊天室資訊 -->
    <div class="room-info">
      {#if room}
        <div class="room-details">
          <h1 class="room-name">{room.name}</h1>
          <div class="room-status">
            <span class="online-indicator"></span>
            <span class="online-count">{onlineCount} 人在線</span>
            {#if room.description}
              <span class="room-description">· {room.description}</span>
            {/if}
          </div>
        </div>
      {:else}
        <div class="room-placeholder">
          <span class="placeholder-text">選擇一個聊天室開始聊天</span>
        </div>
      {/if}
    </div>
    
    <!-- 右側：操作按鈕 -->
    <div class="room-actions">
      <!-- 移動端菜單切換（優先顯示） -->
      <button
        class="btn btn-ghost btn-square md:hidden"
        onclick={toggleMenu}
        aria-label="切換菜單"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      
      <!-- 搜尋按鈕 - 不依賴 room 存在，但在沒有 room 時禁用 -->
      <button
        class="btn btn-ghost btn-circle btn-sm"
        disabled={!room}
        onclick={() => onSearch?.()}
        aria-label="搜尋訊息"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </button>
      
      {#if room}
        <!-- 更多選項 -->
        <div class="dropdown dropdown-end">
          <button
            class="btn btn-ghost btn-circle btn-sm"
            tabindex="0"
            aria-label="更多選項"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
            </svg>
          </button>
          
          <ul class="dropdown-content z-10 menu p-2 shadow-lg bg-base-100 rounded-box w-52 min-w-[12rem]" style="max-height: calc(100vh - 120px); overflow-y: auto;">
            <li>
              <button onclick={handleSettings}>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                聊天室設定
              </button>
            </li>
            <li>
              <button onclick={() => onMembers?.()}>
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                </svg>
                成員列表
              </button>
            </li>
            <li><hr class="my-1" /></li>
            <li>
              <button onclick={handleLeave} class="text-error">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                離開聊天室
              </button>
            </li>
            {#if isOwner}
              <li>
                <button onclick={handleDelete} class="text-error">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  刪除聊天室
                </button>
              </li>
            {/if}
          </ul>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .room-header {
    @apply bg-base-100 border-b border-base-200 px-3 py-2;
  }
  
  .room-header-content {
    @apply flex items-center justify-between;
    width: 100%;
  }
  
  .room-info {
    @apply flex-1 min-w-0 mr-2;
  }
  
  .room-actions {
    @apply flex items-center gap-1 flex-shrink-0;
  }
  
  .room-details {
    @apply flex flex-col;
  }
  
  
  .room-name {
    @apply text-lg font-semibold text-base-content truncate;
    max-width: calc(100vw - 140px);
  }
  
  .room-status {
    @apply flex items-center space-x-1 text-xs text-base-content opacity-70 mt-0.5;
  }
  
  .online-indicator {
    @apply w-2 h-2 bg-green-500 rounded-full animate-pulse;
  }
  
  .online-count {
    @apply font-medium;
  }
  
  .room-description {
    @apply truncate max-w-xs;
  }
  
  .room-placeholder {
    @apply flex items-center justify-center h-10;
  }
  
  .placeholder-text {
    @apply text-base-content opacity-60 font-medium text-sm;
  }
  
  .room-actions {
    @apply flex items-center gap-1;
  }
  
  /* 移動端按鈕增大觸控區域 */
  .room-actions .btn-square {
    @apply w-10 h-10 min-h-[2.5rem];
  }
  
  .room-actions .btn-circle {
    @apply w-9 h-9 min-h-[2.25rem];
  }
  
  /* 響應式設計 */
  @media (max-width: 768px) {
    .room-header {
      @apply px-2 py-1.5;
      min-height: 3.25rem;
    }
    
    .room-name {
      @apply text-base;
      max-width: calc(100vw - 160px);
    }
    
    .room-status {
      @apply text-xs;
    }
    
    .room-description {
      @apply hidden;
    }
  }
</style>