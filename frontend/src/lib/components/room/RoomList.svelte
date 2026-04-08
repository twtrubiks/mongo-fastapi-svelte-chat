<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { roomStore, roomLoading, hasMoreRooms, loadingMoreRooms, hasMoreMyRooms, loadingMoreMyRooms, activeTab, myRoomIds } from '$lib/stores';
  import { Loading, Avatar } from '$lib/components/ui';
  import JoinRoomModal from './JoinRoomModal.svelte';
  import CreateRoomModal from './CreateRoomModal.svelte';
  import JoinByInviteModal from './JoinByInviteModal.svelte';
  import RoomListHeader from './RoomListHeader.svelte';
  import RoomSearchBar from './RoomSearchBar.svelte';
  import { RoomType, JoinPolicy } from '$lib/types';
  import type { RoomSummary } from '$lib/types';
  import { isRetryableError } from '$lib/utils/retry';

  interface Props {
    currentRoomId?: string | null;
    compact?: boolean;
    mobileMode?: boolean;
    rooms?: RoomSummary[] | null;
    onRoomSelected?: (data: { room: RoomSummary }) => void;
  }
  
  let {
    currentRoomId = null,
    compact = false,
    mobileMode = false,
    rooms = null,
    onRoomSelected = undefined
  }: Props = $props();
  
  let searchInput = $state('');
  let trimmedSearch = $derived(searchInput.trim());
  let searchLower = $derived(trimmedSearch.toLowerCase());

  let currentTab = $derived(activeTab());
  let joinedRoomIds = $derived(myRoomIds());
  // 兩個 tab 搜尋策略不同：
  // - 已加入 tab：資料量少且已全部載入，直接用 trimmedSearch 做前端過濾
  // - 探索 tab：資料量大需分頁，搜尋由後端 API 處理（透過 store 的 searchQuery）
  // 高亮統一使用 trimmedSearch，因為不論哪個 tab 搜尋關鍵字都來自本地 searchInput
  let displayRooms = $derived.by(() => {
    if (currentTab === 'joined') {
      const rooms = roomStore.state.myRooms || [];
      if (searchLower) {
        return rooms.filter(r => r.name.toLowerCase().includes(searchLower));
      }
      return rooms;
    }
    // 探索 tab：後端已透過 exclude_joined 排除已加入的房間
    return roomStore.state.rooms || [];
  });
  let isRoomLoading = $derived(roomLoading());
  let hasMore = $derived(currentTab === 'joined' ? hasMoreMyRooms() : hasMoreRooms());
  let isLoadingMore = $derived(currentTab === 'joined' ? loadingMoreMyRooms() : loadingMoreRooms());
  
  let showCreateModal = $state(false);

  // 加入房間相關狀態
  let showJoinModal = $state(false);
  let selectedRoomToJoin = $state<RoomSummary | null>(null);

  // 邀請碼加入相關狀態
  let showJoinByInviteModal = $state(false);

  // 滾動容器 ref（用於自動填充偵測）
  let roomListContainer: HTMLDivElement | null = null;
  
  // 自動填充：當可見房間不足以觸發滾動時，自動載入更多（上限 5 次防止過度請求）
  let autoFillCount = 0;
  const MAX_AUTO_FILL = 5;
  $effect(() => {
    if (currentTab !== 'explore' || !hasMore || isLoadingMore || displayRooms.length === 0) {
      if (currentTab !== 'explore' || !hasMore) autoFillCount = 0;
      return;
    }

    tick().then(() => {
      const container = roomListContainer;
      if (!container) return;
      if (container.scrollHeight <= container.clientHeight + 100 && autoFillCount < MAX_AUTO_FILL) {
        autoFillCount++;
        loadMore();
      }
    });
  });
  
  
  
  // 載入聊天室列表（根據 activeTab）
  async function loadRooms() {
    try {
      if (rooms && rooms.length > 0) {
        roomStore.initializeWithServerRooms(rooms);
        return;
      }

      // 預設載入已加入的房間
      await roomStore.loadMyRooms(true);
    } catch (error) {
      console.error('[RoomList] 載入房間列表失敗:', error);

      if (shouldRetryError(error)) {
        setTimeout(() => loadRooms(), 5000);
      }
    }
  }

  async function switchTab(tab: 'joined' | 'explore') {
    try {
      searchInput = '';
      await roomStore.switchTab(tab);
    } catch (error) {
      console.error('[RoomList] 切換分頁失敗:', error);
    }
  }

  // 判斷是否應該重試的錯誤（使用共用邏輯）
  const shouldRetryError = isRetryableError;

  // 載入更多聊天室
  async function loadMore() {
    try {
      if (currentTab === 'joined') {
        await roomStore.loadMoreMyRooms();
      } else {
        await roomStore.loadMoreRooms();
      }
    } catch (error) {
      console.error('[RoomList] 載入更多房間失敗:', error);

      if (shouldRetryError(error)) {
        setTimeout(() => {
          loadMore();
        }, 3000);
      }
    }
  }

  // 滾動到底部時載入更多
  async function handleScroll(event: Event) {
    const container = event.target as HTMLElement;
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;

    if (scrollHeight - scrollTop - clientHeight < 100 && !isLoadingMore && hasMore) {
      await loadMore();
    }
  }
  
  function clearSearch() {
    searchInput = '';
    if (currentTab === 'explore') roomStore.searchRooms('');
  }

  // 建房成功回調
  function handleCreateSuccess(room: RoomSummary) {
    onRoomSelected?.({ room });
  }

  // 選擇聊天室
  function selectRoom(room: RoomSummary) {
    // 檢查是否需要特殊加入流程
    if (needsSpecialJoin(room)) {
      selectedRoomToJoin = room;
      showJoinModal = true;
    } else {
      onRoomSelected?.({ room });
    }
  }
  
  // 檢查是否需要特殊加入流程
  function needsSpecialJoin(room: RoomSummary): boolean {
    if (joinedRoomIds.has(room.id)) return false;
    return room.room_type === RoomType.PRIVATE || room.join_policy === JoinPolicy.PASSWORD || room.join_policy === JoinPolicy.INVITE;
  }
  
  // 加入房間成功回調
  function handleJoinSuccess(room: RoomSummary) {
    showJoinModal = false;
    selectedRoomToJoin = null;
    onRoomSelected?.({ room });
  }
  
  // 關閉加入模態框
  function handleJoinClose() {
    showJoinModal = false;
    selectedRoomToJoin = null;
  }
  
  // 搜尋關鍵字高亮（queryLower 為已預先轉小寫的搜尋字串，避免每個房間重複轉換）
  function highlightText(text: string, queryLower: string): { text: string; match: boolean }[] {
    if (!queryLower) return [{ text, match: false }];
    const idx = text.toLowerCase().indexOf(queryLower);
    if (idx === -1) return [{ text, match: false }];
    return [
      { text: text.slice(0, idx), match: false },
      { text: text.slice(idx, idx + queryLower.length), match: true },
      { text: text.slice(idx + queryLower.length), match: false }
    ].filter(s => s.text);
  }

  // 初始化載入
  onMount(() => {
    loadRooms();
  });
</script>

<div class="room-list" class:compact class:mobile-mode={mobileMode}>
  <!-- 標題和操作按鈕 -->
  <RoomListHeader
    {compact}
    {mobileMode}
    onCreateRoom={() => showCreateModal = true}
    onJoinByInvite={() => showJoinByInviteModal = true}
  />
  
  <!-- Tab 切換 -->
  {#if !compact}
    <div role="tablist" class="tabs tabs-boxed mx-2 my-2 flex-shrink-0">
      <button
        role="tab"
        class="tab flex-1"
        class:tab-active={currentTab === 'joined'}
        onclick={() => switchTab('joined')}
      >已加入</button>
      <button
        role="tab"
        class="tab flex-1"
        class:tab-active={currentTab === 'explore'}
        onclick={() => switchTab('explore')}
      >探索</button>
    </div>
  {/if}

  <!-- 搜尋框 -->
  {#if !compact}
    <RoomSearchBar
      {currentTab}
      bind:searchValue={searchInput}
      onSearch={(value) => roomStore.searchRooms(value)}
      onClear={clearSearch}
    />
  {/if}

  <!-- 聊天室列表 -->
  <div class="room-list-content" bind:this={roomListContainer} onscroll={handleScroll}>
    {#if isRoomLoading && displayRooms.length === 0}
      <Loading text="載入聊天室..." />
    {:else if displayRooms.length === 0}
      <div class="empty-state">
        <div class="empty-state-icon">
          <svg class="w-8 h-8 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        {#if trimmedSearch}
          <p class="empty-state-text">找不到符合「{trimmedSearch}」的聊天室</p>
          <button
            class="btn btn-primary btn-sm"
            onclick={clearSearch}
          >
            清除搜尋
          </button>
        {:else if currentTab === 'joined'}
          <p class="empty-state-text">尚未加入任何聊天室</p>
          <button
            class="btn btn-primary btn-sm"
            onclick={() => switchTab('explore')}
          >
            探索聊天室
          </button>
        {:else if currentTab === 'explore' && !hasMore}
          <p class="empty-state-text">你已加入所有聊天室</p>
          <button
            class="btn btn-primary btn-sm"
            onclick={() => switchTab('joined')}
          >
            查看已加入
          </button>
        {:else}
          <p class="empty-state-text">暫無公開聊天室</p>
          <button
            class="btn btn-primary btn-sm"
            onclick={() => showCreateModal = true}
          >
            創建第一個聊天室
          </button>
        {/if}
      </div>
    {:else}
      <!-- 使用 DaisyUI menu 組件，手機端更緊湊 -->
      <ul class="menu {mobileMode ? 'p-1' : 'p-2'} w-full">
        {#each displayRooms as room (room.id)}
          <li>
            <button
              class="flex items-center gap-2 {mobileMode ? 'px-2 py-2.5 min-h-[3rem]' : 'px-3 py-2'}"
              class:active={currentRoomId === room.id}
              onclick={() => selectRoom(room)}
            >
              <Avatar
                user={{ username: room.name }}
                size={mobileMode ? "xs" : "sm"}
              />
              
              <div class="flex-1 min-w-0 text-left">
                <div class="font-semibold truncate {mobileMode ? 'text-sm' : ''}">
                  {#each highlightText(room.name, searchLower) as segment, i (i)}
                    {#if segment.match}
                      <mark class="bg-yellow-200 rounded-sm">{segment.text}</mark>
                    {:else}
                      {segment.text}
                    {/if}
                  {/each}
                </div>
                <div class="text-xs opacity-60">
                  {#if room.owner_name}
                    <span>by {room.owner_name}</span>
                    <span>·</span>
                  {/if}
                  <span>👥 {room.member_count} 成員</span>
                </div>
              </div>
              
              <!-- 徽章 -->
              <div class="flex gap-1">
                {#if room.room_type === RoomType.PRIVATE}
                  <span class="badge badge-xs">🔒</span>
                {/if}
                {#if room.join_policy === JoinPolicy.PASSWORD}
                  <span class="badge badge-xs">🔑</span>
                {:else if room.join_policy === JoinPolicy.INVITE}
                  <span class="badge badge-xs">📧</span>
                {/if}
              </div>
            </button>
          </li>
        {/each}
        
        <!-- 載入更多指示器（僅探索 tab） -->
        {#if currentTab === 'explore'}
          {#if isLoadingMore}
            <div class="loading-more">
              <Loading text="載入更多聊天室..." size="sm" />
            </div>
          {:else if hasMore}
            <div class="load-more-trigger">
              <p class="text-sm text-base-content/60 text-center py-4">
                滾動到底部載入更多聊天室
              </p>
            </div>
          {:else if displayRooms.length > 0}
            <div class="no-more-data">
              <p class="text-sm text-base-content/40 text-center py-4">
                已顯示所有聊天室
              </p>
            </div>
          {/if}
        {/if}
      </ul>
    {/if}
  </div>
  
  <!-- 創建聊天室模態框 -->
  <CreateRoomModal
    bind:open={showCreateModal}
    onSuccess={handleCreateSuccess}
    onClose={() => showCreateModal = false}
  />

  <!-- 加入房間模態框 -->
  {#if selectedRoomToJoin}
    <JoinRoomModal
      room={selectedRoomToJoin}
      show={showJoinModal}
      onClose={handleJoinClose}
      onSuccess={handleJoinSuccess}
    />
  {/if}

  <!-- 通過邀請碼加入房間模態框 -->
  <JoinByInviteModal
    bind:open={showJoinByInviteModal}
    onSuccess={(room) => onRoomSelected?.({ room })}
    onClose={() => showJoinByInviteModal = false}
  />
</div>

<style>
	@reference "$lib/styles/tailwind.css";
  .room-list {
    @apply flex flex-col h-full bg-base-100;
    width: 100%;
    position: relative;
    box-sizing: border-box;
    overflow: hidden;
  }
  
  /* 確保所有子元素也使用 border-box */
  .room-list * {
    box-sizing: border-box;
  }
  
  .room-list.compact {
    @apply w-16;
  }
  
  .room-list-content {
    @apply flex-1 overflow-y-auto;
    min-height: 0;
    width: 100%;
    box-sizing: border-box;
  }
  
  /* DaisyUI menu 項目自定義樣式 */
  .menu li button.active {
    @apply bg-primary text-primary-content;
  }
  
  .menu li button:not(.active):hover {
    @apply bg-base-200;
  }
  
  /* 移動端模式樣式 */
  .room-list.mobile-mode {
    @apply h-full flex flex-col;
    max-height: 100vh;
  }
  
  .room-list.mobile-mode .room-list-content {
    @apply flex-1 overflow-y-auto;
    padding: 0;
    /* 確保內容可以滾動 */
    -webkit-overflow-scrolling: touch;
    min-height: 0;
    /* 設置最大高度以確保可滾動 */
    max-height: calc(100vh - 3.5rem);
  }
  
  .empty-state {
    @apply flex flex-col items-center justify-center h-full p-8 text-center;
  }
  
  .empty-state-icon {
    @apply mb-6;
  }
  
  .empty-state-text {
    @apply text-base-content opacity-60 mb-6 text-base;
  }

  /* 滾動條美化 */
  .room-list-content::-webkit-scrollbar {
    @apply w-2;
  }
  
  .room-list-content::-webkit-scrollbar-track {
    @apply bg-transparent;
  }
  
  .room-list-content::-webkit-scrollbar-thumb {
    @apply bg-base-300 rounded-full opacity-60 transition-opacity duration-300;
  }
  
  .room-list-content:hover::-webkit-scrollbar-thumb,
  .room-list-content:focus-within::-webkit-scrollbar-thumb {
    @apply opacity-100;
  }
  
  .room-list-content::-webkit-scrollbar-thumb:hover {
    @apply bg-primary opacity-60;
  }
  
  /* 載入更多指示器樣式 */
  .loading-more,
  .load-more-trigger,
  .no-more-data {
    @apply py-2 px-4;
  }

  .loading-more {
    @apply flex justify-center items-center;
  }
</style>