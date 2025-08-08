<script lang="ts">
  import { onMount } from 'svelte';
  import { roomStore, roomList, roomLoading, hasMoreRooms, loadingMoreRooms } from '$lib/stores';
  import { Button, Loading, Avatar } from '$lib/components/ui';
  import { formatDateTime } from '$lib/utils';
  import JoinRoomModal from './JoinRoomModal.svelte';
  import type { Room, RoomType, JoinPolicy } from '$lib/types';
  
  interface Props {
    currentRoomId?: string | null;
    compact?: boolean;
    mobileMode?: boolean;
    rooms?: Room[] | null;
    onRoomSelected?: (data: { room: Room }) => void;
  }
  
  let {
    currentRoomId = null,
    compact = false,
    mobileMode = false,
    rooms = null,
    onRoomSelected = undefined
  }: Props = $props();
  
  // 總是使用 store 中的 rooms（server rooms 會初始化到 store 中）
  // 直接訪問 roomStore.state.rooms 以確保響應式更新
  let displayRooms = $derived.by(() => {
    const rooms = roomStore.state.rooms;
    return rooms || [];
  });
  let isRoomLoading = $derived(roomLoading());
  let hasMore = $derived(hasMoreRooms());
  let isLoadingMore = $derived(loadingMoreRooms());
  
  let showCreateModal = $state(false);
  let newRoomName = $state('');
  let newRoomDescription = $state('');
  let newRoomType = $state<RoomType>('public');
  let newPassword = $state('');
  let showNewPassword = $state(false);
  let isCreating = $state(false);
  
  // 加入房間相關狀態
  let showJoinModal = $state(false);
  let selectedRoomToJoin = $state<Room | null>(null);
  
  // 邀請碼顯示相關狀態
  let showInviteCodeModal = $state(false);
  let currentInviteCode = $state<string>('');
  
  // 邀請碼加入相關狀態
  let showJoinByInviteModal = $state(false);
  let inviteCodeInput = $state<string>('');
  let isJoiningByInvite = $state(false);
  
  // 待處理的房間選擇（用於邀請碼顯示後）
  let pendingRoomSelection = $state<Room | null>(null);
  
  // 避免重複函數調用的衍生變數
  let trimmedRoomName = $derived(newRoomName.trim());
  let trimmedPassword = $derived(newPassword.trim());
  let isPasswordValid = $derived(trimmedPassword.length === 0 || trimmedPassword.length >= 6);
  
  // 當房間類型改為私人時，清空密碼欄位
  $effect(() => {
    if (newRoomType === 'private') {
      newPassword = '';
    }
  });
  
  
  
  // 載入聊天室列表
  async function loadRooms() {
    try {
      if (rooms && rooms.length > 0) {
        // 如果有外部傳入的 rooms，先初始化 store
        roomStore.initializeWithServerRooms(rooms);
        // 如果已經有外部傳入的房間，就不需要重新載入
        return;
      }
      
      // 只有在沒有外部傳入房間時才載入
      const loadedRooms = await roomStore.loadRooms(true); // reset = true，重新載入
    } catch (error) {
      console.error('[RoomList] 載入房間列表失敗:', error);
      
      // 如果是網路錯誤，5秒後自動重試
      if (shouldRetryError(error)) {
        // 5秒後自動重試載入房間列表
        setTimeout(() => {
          loadRooms();
        }, 5000);
      }
    }
  }

  // 判斷是否應該重試的錯誤
  function shouldRetryError(error: any): boolean {
    const status = error.status || error.response?.status;
    return status >= 500 || 
           error.code === 'ECONNREFUSED' || 
           error.code === 'ENOTFOUND' ||
           error.message?.includes('Network Error') ||
           error.message?.includes('timeout') ||
           error.message?.includes('Failed to fetch');
  }

  // 載入更多聊天室
  async function loadMoreRooms() {
    try {
      await roomStore.loadMoreRooms();
    } catch (error) {
      console.error('[RoomList] 載入更多房間失敗:', error);
      
      // 如果是網路錯誤，3秒後自動重試
      if (shouldRetryError(error)) {
        // 3秒後自動重試載入更多房間
        setTimeout(() => {
          loadMoreRooms();
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
    
    // 當滾動到底部附近時載入更多
    if (scrollHeight - scrollTop - clientHeight < 100 && !isLoadingMore && hasMore) {
      await loadMoreRooms();
    }
  }
  
  // 創建新聊天室
  async function createRoom() {
    if (!trimmedRoomName) return;
    
    // 驗證密碼長度
    if (!isPasswordValid) {
      alert('密碼至少需要 6 個字符');
      return;
    }
    
    isCreating = true;
    try {
      // 根據房間類型和密碼設置自動決定加入策略
      let joinPolicy: JoinPolicy;
      if (newRoomType === 'private') {
        joinPolicy = 'invite';  // 私人房間自動設為邀請制
      } else if (trimmedPassword) {
        joinPolicy = 'password';  // 公開房間但有密碼設為密碼制
      } else {
        joinPolicy = 'direct';  // 公開房間無密碼為直接加入
      }
      
      const room = await roomStore.createRoom({
        name: trimmedRoomName,
        description: newRoomDescription.trim() || undefined,
        is_public: newRoomType === 'public',
        room_type: newRoomType,
        join_policy: joinPolicy,
        max_members: 100,
        // 只有公開房間才允許設定密碼
        password: newRoomType === 'public' ? (trimmedPassword || undefined) : undefined,
      });
      
      // 重置表單
      resetCreateForm();
      showCreateModal = false;
      
      // 如果是邀請制房間，顯示邀請碼，延後跳轉
      if (room.join_policy === 'invite' && room.invite_code) {
        currentInviteCode = room.invite_code;
        showInviteCodeModal = true;
        // 暫存房間信息，等邀請碼模態框關閉後再跳轉
        pendingRoomSelection = room;
      } else {
        // 非邀請制房間直接跳轉
        onRoomSelected?.({ room });
      }
    } catch (error: any) {
      
      // 顯示具體的錯誤訊息
      let errorMessage = '創建房間時發生錯誤';
      
      // 處理不同類型的錯誤
      if (error.response?.data?.detail) {
        // FastAPI 錯誤格式
        errorMessage = error.response.data.detail;
      } else if (error.response?.data?.error?.message) {
        // BFF 錯誤格式
        errorMessage = error.response.data.error.message;
      } else if (error.message) {
        // 一般錯誤
        errorMessage = error.message;
      }
      
      alert(errorMessage);
    } finally {
      isCreating = false;
    }
  }
  
  // 重置創建表單
  function resetCreateForm() {
    newRoomName = '';
    newRoomDescription = '';
    newRoomType = 'public';
    newPassword = '';
    showNewPassword = false;
  }
  
  // 複製邀請碼到剪貼板
  async function copyInviteCode() {
    try {
      await navigator.clipboard.writeText(currentInviteCode);
    } catch (err) {
      // 如果 navigator.clipboard 不可用，使用備用方法
      fallbackCopyToClipboard(currentInviteCode);
    }
  }
  
  // 備用複製方法（針對較舊的瀏覽器）
  function fallbackCopyToClipboard(text: string) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
    } catch (err) {
      // 靜默處理錯誤
    }
    document.body.removeChild(textArea);
  }
  
  // 通過邀請碼加入房間
  async function joinByInviteCode() {
    if (!inviteCodeInput.trim()) {
      return;
    }
    
    isJoiningByInvite = true;
    try {
      // 先驗證邀請碼並獲取房間信息
      const result = await roomStore.validateInvitation(inviteCodeInput.trim());
      
      if (result.room) {
// 嘗試加入房間
        await roomStore.joinRoom(result.room.id, { invite_code: inviteCodeInput.trim() });
        
        // 成功後關閉模態框並重置
        showJoinByInviteModal = false;
        inviteCodeInput = '';
        
        // 跳轉到房間
        onRoomSelected?.({ room: result.room });
      }
    } catch (error: any) {
      
      // 顯示友好的錯誤信息
      alert(`邀請碼驗證失敗：${error.message}`);
    } finally {
      isJoiningByInvite = false;
    }
  }
  
  // 選擇聊天室
  function selectRoom(room: Room) {
    // 檢查是否需要特殊加入流程
    if (needsSpecialJoin(room)) {
      selectedRoomToJoin = room;
      showJoinModal = true;
    } else {
      onRoomSelected?.({ room });
    }
  }
  
  // 檢查是否需要特殊加入流程
  function needsSpecialJoin(room: Room): boolean {
    // 如果已經是成員，直接進入
    // 這裡簡化處理，實際應該檢查當前用戶是否在 room.members 中
    // 私人房間或有密碼的房間需要特殊加入流程
    return room.room_type === 'private' || room.join_policy === 'password' || room.join_policy === 'invite';
  }
  
  // 加入房間成功回調
  function handleJoinSuccess(room: Room) {
    showJoinModal = false;
    selectedRoomToJoin = null;
    onRoomSelected?.({ room });
  }
  
  // 關閉加入模態框
  function handleJoinClose() {
    showJoinModal = false;
    selectedRoomToJoin = null;
  }
  
  // 獲取房間類型圖標
  function getRoomTypeIcon(roomType?: RoomType): string {
    switch (roomType) {
      case 'public': return '🌍';
      case 'private': return '🔒';
      default: return '🌍';
    }
  }
  
  // 獲取加入策略圖標
  function getJoinPolicyIcon(joinPolicy?: JoinPolicy): string {
    switch (joinPolicy) {
      case 'password': return '🔑';
      case 'invite': return '📧';
      default: return '';
    }
  }

  // 初始化載入
  onMount(() => {
    loadRooms();
  });
</script>

<div class="room-list" class:compact class:mobile-mode={mobileMode}>
  <!-- 標題和操作按鈕 -->
  {#if mobileMode}
    <!-- 移動端：使用 navbar 組件，增大按鈕尺寸提升觸控體驗 -->
    <div class="navbar bg-base-100 border-b border-base-200 sticky top-0 z-50 min-h-[3.5rem]">
      <div class="navbar-start flex-1">
        <span class="text-lg font-bold px-2">聊天室</span>
      </div>
      <div class="navbar-end flex-none">
        <div class="flex gap-1">
          <button
            class="btn btn-ghost btn-square"
            onclick={() => showCreateModal = true}
            aria-label="創建聊天室"
            title="創建聊天室"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
          </button>
          <button
            class="btn btn-ghost btn-square"
            onclick={() => showJoinByInviteModal = true}
            aria-label="加入房間"
            title="加入房間"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  {:else if !compact}
    <!-- 桌面端：原有的標題欄 -->
    <div class="room-list-header">
      <h2 class="room-list-title">聊天室</h2>
      <div class="btn-group">
        <button
          class="btn btn-sm btn-ghost btn-square"
          onclick={() => showCreateModal = true}
          aria-label="創建聊天室"
          title="創建聊天室"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </button>
        
        <button
          class="btn btn-sm btn-ghost btn-square"
          onclick={() => showJoinByInviteModal = true}
          aria-label="通過邀請碼加入"
          title="通過邀請碼加入"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
          </svg>
        </button>
      </div>
    </div>
  {/if}
  
  <!-- 聊天室列表 -->
  <div class="room-list-content" onscroll={handleScroll}>
    {#if isRoomLoading && displayRooms.length === 0}
      <Loading text="載入聊天室..." />
    {:else if displayRooms.length === 0}
      <div class="empty-state">
        <div class="empty-state-icon">
          <svg class="w-8 h-8 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <p class="empty-state-text">暫無聊天室</p>
        <button
          class="btn btn-primary btn-sm"
          onclick={() => showCreateModal = true}
        >
          創建第一個聊天室
        </button>
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
                user={{ username: room.name, avatar: undefined }}
                size={mobileMode ? "xs" : "sm"}
              />
              
              <div class="flex-1 min-w-0 text-left">
                <div class="font-semibold truncate {mobileMode ? 'text-sm' : ''}">{room.name}</div>
                <div class="text-xs opacity-60">
                  👥 {room.members.length} 成員
                </div>
              </div>
              
              <!-- 徽章 -->
              <div class="flex gap-1">
                {#if room.room_type === 'private'}
                  <span class="badge badge-xs">🔒</span>
                {/if}
                {#if room.join_policy === 'password'}
                  <span class="badge badge-xs">🔑</span>
                {:else if room.join_policy === 'invite'}
                  <span class="badge badge-xs">📧</span>
                {/if}
              </div>
            </button>
          </li>
        {/each}
        
        <!-- 載入更多指示器 -->
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
      </ul>
    {/if}
  </div>
  
  <!-- 創建聊天室模態框 -->
  {#if showCreateModal}
    <!-- 使用 Svelte 5 的 teleport 概念，將 modal 渲染到 body -->
    <div 
      class="fixed inset-0 flex items-center justify-center"
      style="z-index: 9999 !important;"
      onclick={() => { showCreateModal = false; resetCreateForm(); }}
    >
      <!-- 背景遮罩 -->
      <div class="absolute inset-0 bg-black bg-opacity-50 backdrop-blur-sm"></div>
      
      <!-- Modal 內容 -->
      <div 
        class="relative bg-base-100 rounded-lg shadow-xl max-w-2xl w-[calc(100%-2rem)] md:w-full mx-4 max-h-[85vh] overflow-y-auto"
        onclick={(e) => e.stopPropagation()}
        style="max-width: min(40rem, calc(100vw - 2rem));"
      >
        <button
          class="btn btn-sm btn-circle btn-ghost absolute right-2 top-2 z-10"
          onclick={() => {
            showCreateModal = false;
            resetCreateForm();
          }}
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        
        <div class="p-6">
          <h3 class="font-bold text-lg mb-4 pr-8">創建新聊天室</h3>
          
          <div class="form-control mb-4">
            <label class="label" for="room-name">
              <span class="label-text">聊天室名稱</span>
            </label>
            <input
              id="room-name"
              type="text"
              placeholder="請輸入聊天室名稱"
              class="input input-bordered w-full"
              bind:value={newRoomName}
              maxlength="50"
            />
          </div>
          
          <div class="form-control mb-4">
            <label class="label" for="room-description">
              <span class="label-text">描述（可選）</span>
            </label>
            <textarea
              id="room-description"
              placeholder="請輸入聊天室描述"
              class="textarea textarea-bordered w-full"
              bind:value={newRoomDescription}
              maxlength="200"
            ></textarea>
          </div>
          
          <!-- 房間類型選擇 -->
          <div class="form-control mb-4">
            <label class="label">
              <span class="label-text">房間類型</span>
            </label>
            <div class="space-y-3">
              <label class="flex items-start space-x-3 p-3 border rounded-lg cursor-pointer hover:bg-base-200 transition-colors" class:bg-primary={newRoomType === 'public'} class:text-primary-content={newRoomType === 'public'}>
                <input
                  type="radio"
                  name="room-type"
                  value="public"
                  bind:group={newRoomType}
                  class="radio radio-primary mt-1"
                />
                <div class="flex-1">
                  <div class="font-medium">🌍 公開房間</div>
                  <div class="text-sm opacity-70">任何人都可以看到並加入，可選密碼保護</div>
                </div>
              </label>
              <label class="flex items-start space-x-3 p-3 border rounded-lg cursor-pointer hover:bg-base-200 transition-colors" class:bg-primary={newRoomType === 'private'} class:text-primary-content={newRoomType === 'private'}>
                <input
                  type="radio"
                  name="room-type"
                  value="private"
                  bind:group={newRoomType}
                  class="radio radio-primary mt-1"
                />
                <div class="flex-1">
                  <div class="font-medium">🔒 私人房間</div>
                  <div class="text-sm opacity-70">僅通過邀請碼加入</div>
                </div>
              </label>
            </div>
          </div>
          
          <!-- 密碼設置（僅公開房間可用） -->
          {#if newRoomType === 'public'}
          <div class="form-control mb-4">
            <label class="label">
              <span class="label-text">房間密碼（可選）</span>
              <span class="label-text-alt">設置密碼以增加安全性</span>
            </label>
            <div class="relative">
              <input
                id="room-password"
                type={showNewPassword ? 'text' : 'password'}
                placeholder="留空表示無密碼保護"
                class="input input-bordered w-full pr-12"
                bind:value={newPassword}
                maxlength="50"
              />
              <button
                type="button"
                class="absolute inset-y-0 right-0 flex items-center pr-3"
                onclick={() => showNewPassword = !showNewPassword}
                disabled={isCreating}
                aria-label={showNewPassword ? '隱藏密碼' : '顯示密碼'}
              >
                {#if showNewPassword}
                  <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L5.636 5.636m4.242 4.242L15.12 15.12m-4.242-4.242L5.636 5.636m9.484 9.484L15.12 15.12M9.878 9.878l4.242 4.242" />
                  </svg>
                {:else}
                  <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                {/if}
              </button>
            </div>
            {#if trimmedPassword && trimmedPassword.length < 6}
              <div class="label">
                <span class="label-text-alt text-error">密碼至少需要 6 個字符</span>
              </div>
            {/if}
          </div>
          {/if}
          
          <div class="flex justify-end space-x-2 mt-6 pt-4 border-t border-base-200">
            <Button
              variant="ghost"
              onclick={() => {
                showCreateModal = false;
                resetCreateForm();
              }}
              disabled={isCreating}
            >
              取消
            </Button>
            <Button
              variant="primary"
              onclick={createRoom}
              loading={isCreating}
              disabled={!trimmedRoomName || isCreating || !isPasswordValid}
            >
              創建
            </Button>
          </div>
        </div>
      </div>
    </div>
  {/if}
  
  <!-- 加入房間模態框 -->
  {#if selectedRoomToJoin}
    <JoinRoomModal
      room={selectedRoomToJoin}
      show={showJoinModal}
      onClose={handleJoinClose}
      onSuccess={handleJoinSuccess}
    />
  {/if}
  
  <!-- 邀請碼顯示模態框 -->
  {#if showInviteCodeModal}
    <div class="modal modal-open">
      <div class="modal-box">
        <h3 class="font-bold text-lg mb-4">🎉 房間創建成功！</h3>
        
        <div class="mb-6">
          <p class="mb-3">您的房間邀請碼如下，請分享給其他人以便他們加入房間：</p>
          
          <div class="bg-base-200 p-4 rounded-lg mb-4">
            <div class="flex items-center justify-between">
              <code class="text-lg font-mono text-primary flex-1 mr-3">{currentInviteCode}</code>
              <button
                class="btn btn-outline btn-sm"
                onclick={copyInviteCode}
                title="複製邀請碼"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                </svg>
                複製
              </button>
            </div>
          </div>
          
          <div class="text-sm text-base-content/70">
            <p class="mb-2">📝 使用方法：</p>
            <ul class="list-disc list-inside space-y-1 ml-2">
              <li>將邀請碼分享給其他用戶</li>
              <li>他們可以通過「加入房間」功能輸入此邀請碼</li>
              <li>或者直接提供邀請碼讓他們手動輸入</li>
            </ul>
          </div>
        </div>
        
        <div class="modal-action">
          <button
            class="btn btn-primary"
            onclick={() => {
              showInviteCodeModal = false;
              currentInviteCode = '';
              
              // 如果有待處理的房間選擇，現在執行跳轉
              if (pendingRoomSelection) {
                onRoomSelected?.({ room: pendingRoomSelection });
                pendingRoomSelection = null;
              }
            }}
          >
            知道了
          </button>
        </div>
      </div>
    </div>
  {/if}
  
  <!-- 通過邀請碼加入房間模態框 -->
  {#if showJoinByInviteModal}
    <div class="modal modal-open">
      <div class="modal-box">
        <h3 class="font-bold text-lg mb-4">🔑 通過邀請碼加入房間</h3>
        
        <div class="mb-6">
          <p class="mb-4 text-sm text-base-content/70">
            請輸入其他用戶分享給您的邀請碼來加入私人房間：
          </p>
          
          <div class="form-control mb-4">
            <label class="label">
              <span class="label-text">邀請碼</span>
            </label>
            <input
              type="text"
              placeholder="請輸入邀請碼"
              class="input input-bordered w-full"
              bind:value={inviteCodeInput}
              onkeydown={(e) => e.key === 'Enter' && !isJoiningByInvite && joinByInviteCode()}
              disabled={isJoiningByInvite}
            />
          </div>
          
          <div class="text-xs text-base-content/50">
            💡 邀請碼通常是由房間創建者分享的一串字符
          </div>
        </div>
        
        <div class="modal-action">
          <button
            class="btn"
            onclick={() => {
              showJoinByInviteModal = false;
              inviteCodeInput = '';
            }}
            disabled={isJoiningByInvite}
          >
            取消
          </button>
          
          <button
            class="btn btn-primary"
            onclick={joinByInviteCode}
            disabled={!inviteCodeInput.trim() || isJoiningByInvite}
          >
            {#if isJoiningByInvite}
              <span class="loading loading-spinner loading-sm"></span>
              加入中...
            {:else}
              加入房間
            {/if}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
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
  
  .room-list-header {
    @apply flex items-center justify-between bg-base-100 border-b border-base-200 shadow-sm flex-shrink-0;
    /* 調整內邊距確保按鈕可見 */
    padding: 0.5rem 0.75rem;
    width: 100%;
    box-sizing: border-box;
    min-height: 56px;
  }
  
  .room-list-title {
    @apply text-base font-bold text-base-content tracking-tight;
    /* 防止標題過長 */
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  /* 按鈕組樣式 */
  .room-list-header .btn-group {
    @apply flex gap-1 flex-shrink-0;
  }
  
  /* 確保按鈕在移動端正確顯示 */
  .room-list-header .btn-square {
    @apply w-8 h-8 min-h-8;
  }
  
  .room-list.compact .room-list-title {
    @apply hidden;
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
  
  .room-list.mobile-mode .navbar {
    @apply flex-none;
    min-height: 3.5rem;
  }
  
  /* 確保 navbar 按鈕有足夠的空間和可見性 */
  .room-list.mobile-mode .navbar-end {
    padding-right: 0.25rem;
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
  
  /* 移動端按鈕樣式 - 增大觸控區域 */
  .room-list.mobile-mode .btn-square {
    @apply w-11 h-11 min-h-[2.75rem];
  }
  
  .room-list.mobile-mode .btn-square svg {
    @apply w-6 h-6;
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
  
  .room-items {
    /* 確保項目列表使用全寬 */
    @apply space-y-1;
    width: 100%;
  }
  
  .room-item {
    @apply flex items-center w-full text-left transition-all duration-200 rounded-lg hover:bg-base-200 focus:bg-base-200 focus:outline-none;
    padding: 0.625rem;
    margin-bottom: 0.25rem;
    box-sizing: border-box;
    /* 防止內容溢出 */
    overflow: hidden;
  }
  
  .room-item.active {
    @apply bg-primary text-primary-content shadow-md;
  }
  
  .room-list.compact .room-item {
    @apply justify-center p-3 rounded-xl;
  }
  
  .room-avatar {
    @apply flex-shrink-0;
    /* 設定適當的右邊距 */
    margin-right: 0.75rem;
    /* 確保頭像不被裁剪 */
    min-width: 40px;
  }
  
  .room-list.compact .room-avatar {
    @apply mr-0;
  }
  
  .room-info {
    @apply flex-1 min-w-0;
    /* 確保文字不會超出 */
    overflow: hidden;
  }
  
  .room-list.compact .room-info {
    @apply hidden;
  }
  
  .room-name {
    @apply font-semibold text-base text-current truncate;
    /* 確保名稱不會超出 */
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .room-description {
    @apply text-sm text-current opacity-75 truncate mt-1 leading-tight;
    /* 確保描述不會太長 */
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  /* 手機版隱藏描述以節省空間 */
  @media (max-width: 640px) {
    .room-description {
      display: none;
    }
  }
  
  .room-meta {
    @apply flex items-center space-x-2 text-xs text-current opacity-60 mt-1;
    /* 隱藏時間戳以節省空間 */
  }
  
  /* 手機版隱藏創建時間 */
  @media (max-width: 768px) {
    .room-created {
      display: none;
    }
  }
  
  .room-members {
    @apply flex items-center space-x-1;
  }
  
  .room-members:before {
    content: "👥";
    @apply text-xs;
  }
  
  .room-created {
    @apply flex items-center space-x-1;
  }
  
  .room-created:before {
    content: "📅";
    @apply text-xs;
  }
  
  .room-badges {
    @apply flex items-center space-x-1;
    /* 減少左邊距 */
    margin-left: 0.25rem;
    flex-shrink: 0;
  }
  
  .room-list.compact .room-badges {
    @apply hidden;
  }
  
  .room-type-badge, .join-policy-badge {
    @apply text-xs rounded-full text-white font-medium flex items-center justify-center;
    /* 減小徽章尺寸 */
    padding: 0.125rem;
    min-width: 20px;
    height: 20px;
    font-size: 0.625rem;
  }
  
  /* 房間類型徽章顏色 */
  .room-type-badge.public {
    @apply bg-green-500;
  }
  
  .room-type-badge.private {
    @apply bg-red-500;
  }
  
  /* 加入策略徽章顏色 */
  .join-policy-badge.password {
    @apply bg-orange-500;
  }
  
  .join-policy-badge.invite {
    @apply bg-purple-500;
  }
  
  /* 活動聊天室的特殊樣式 */
  .room-item.active .room-name {
    @apply text-primary-content font-bold;
  }
  
  .room-item.active .room-description {
    @apply text-primary-content opacity-90;
  }
  
  .room-item.active .room-meta {
    @apply text-primary-content opacity-80;
  }
  
  .room-item.active .room-type-badge,
  .room-item.active .join-policy-badge {
    @apply brightness-110 shadow-sm;
  }
  
  /* Hover 效果增強 */
  .room-item:not(.active):hover {
    @apply shadow-sm transform scale-[1.02];
  }
  
  /* 滾動條美化 - 讓 scrollbar 更明顯 */
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
  
  /* 創建按鈕美化 */
  .room-list-header button {
    @apply rounded-full p-2 hover:bg-base-200 transition-colors duration-200 text-base-content;
  }
  
  .room-list-header button svg {
    @apply text-base-content;
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