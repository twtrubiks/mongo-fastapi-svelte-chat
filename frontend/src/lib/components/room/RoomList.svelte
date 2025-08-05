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
    rooms?: Room[] | null;
    onRoomSelected?: (data: { room: Room }) => void;
  }
  
  let {
    currentRoomId = null,
    compact = false,
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

<div class="room-list" class:compact>
  <!-- 標題和創建按鈕 -->
  <div class="room-list-header">
    <h2 class="room-list-title">聊天室</h2>
    <div class="flex gap-1">
      <Button
        variant="ghost"
        size="sm"
        onclick={() => showCreateModal = true}
        aria-label="創建聊天室"
        title="創建聊天室"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
      </Button>
      
      <Button
        variant="ghost"
        size="sm"
        onclick={() => showJoinByInviteModal = true}
        aria-label="通過邀請碼加入"
        title="通過邀請碼加入"
      >
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
        </svg>
      </Button>
    </div>
  </div>
  
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
        <Button
          variant="primary"
          size="sm"
          onclick={() => showCreateModal = true}
        >
          創建第一個聊天室
        </Button>
      </div>
    {:else}
      <div class="room-items">
        {#each displayRooms as room (room.id)}
          <button
            class="room-item"
            class:active={currentRoomId === room.id}
            onclick={() => selectRoom(room)}
          >
            <div class="room-avatar">
              <Avatar
                user={{ username: room.name, avatar: undefined }}
                size="md"
              />
            </div>
            
            <div class="room-info">
              <div class="room-name">{room.name}</div>
              {#if room.description}
                <div class="room-description">{room.description}</div>
              {/if}
              <div class="room-meta">
                <span class="room-members">{room.members.length} 成員</span>
                <span class="room-created">
                  {formatDateTime(room.created_at)}
                </span>
              </div>
            </div>
            
            <!-- 房間類型和加入策略徽章 -->
            <div class="room-badges">
              <!-- 房間類型徽章 -->
              <div class="room-type-badge" class:public={room.room_type === 'public'} class:private={room.room_type === 'private'}>
                {getRoomTypeIcon(room.room_type)}
              </div>
              
              <!-- 加入策略徽章 -->
              {#if room.join_policy && room.join_policy !== 'direct'}
                <div class="join-policy-badge" class:password={room.join_policy === 'password'} class:invite={room.join_policy === 'invite'}>
                  {getJoinPolicyIcon(room.join_policy)}
                </div>
              {/if}
            </div>
          </button>
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
      </div>
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
        class="relative bg-base-100 rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto"
        onclick={(e) => e.stopPropagation()}
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
    @apply flex flex-col h-full bg-base-100 border-r border-base-200;
  }
  
  .room-list.compact {
    @apply w-16;
  }
  
  .room-list-header {
    @apply flex items-center justify-between px-4 py-3 bg-base-100 border-b border-base-200 shadow-sm;
  }
  
  .room-list-title {
    @apply text-lg font-bold text-base-content tracking-tight;
  }
  
  .room-list.compact .room-list-title {
    @apply hidden;
  }
  
  .room-list-content {
    @apply flex-1 overflow-y-auto;
    min-height: 0;
    max-height: 100%;
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
    @apply p-2 space-y-1;
  }
  
  .room-item {
    @apply flex items-center w-full p-3 text-left transition-all duration-200 rounded-lg hover:bg-base-200 focus:bg-base-200 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-opacity-20;
  }
  
  .room-item.active {
    @apply bg-primary text-primary-content shadow-md;
  }
  
  .room-list.compact .room-item {
    @apply justify-center p-3 rounded-xl;
  }
  
  .room-avatar {
    @apply flex-shrink-0 mr-3;
  }
  
  .room-list.compact .room-avatar {
    @apply mr-0;
  }
  
  .room-info {
    @apply flex-1 min-w-0;
  }
  
  .room-list.compact .room-info {
    @apply hidden;
  }
  
  .room-name {
    @apply font-semibold text-base text-current truncate;
  }
  
  .room-description {
    @apply text-sm text-current opacity-75 truncate mt-1 leading-tight;
  }
  
  .room-meta {
    @apply flex items-center space-x-3 text-xs text-current opacity-60 mt-2;
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
    @apply flex items-center space-x-1 ml-2;
  }
  
  .room-list.compact .room-badges {
    @apply hidden;
  }
  
  .room-type-badge, .join-policy-badge {
    @apply text-xs p-1 rounded-full text-white font-medium min-w-[24px] h-6 flex items-center justify-center;
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