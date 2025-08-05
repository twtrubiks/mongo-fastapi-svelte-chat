<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { roomStore, currentRoom, roomList } from '$lib/stores/room.svelte';
  import { messageStore, messageList, messageLoading } from '$lib/stores/message.svelte';
  import { isAuthenticated } from '$lib/stores/auth.svelte';
  import { wsManager } from '$lib/websocket/manager';
  import { RoomList, RoomHeader, UserList } from '$lib/components/room';
  import MessageList from '$lib/components/chat/MessageList.svelte';
  import MessageInput from '$lib/components/chat/MessageInput.svelte';
  import { Toast } from '$lib/components/ui';
  import type { Room, Message } from '$lib/types';

  let { data } = $props<{ 
    data: {
      rooms: Room[]; 
      error: string | null;
      // 從父 layout 繼承的用戶數據
      user: any;
    }
  }>();
  
  let showMobileMenu = $state(false);
  let showToastVisible = $state(false);
  let toastMessage = $state('');
  let toastType: 'success' | 'error' | 'warning' | 'info' = $state('info');
  
  // 創建本地的響應式變數，避免重複調用函數
  let currentRoomData = $derived(currentRoom());
  let rooms = $derived(roomList());
  let messages = $derived(messageList());
  let isMessageLoading = $derived(messageLoading());
  let roomUsers = $derived(roomStore.state?.users || []);
  let onlineCount = $derived(roomUsers.length);
  
  // 選擇聊天室
  async function handleRoomSelected(data: { room: Room }) {
    const { room } = data;
    
    if (currentRoomData?.id === room.id) return;
    
    // 斷開當前連接
    if (currentRoomData) {
      wsManager.getInstance().disconnect();
    }
    
    try {
      // 載入聊天室資料
      await roomStore.loadRoom(room.id);
      await messageStore.loadMessages(room.id);
      
      // 建立 WebSocket 連接
      const token = localStorage.getItem('auth_token');
      if (token) {
        await wsManager.getInstance().connect(room.id, token);
      }
      
      // 使用 store 更新當前房間
      roomStore.setCurrentRoom(room);
      showMobileMenu = false;
      
      // 更新 URL
      goto(`/app/room/${room.id}`, { replaceState: true });
      
    } catch (error) {
      // 加入聊天室失敗
      showToast('加入聊天室失敗', 'error');
    }
  }
  
  // 發送訊息
  async function handleSendMessage(detail: { content: string, type: string, messageId: string }) {
    const { content, type } = detail;
    
    if (!currentRoomData) return;
    
    // 確保 type 是有效的類型
    const messageType = type as 'text' | 'image' | 'file';
    
    try {
      // 通過 WebSocket 發送
      if (wsManager.getInstance().isConnected()) {
        wsManager.getInstance().sendMessage(content, messageType);
      } else {
        // 如果 WebSocket 未連接，使用 API
        await messageStore.sendMessage(currentRoomData.id, { content, message_type: type as 'text' | 'image' });
      }
    } catch (error) {
      // 發送訊息失敗
      showToast('發送訊息失敗', 'error');
    }
  }
  
  // 處理圖片上傳
  async function handleImageUpload(detail: { file: File, url: string, filename: string }) {
    const { file } = detail;
    
    if (!currentRoomData) return;
    
    try {
      // TODO: 實作圖片上傳到伺服器
      // const response = await apiClient.files.upload(file);
      // const imageUrl = response.url;
      
      // 暫時使用本地 URL
      const imageUrl = URL.createObjectURL(file);
      
      // 發送圖片訊息
      if (wsManager.getInstance().isConnected()) {
        wsManager.getInstance().sendMessage(imageUrl, 'image');
      } else {
        await messageStore.sendMessage(currentRoomData.id, { 
          content: imageUrl, 
          message_type: 'image' 
        });
      }
      
      showToast('圖片上傳成功', 'success');
    } catch (error) {
      // 圖片上傳失敗
      showToast('圖片上傳失敗', 'error');
    }
  }
  
  // 處理錯誤
  function handleError(detail: { message: string }) {
    const { message } = detail;
    showToast(message, 'error');
  }
  
  // 顯示通知
  function showToast(message: string, type: typeof toastType) {
    toastMessage = message;
    toastType = type;
    showToastVisible = true;
  }
  
  // 切換移動端菜單
  function toggleMobileMenu() {
    showMobileMenu = !showMobileMenu;
  }
  
  // 離開聊天室
  async function handleLeaveRoom(data: { room: Room | null }) {
    const { room } = data;
    
    if (!room) return;
    
    if (confirm(`確定要離開聊天室「${room.name}」嗎？`)) {
      try {
        await roomStore.leaveRoom(room.id);
        
        if (currentRoomData?.id === room.id) {
          wsManager.getInstance().disconnect();
          roomStore.setCurrentRoom(null);
          messageStore.clearMessages();
          goto('/app/rooms', { replaceState: true });
        }
        
        showToast('已離開聊天室', 'info');
      } catch (error) {
        // 離開聊天室失敗
        showToast('離開聊天室失敗', 'error');
      }
    }
  }
  
  // 用戶點擊
  function handleUserClick(event: { user: User }) {
    const { user } = event;
    // TODO: 實作用戶資料查看功能
  }
  
  // 處理服務端載入的錯誤
  $effect(() => {
    if (data.error) {
      showToast(data.error, 'error');
    }
  });
  
  // 監聽認證狀態變化 - 如果未認證則重定向
  $effect(() => {
    if (!isAuthenticated && browser) {
      goto('/login');
    }
  });
  
  // 載入初始聊天室
  onMount(async () => {
    try {
      // 先載入所有可用房間到 store
      await roomStore.loadRooms();
      
      // 然後載入用戶已加入的房間
      // TODO: loadMyRooms 會覆蓋所有房間，需要修復
      // const userRooms = await roomStore.loadMyRooms();
      const userRooms: any[] | null = null; // 暫時停用
      
      if (userRooms && userRooms.length > 0) {
        handleRoomSelected({ room: userRooms[0] });
      } else {
        // 如果用戶沒有加入任何房間，檢查 store 中是否有可直接加入的公開房間
        const allRooms = rooms;
        
        let foundRoom = false;
        if (allRooms.length > 0) {
          for (const room of allRooms) {
            try {
              // 檢查房間加入要求
              const requirements = await roomStore.checkJoinRequirements(room.id);
              
              if (requirements.isMember) {
                // 如果已經是成員，直接選擇
                handleRoomSelected({ room });
                foundRoom = true;
                return;
              } else if (requirements.requirements.canDirectJoin) {
                // 如果可以直接加入，嘗試加入
                await roomStore.joinRoom(room.id);
                handleRoomSelected({ room });
                foundRoom = true;
                return;
              }
            } catch (error) {
              continue;
            }
          }
        }
        
        // 如果沒有找到可加入的房間，建立 lobby 連接以接收房間創建通知
        if (!foundRoom) {
          const token = localStorage.getItem('auth_token');
          if (token) {
            try {
              await wsManager.getInstance().connect('lobby', token);
              console.log('[Rooms Page] 已連接到 lobby 以接收房間更新');
            } catch (error) {
              console.error('[Rooms Page] 連接到 lobby 失敗:', error);
            }
          }
        }
      }
    } catch (error) {
      console.error('載入房間列表失敗:', error);
      showToast('載入房間列表失敗', 'error');
    }
  });
  
  // 組件銷毀時清理
  onDestroy(() => {
    // 如果沒有選擇具體房間（只連接到 lobby），則斷開連接
    if (!currentRoomData && wsManager.getInstance().isConnected()) {
      wsManager.getInstance().disconnect();
      console.log('[Rooms Page] 斷開 lobby 連接');
    }
  });
</script>

<div class="chat-app">
  <!-- 桌面端布局 -->
  <div class="desktop-layout hidden md:flex">
    <!-- 左側：聊天室列表 -->
    <div class="room-sidebar">
      <RoomList
        rooms={rooms}
        currentRoomId={currentRoomData?.id || null}
        onRoomSelected={handleRoomSelected}
      />
    </div>
    
    <!-- 中間：聊天區域 -->
    <div class="chat-area">
      <RoomHeader
        room={currentRoomData}
        onlineCount={onlineCount}
        onLeave={handleLeaveRoom}
        onSettings={() => showToast('設定功能開發中', 'info')}
        onMembers={() => showToast('成員功能開發中', 'info')}
        onSearch={() => showToast('搜尋功能開發中', 'info')}
      />
      
      <div class="chat-content">
        {#if currentRoomData}
          <MessageList
            messages={messages}
            loading={isMessageLoading}
            roomId={currentRoomData.id}
          />
          
          <MessageInput
            onSend={handleSendMessage}
            onFileUploaded={handleImageUpload}
            onError={handleError}
          />
        {:else}
          <div class="empty-chat">
            <div class="empty-chat-icon">
              <svg class="w-16 h-16 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h2 class="empty-chat-title">歡迎使用聊天室</h2>
            <p class="empty-chat-description">選擇一個聊天室開始聊天，或創建一個新的聊天室</p>
          </div>
        {/if}
      </div>
    </div>
    
    <!-- 右側：用戶列表 -->
    <div class="user-sidebar">
      <UserList
        users={roomUsers}
        currentUserId={data.user?.id}
        onUserClick={handleUserClick}
      />
    </div>
  </div>
  
  <!-- 移動端布局 -->
  <div class="mobile-layout md:hidden">
    <RoomHeader
      room={currentRoomData}
      onlineCount={onlineCount}
      onToggleMenu={toggleMobileMenu}
      onLeave={handleLeaveRoom}
      onSettings={() => showToast('設定功能開發中', 'info')}
      onMembers={() => showToast('成員功能開發中', 'info')}
      onSearch={() => showToast('搜尋功能開發中', 'info')}
    />
    
    <!-- 移動端菜單 -->
    {#if showMobileMenu}
      <div class="mobile-menu">
        <div class="mobile-menu-backdrop" onclick={toggleMobileMenu} onkeydown={(e) => { if (e.key === 'Escape') toggleMobileMenu(); }} role="button" tabindex="0" aria-label="關閉菜單"></div>
        <div class="mobile-menu-content">
          <RoomList
            currentRoomId={currentRoomData?.id || null}
            onRoomSelected={handleRoomSelected}
          />
        </div>
      </div>
    {/if}
    
    <!-- 聊天內容 -->
    <div class="mobile-chat-content">
      {#if currentRoomData}
        <MessageList
          messages={messages}
          loading={isMessageLoading}
          roomId={currentRoomData.id}
        />
        
        <MessageInput
          onSend={handleSendMessage}
          onFileUploaded={handleImageUpload}
          onError={handleError}
        />
      {:else}
        <div class="empty-chat">
          <div class="empty-chat-icon">
            <svg class="w-16 h-16 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h2 class="empty-chat-title">歡迎使用聊天室</h2>
          <p class="empty-chat-description">點擊右上角菜單選擇聊天室</p>
        </div>
      {/if}
    </div>
  </div>
</div>

<!-- 通知 -->
<Toast
  bind:show={showToastVisible}
  type={toastType}
  message={toastMessage}
  onClose={() => showToastVisible = false}
/>

<style>
  .chat-app {
    @apply h-screen bg-gradient-to-br from-base-200 to-base-100 overflow-hidden;
  }
  
  /* 桌面端布局 */
  .desktop-layout {
    @apply h-full shadow-inner;
  }
  
  .room-sidebar {
    @apply w-80 flex-shrink-0 shadow-lg z-10 h-full overflow-hidden;
  }
  
  /* 滾動條美化 - 默認隱藏，懸停或聚焦時顯示 */
  .room-sidebar :global(.room-list) {
    @apply h-full;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar {
    @apply w-1;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar-track {
    @apply bg-transparent;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar-thumb {
    @apply bg-base-300 rounded-full opacity-0 transition-opacity duration-300;
  }
  
  .room-sidebar :global(.room-list-content):hover::-webkit-scrollbar-thumb,
  .room-sidebar :global(.room-list-content):focus-within::-webkit-scrollbar-thumb {
    @apply opacity-100;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar-thumb:hover {
    @apply bg-base-content opacity-30;
  }
  
  .chat-area {
    @apply flex-1 flex flex-col min-w-0 bg-gradient-to-b from-base-200 to-base-100;
  }
  
  .chat-content {
    @apply flex-1 flex flex-col min-h-0 relative;
  }
  
  .chat-content::before {
    content: '';
    @apply absolute inset-0 bg-gradient-to-br pointer-events-none;
    background: linear-gradient(to bottom right, rgba(var(--p) / 0.05), rgba(var(--s) / 0.05));
  }
  
  .user-sidebar {
    @apply w-64 flex-shrink-0 shadow-lg z-10;
  }
  
  /* 移動端布局 */
  .mobile-layout {
    @apply h-full flex flex-col bg-gradient-to-b from-base-200 to-base-100;
  }
  
  .mobile-chat-content {
    @apply flex-1 flex flex-col min-h-0;
  }
  
  .mobile-menu {
    @apply fixed inset-0 z-50 flex backdrop-blur-sm;
    animation: menu-appear 0.2s ease-out;
  }
  
  @keyframes menu-appear {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }
  
  .mobile-menu-backdrop {
    @apply absolute inset-0 bg-black/50;
  }
  
  .mobile-menu-content {
    @apply relative w-80 max-w-sm bg-base-100 shadow-2xl border-r border-base-200;
    animation: menu-slide 0.3s ease-out;
  }
  
  @keyframes menu-slide {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(0);
    }
  }
  
  /* 空狀態優化 */
  .empty-chat {
    @apply flex-1 flex flex-col items-center justify-center p-12 text-center relative;
  }
  
  .empty-chat::before {
    content: '';
    @apply absolute inset-0 bg-gradient-to-br rounded-3xl border border-base-200;
    background: linear-gradient(to bottom right, rgba(var(--p) / 0.1), rgba(var(--s) / 0.1));
  }
  
  .empty-chat-icon {
    @apply mb-8 p-6 bg-base-200 rounded-full shadow-md relative;
  }
  
  .empty-chat-title {
    @apply text-3xl font-bold text-base-content mb-6 relative bg-gradient-to-r from-primary to-secondary bg-clip-text text-transparent;
  }
  
  .empty-chat-description {
    @apply text-base-content opacity-70 max-w-md text-lg leading-relaxed relative;
  }
  
  /* 增強視覺層次 */
  .room-sidebar,
  .user-sidebar {
    @apply relative;
  }
  
  .room-sidebar::after,
  .user-sidebar::after {
    content: '';
    @apply absolute top-0 bottom-0 w-px bg-gradient-to-b from-transparent via-base-300 to-transparent;
  }
  
  .room-sidebar::after {
    @apply right-0;
  }
  
  .user-sidebar::after {
    @apply left-0;
  }
  
  /* 響應式設計增強 */
  @media (max-width: 1024px) {
    .room-sidebar {
      @apply w-72;
    }
    
    .user-sidebar {
      @apply w-56;
    }
  }
  
  @media (max-width: 768px) {
    .chat-app {
      @apply bg-base-100;
    }
    
    .mobile-chat-content {
      @apply bg-base-100;
    }
  }
  
  /* 深色模式優化 */
  @media (prefers-color-scheme: dark) {
    .chat-app {
      @apply bg-gradient-to-br from-base-300 to-base-200;
    }
    
    .empty-chat-title {
      @apply text-base-content;
      background: none;
      -webkit-background-clip: unset;
      -webkit-text-fill-color: unset;
    }
  }
</style>