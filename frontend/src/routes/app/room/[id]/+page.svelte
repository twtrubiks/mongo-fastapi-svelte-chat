<script lang="ts">
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';
  import { roomStore, roomList, roomUsers } from '$lib/stores/room.svelte';
  import { messageStore, messageList, messageLoading } from '$lib/stores/message.svelte';
  import { currentUser, isAuthenticated, authStore } from '$lib/stores/auth.svelte';
  import { wsManager } from '$lib/websocket/manager';
  import { RoomList, RoomHeader, UserList, RoomSettings } from '$lib/components/room';
  import MessageList from '$lib/components/chat/MessageList.svelte';
  import MessageInput from '$lib/components/chat/MessageInput.svelte';
  import MessageSearch from '$lib/components/chat/MessageSearch.svelte';
  import { Toast, ErrorToast, ConnectionStatus } from '$lib/components/ui';
  import { errorStore } from '$lib/stores/errorHandler.svelte';
  import { networkStore } from '$lib/stores/networkStatus.svelte';
  import { messageRetryManager } from '$lib/utils/messageRetry';
  import { apiClient } from '$lib/api/client';
  import { bffApiClient } from '$lib/bff-api-client';
  import { getFileType, getFileTypeLabel, extractFileNameFromUrl, inferMimeTypeFromUrl } from '$lib/utils';
  // import { createRoomContext, setRoomContext } from '$lib/contexts/room-context';
  import type { Room, Message } from '$lib/types';
  
  let currentRoom: Room | null = $state(null);
  let showMobileMenu = $state(false);
  // WebSocket 連接狀態
  let isWebSocketConnected = $state(false);
  // Toast 狀態
  let toastState = $state({
    show: false,
    message: '',
    type: 'info' as 'success' | 'error' | 'warning' | 'info'
  });
  
  // 房間設定狀態
  let showRoomSettings = $state(false);
  let showSearchModal = $state(false);
  let screenWidth = $state(typeof window !== 'undefined' ? window.innerWidth : 1024); // 預設為桌面寬度
  let avatarErrors = $state<Record<string, boolean>>({});  // 追蹤頭像載入錯誤
  let isLoading = $state(true); // 新增載入狀態
  let isInitialized = $state(false); // 追蹤初始化狀態
  let currentLoadingRoomId: string | null = $state(null); // 正在載入的房間 ID
  let messageInputComponent: any; // MessageInput 組件引用（桌面版）
  let mobileMessageInputComponent: any; // MessageInput 組件引用（移動版）
  let desktopMessageListComponent: any; // 桌面端 MessageList 組件引用
  let mobileMessageListComponent: any; // 移動端 MessageList 組件引用
  let messageIdToScrollTo: string | null = $state(null); // 待定位的訊息 ID
  
  // 創建房間 context - 暫時禁用
  // const roomContext = createRoomContext();
  // setRoomContext(roomContext);
  
  let roomId = $derived($page.params.id);
  let isDesktop = $derived(screenWidth >= 768);
  
  // 創建本地的響應式用戶變數，避免重複調用函數
  let user = $derived(currentUser());
  let isAuth = $derived(isAuthenticated());
  let messages = $derived.by(() => {
    // 使用 messageStore.messages 來確保響應式追蹤
    const allMessages = messageStore.messages;
    // console.log('[page.svelte] $derived.by 執行，所有訊息數量:', allMessages.length);
    const filtered = allMessages.filter(msg => msg.room_id === roomId);
    // console.log('[page.svelte] 過濾後訊息數量:', filtered.length, 'roomId:', roomId);
    return filtered;
  });
  let isMessageLoading = $derived(messageLoading());
  let users = $derived(roomUsers());
  
  // 確保只有在初始化完成後才開始渲染
  let canRender = $derived(isInitialized && !isLoading);
  
  // 監控 loading 狀態
  $effect(() => {
  });
  
  // 響應式計算當前聊天室的用戶列表和在線用戶數
  let currentRoomUsers = $derived.by(() => {
    const roomUsersList = users || [];
    return roomUsersList;
  });
  let onlineUserCount = $derived(currentRoomUsers.length);
  
  // 響應式檢查是否有當前用戶
  let hasCurrentUser = $derived(!!user?.id);
  
  // 響應式檢查當前聊天室是否已載入
  let hasCurrentRoom = $derived(!!currentRoom);
  
  // 響應式檢查是否可以刪除當前房間
  let canDeleteCurrentRoom = $derived(currentRoom && user && currentRoom.owner_id === user.id);
  
  // 響應式處理訊息定位
  $effect(() => {
    if (messageIdToScrollTo && messages.length > 0 && !isMessageLoading) {
      const messageListComponent = isDesktop ? desktopMessageListComponent : mobileMessageListComponent;
      
      if (messageListComponent && messageListComponent.scrollToMessage) {
        // 延遲執行以確保 DOM 已更新
        setTimeout(() => {
          const success = messageListComponent.scrollToMessage(messageIdToScrollTo, true);
          
          if (success) {
            showToast('已定位到指定訊息', 'success');
            messageIdToScrollTo = null; // 清除待定位 ID
          } else {
            // 如果失敗，可能需要載入更多訊息
            showToast('訊息可能不在當前載入範圍', 'info');
            messageIdToScrollTo = null; // 避免無限嘗試
          }
        }, 500);
      }
    }
  });
  
  // 響應式檢查 WebSocket 連接狀態 - 已在第28行定義
  
  // 處理房間訪問權限
  async function handleRoomAccess(roomId: string, requirements: any) {
    const room = requirements.room;
    
    // 如果房間可以直接加入
    if (requirements.requirements.canDirectJoin) {
      try {
        await roomStore.joinRoom(roomId);
        // 成功加入後重新載入房間
        const { room } = await roomStore.loadRoom(roomId);
        await messageStore.loadMessages(roomId);
        currentRoom = room;
        showToast('成功加入房間', 'success');
        return;
      } catch (error) {
        console.error('自動加入房間失敗:', error);
      }
    }
    
    // 顯示房間信息和提示用戶需要權限
    showToast(`無法直接訪問房間「${room.name}」，請通過適當方式加入`, 'warning');
    
    // 重定向到房間列表，並可選擇顯示加入該房間的選項
    await redirectToAvailableRoom();
  }
  
  // 重定向到可用的房間
  async function redirectToAvailableRoom() {
    try {
      // 獲取用戶已加入的房間列表
      const userRooms = await roomStore.loadMyRooms();
      
      if (userRooms && userRooms.length > 0) {
        // 重定向到第一個可用房間
        const firstRoom = userRooms[0];
        showToast(`已為您切換到「${firstRoom.name}」`, 'info');
        goto(`/app/room/${firstRoom.id}`);
      } else {
        // 沒有可用房間，重定向到房間列表頁面
        showToast('您還沒有加入任何房間，請先創建或加入一個房間', 'info');
        goto('/app/rooms');
      }
    } catch (error) {
      console.error('獲取用戶房間列表失敗:', error);
      // 如果獲取失敗，直接重定向到房間列表
      showToast('無法載入您的房間列表，請重新登入', 'error');
      goto('/app/rooms');
    }
  }
  
  // 載入聊天室
  async function loadRoom(id: string) {
    // console.log('[Room] loadRoom 函數開始:', { id, currentLoadingRoomId });
    
    // 防止重複載入同一個房間
    if (currentLoadingRoomId === id) {
      // console.log('[Room] 跳過重複載入，房間ID相同:', id);
      return;
    }
    
    currentLoadingRoomId = id;
    
    try {
      // console.log('[Room] loadRoom 開始執行');
      
      // 斷開當前連接
      if (currentRoom && currentRoom.id !== id) {
        // console.log('[Room] 斷開現有連接');
        wsManager.getInstance().disconnect();
      }
      
      // 先檢查房間權限和加入要求
      // console.log('[Room] 檢查房間權限...');
      try {
        const joinRequirements = await roomStore.checkJoinRequirements(id);
        // console.log('[Room] 房間權限檢查完成:', joinRequirements);
        
        // 如果用戶不是成員且房間需要特殊權限，處理加入流程
        if (!joinRequirements.isMember) {
          // console.log('[Room] 用戶非成員，處理加入流程');
          await handleRoomAccess(id, joinRequirements);
          return; // 處理完成後返回，避免繼續載入
        }
      } catch (error: any) {
        console.error('[Room] 檢查房間權限失敗:', error);
        // 如果房間不存在或無法訪問，重定向到房間列表
        await redirectToAvailableRoom();
        return;
      }
      
      // 載入聊天室資料
      // console.log('[Room] 載入聊天室資料...');
      const { room } = await roomStore.loadRoom(id);
      // console.log('[Room] 聊天室資料載入完成:', room);
      
      // 立即設置 currentRoom，讓 UI 可以開始渲染內容
      // console.log('[Room] 立即設置 currentRoom:', room);
      currentRoom = room;
      
      // console.log('[Room] 載入訊息...');
      await messageStore.loadMessages(id);
      // console.log('[Room] 訊息載入完成');
      
      // 重要！在訊息載入後立即更新 lastMessageCount
      lastMessageCount = messages.length;
      
      // 建立 WebSocket 連接
      const token = localStorage.getItem('auth_token');
      // console.log('[Room] 準備建立 WebSocket 連接:', { roomId: id, hasToken: !!token });
      if (token) {
        // console.log('[Room] 開始 WebSocket 連接...');
        await wsManager.getInstance().connect(id, token);
        // console.log('[Room] WebSocket 連接完成');
        isWebSocketConnected = true;
        // 已讀功能已移至響應式 $effect 中處理
      }
      
      // currentRoom 已經在早期設置了，不需要重複設置
      // console.log('[Room] loadRoom 成功完成');
      
    } catch (error) {
      console.error('[Room] 載入聊天室失敗:', error);
      showToast('載入聊天室失敗', 'error');
      // 重定向到聊天室列表
      goto('/app/rooms');
    } finally {
      // console.log('[Room] loadRoom finally 塊執行');
      currentLoadingRoomId = null;
    }
  }
  
  // 選擇聊天室
  async function handleRoomSelected(data: { room: Room }) {
    const { room } = data;
    goto(`/app/room/${room.id}`);
  }
  
  // 發送訊息
  async function handleSendMessage(detail: { content: string, type: string, messageId: string }) {
    // console.log('[handleSendMessage] 開始發送訊息:', detail);
    const { content, type, messageId } = detail;
    
    // console.log('[handleSendMessage] hasCurrentRoom:', hasCurrentRoom, 'currentRoom:', currentRoom);
    if (!hasCurrentRoom) {
      // console.error('[handleSendMessage] 沒有當前房間，取消發送');
      return;
    }
    
    // 確保 type 是有效的類型
    const messageType = type as 'text' | 'image' | 'file';
    
    try {
      // 通過 WebSocket 發送
      // console.log('[handleSendMessage] isWebSocketConnected:', isWebSocketConnected);
      if (isWebSocketConnected) {
        wsManager.getInstance().sendMessage(content, messageType, messageId);
        // console.log('[handleSendMessage] WebSocket 發送結果:', result);
      } else {
        // 如果 WebSocket 未連接，使用 API
        // console.log('[handleSendMessage] 使用 API 發送');
        await messageStore.sendMessage(currentRoom.id, { content, message_type: type });
      }
    } catch (error) {
      console.error('發送訊息失敗:', error);
      showToast('發送訊息失敗', 'error');
    }
  }
  
  
  // 處理檔案上傳完成（FileUpload組件自己完成上傳）
  async function handleFileUploaded(detail: { file: File, url: string, filename: string }) {
    
    await processFileUpload(detail);
  }
  
  // 處理檔案上傳的核心邏輯
  async function processFileUpload(detail: { file: File, url: string, filename: string }) {
    
    // 暴露到全局以供 MessageInput 調用
    if (typeof window !== 'undefined') {
      window.processFileUpload = processFileUpload;
    }
    
    const { file, url, filename } = detail;
    
    if (!currentRoom) {
      console.error('沒有當前房間，無法發送訊息');
      return;
    }
    
    try {
      if (!url) {
        throw new Error('上傳回應中沒有檔案URL');
      }
      
      let fileUrl = url;
      
      // 如果是相對路徑，轉換為完整URL
      if (fileUrl.startsWith('/')) {
        fileUrl = `http://localhost:8000${fileUrl}`;
      }
      
      
      // 決定訊息類型
      const fileType = getFileType(file);
      const messageType = fileType === 'image' ? 'image' : 'file';
      
      // 生成訊息 ID 用於重試追蹤
      const messageId = `file_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // 準備檔案元數據
      const fileMetadata = {
        filename: filename,
        fileSize: file.size,
        mimeType: file.type || inferMimeTypeFromUrl(fileUrl),
        originalName: file.name,
        uploadedAt: new Date().toISOString()
      };
      
      // 添加到重試佇列
      messageRetryManager.addToRetryQueue({
        id: messageId,
        content: fileUrl,
        type: messageType,
        metadata: fileMetadata
      });
      
      // 發送檔案訊息
      if (isWebSocketConnected) {
        const result = wsManager.getInstance().sendMessage(fileUrl, messageType, messageId, fileMetadata);
        
        // 檢查 3 秒後消息是否出現
        setTimeout(() => {
          const fileMessages = $state.snapshot(messages).filter(msg => msg.message_type === messageType);
        }, 3000);
      } else {
        const messageData = { 
          content: fileUrl, 
          message_type: messageType 
        };
        await messageStore.sendMessage(currentRoom.id, messageData);
      }
      
      showToast(`${getFileTypeLabel(file)}上傳成功`, 'success');
    } catch (error) {
      console.error('發送檔案訊息失敗:', error);
      showToast('發送檔案訊息失敗', 'error');
    }
  }
  
  // 處理錯誤
  function handleError(detail: { message: string }) {
    const { message } = detail;
    showToast(message, 'error');
  }
  
  // 處理頭像載入錯誤
  function handleAvatarError(userId: string) {
    avatarErrors = { ...avatarErrors, [userId]: true };
  }
  
  // 顯示通知
  function showToast(message: string, type: 'success' | 'error' | 'warning' | 'info') {
    toastState = {
      show: true,
      message,
      type
    };
  }
  
  // 切換移動端菜單
  function toggleMobileMenu() {
    showMobileMenu = !showMobileMenu;
  }
  
  // 離開聊天室
  async function handleLeaveRoom(event: CustomEvent | { room: Room }) {
    const room = 'detail' in event ? event.detail.room : event.room;
    
    if (confirm(`確定要離開聊天室「${room.name}」嗎？`)) {
      try {
        await roomStore.leaveRoom(room.id);
        wsManager.getInstance().disconnect();
        currentRoom = null;
        messageStore.clearMessages();
        goto('/app/rooms');
        showToast('已離開聊天室', 'info');
      } catch (error) {
        console.error('離開聊天室失敗:', error);
        showToast('離開聊天室失敗', 'error');
      }
    }
  }
  
  // 刪除聊天室
  async function handleDeleteRoom(event: CustomEvent | { room: Room }) {
    const room = 'detail' in event ? event.detail.room : event.room;
    
    if (!room || !user) return;
    
    
    // 檢查是否為房間擁有者
    if (room.owner_id !== user.id) {
      showToast('只有房間擁有者可以刪除聊天室', 'error');
      return;
    }
    
    // 確認對話框
    const confirmed = confirm(
      `確定要刪除聊天室「${room.name}」嗎？\n\n` +
      `此操作無法復原，將刪除所有聊天記錄。`
    );
    
    if (!confirmed) return;
    
    try {
      // 調用 BFF 端點刪除房間
      const response = await fetch(`/api/rooms/${room.id}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        const result = await response.json();
        // 成功刪除，斷開 WebSocket 並導航回房間列表
        wsManager.getInstance().disconnect();
        currentRoom = null;
        messageStore.clearMessages();
        showToast(result.data?.message || '聊天室已刪除', 'success');
        await goto('/app/rooms');
      } else {
        const error = await response.json();
        showToast(`刪除失敗：${error.error?.message || '未知錯誤'}`, 'error');
      }
    } catch (error) {
      showToast('刪除失敗，請稍後重試', 'error');
    }
  }
  
  // 用戶點擊
  function handleUserClick(event: CustomEvent) {
    const { user } = event.detail;
    // TODO: 實作用戶資料查看功能
  }
  
  // 處理搜尋訊息選擇
  function handleSelectMessage(message: Message) {
    showSearchModal = false;
    
    // 選擇正確的 MessageList 組件引用
    const messageListComponent = isDesktop ? desktopMessageListComponent : mobileMessageListComponent;
    
    // 滾動到選定的訊息
    if (messageListComponent && messageListComponent.scrollToMessage) {
      const success = messageListComponent.scrollToMessage(message.id, true);
      if (success) {
        showToast('已定位到選定訊息', 'success');
      } else {
        showToast('訊息可能不在當前載入的範圍內', 'warning');
      }
    } else {
      showToast('無法定位到訊息', 'error');
    }
  }
  
  // WebSocket 錯誤處理
  function setupWebSocketErrorHandling() {
    const ws = wsManager.getInstance();
    
    // 監聽連接狀態
    ws.on('disconnected', (data) => {
      const { code, reason } = data;
      if (code !== 1000) { // 非正常關閉
        errorStore.showConnectionError({
          label: '重新連接',
          handler: () => {
            ws.manualReconnect().catch((error) => {
              console.error('Manual reconnect failed:', error);
            });
          }
        });
      }
    });
    
    // 監聽重連失敗
    ws.on('reconnect_failed', (data) => {
      const { attempts } = data;
      errorStore.showReconnectFailed(attempts, {
        label: '重試',
        handler: () => {
          ws.manualReconnect().catch((error) => {
            console.error('Manual reconnect failed:', error);
          });
        }
      });
    });
    
    // 監聽訊息錯誤
    ws.on('message_error', (data) => {
      if (data.temp_id) {
        // 不顯示錯誤 toast，讓 MessageInput 組件處理重試 UI
      } else {
        // 沒有 temp_id 的通用錯誤
        errorStore.showMessageSendError('', {
          label: '重試',
          handler: () => {
          }
        });
      }
    });
    
    // 監聽網路狀態
    ws.on('offline', () => {
      errorStore.showNetworkError();
    });
    
    // 網路狀態變化監聽已移至組件層級的 $effect
  }
  
  // 記錄上次載入的房間 ID，避免重複載入
  let lastLoadedRoomId: string | null = null;
  
  // 監聽路由變化和認證狀態
  $effect(() => {
    // console.log('[Room] $effect 觸發:', { roomId, isAuthenticated, lastLoadedRoomId });
    if (roomId && isAuthenticated) {
      
      // 避免重複載入同一個房間
      if (lastLoadedRoomId !== roomId) {
        // console.log('[Room] 開始載入新房間:', roomId);
        lastLoadedRoomId = roomId;
        loadRoom(roomId);
        setupWebSocketErrorHandling();
      } else {
        // console.log('[Room] 跳過重複載入房間:', roomId);
      }
    } else {
      // console.log('[Room] 條件不滿足，跳過房間載入');
    }
  });
  
  // 監聽認證狀態變化 - 如果未認證則重定向
  $effect(() => {
    if (!isAuthenticated && browser) {
      goto('/login');
    }
  });
  
  // 監聽網路狀態變化
  $effect(() => {
    if (!networkStore.isOnline) {
      errorStore.showNetworkError({
        label: '重新檢查',
        handler: () => {
          // 嘗試重新連接
          if (currentRoom) {
            loadRoom(currentRoom.id);
          }
        }
      });
    }
  });
  
  // 檢查認證狀態
  async function checkAuthentication() {
    // console.log('[Room] checkAuthentication: isAuthenticated =', isAuth);
    
    // 如果未認證，重定向到登入頁面
    if (!isAuth) {
      // console.log('[Room] 用戶未認證，嘗試恢復認證狀態');
      // 嘗試從 localStorage 恢復認證狀態
      const token = localStorage.getItem('auth_token');
      if (token) {
        // console.log('[Room] 找到 token，嘗試驗證');
        try {
          await authStore.verify();
          // console.log('[Room] 認證驗證成功');
          return true; // 認證成功
        } catch (error) {
          console.error('[Room] 認證驗證失敗:', error);
        }
      }
      
      // 重定向到登入頁面，並保存當前路由用於登入後返回
      const currentPath = $page.url.pathname;
      // console.log('[Room] 重定向到登入頁面');
      goto(`/login?redirect=${encodeURIComponent(currentPath)}`);
      return false;
    }
    // console.log('[Room] 用戶已認證');
    return true; // 已認證
  }

  // 追蹤已處理的房間ID，避免重複執行
  let processedRoomId = $state<string | null>(null);
  // 追蹤最後一次檢查的訊息數量 - 初始值設為 -1 以避免錯誤觸發
  let lastMessageCount = $state(-1);
  // 用於管理已讀操作的 timeout
  let markAsReadTimeoutId: number | null = null;
  
  // 執行已讀操作的函數
  async function executeMarkAsRead(roomId: string, forceRefresh: boolean = false) {
    // 先嘗試通過 WebSocket 標記已讀
    const wsResult = wsManager.getInstance().markRoomMessagesRead(roomId);
    
    try {
      // 強制刷新或第一次載入時，從 API 獲取最新通知
      const response = await fetch('/api/notifications/', {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        const allNotifications = data.notifications || [];
        
        // 從 notificationStore 導入並設置通知
        const { notificationStore } = await import('$lib/stores/notification.svelte');
        notificationStore.setNotifications(allNotifications);
        
        // 找到與當前房間相關的未讀通知
        const roomNotifications = allNotifications.filter(n => 
          n.room_id === roomId && n.status === 'UNREAD'
        );
        
        // 逐個標記為已讀
        for (const notification of roomNotifications) {
          try {
            const readResponse = await fetch(`/api/notifications/${notification.id}/read`, {
              method: 'POST',
              credentials: 'include'
            });
            
            if (readResponse.ok) {
              notificationStore.markAsRead(notification.id);
              // 給一點時間讓響應式更新生效
              await new Promise(resolve => setTimeout(resolve, 50));
            }
          } catch (err) {
            console.error('標記通知已讀失敗:', err);
          }
        }
        
        // 如果是強制刷新，再次從 API 獲取最新狀態
        if (forceRefresh) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          const refreshResponse = await fetch('/api/notifications/', {
            credentials: 'include'
          });
          if (refreshResponse.ok) {
            const refreshData = await refreshResponse.json();
            notificationStore.setNotifications(refreshData.notifications || []);
          }
        }
      }
    } catch (error) {
      console.error('處理已讀通知失敗:', error);
    }
  }
  
  // 響應式處理自動已讀功能 - 進入房間或切換房間時
  $effect(() => {
    if (!browser || !currentRoom || !isWebSocketConnected) return;
    
    // 當進入新房間或 WebSocket 重新連接時，標記已讀
    const roomId = currentRoom.id;
    
    // 如果已經處理過這個房間，跳過（除非 WebSocket 重新連接）
    if (processedRoomId === roomId && isWebSocketConnected) {
      return;
    }
    
    
    // 延遲執行已讀操作，確保訊息已載入
    const timeoutId = setTimeout(async () => {
      await executeMarkAsRead(roomId);
      // 標記這個房間已處理
      processedRoomId = roomId;
      // 記錄當前訊息數量 - 重要！這裡要初始化
      lastMessageCount = messages.length;
    }, 500);
    
    // 清理函數
    return () => {
      clearTimeout(timeoutId);
    };
  });
  
  // 響應式處理自動已讀功能 - 收到新訊息時
  $effect(() => {
    if (!browser || !currentRoom || !isWebSocketConnected) return;
    
    const currentMessageCount = messages.length;
    const roomId = currentRoom.id;
    
    // 如果訊息數量增加（收到新訊息）
    if (currentMessageCount > lastMessageCount && lastMessageCount >= 0) {
      // 清除之前的 timeout（如果存在）
      if (markAsReadTimeoutId !== null) {
        clearTimeout(markAsReadTimeoutId);
      }
      
      // 延遲執行已讀操作，給通知系統足夠的時間處理
      markAsReadTimeoutId = setTimeout(async () => {
        // 強制刷新以確保獲取最新的通知
        await executeMarkAsRead(roomId, true);
        markAsReadTimeoutId = null;
      }, 3000); // 增加延遲到 3 秒，確保通知系統已經處理完新訊息
    }
    
    // 更新訊息計數（避免錯過變化）
    lastMessageCount = currentMessageCount;
  });
  
  // 組件銷毀時清除 timeout
  $effect(() => {
    return () => {
      if (markAsReadTimeoutId !== null) {
        clearTimeout(markAsReadTimeoutId);
      }
    };
  });

  // 響應式處理 URL 參數中的訊息定位
  $effect(() => {
    if (!browser) return;
    
    // 監聽 page 變化，處理 URL 查詢參數
    const searchParams = $page.url.searchParams;
    const targetMessageId = searchParams.get('message');
    
    
    if (targetMessageId && targetMessageId !== messageIdToScrollTo) {
      // console.log('[Room] 檢測到 URL 中的 message 參數:', targetMessageId);
      // 設置待定位的訊息 ID，讓響應式邏輯處理
      messageIdToScrollTo = targetMessageId;
      
      // 清理 URL 參數，避免重複觸發
      const newUrl = $page.url.pathname;
      // console.log('[Room] 清理 URL 參數，跳轉到:', newUrl);
      goto(newUrl, { replaceState: true });
    }
  });

  // 清理和螢幕尺寸監聽
  onMount(async () => {
    // console.log('[Room] onMount 開始');
    
    // 首先檢查認證狀態
    // console.log('[Room] 檢查認證狀態...');
    const isAuth = await checkAuthentication();
    // console.log('[Room] 認證狀態:', isAuth);
    if (!isAuth) {
      // console.log('[Room] 未認證，返回');
      return; // 如果未認證，已重定向，直接返回
    }
    
    // 監聽螢幕尺寸變化
    const updateScreenWidth = () => {
      screenWidth = window.innerWidth;
    };
    
    updateScreenWidth();
    window.addEventListener('resize', updateScreenWidth);
    
    // 監聽 WebSocket 連接狀態變化
    const ws = wsManager.getInstance();
    
    const handleConnected = () => {
      // console.log('[Room] WebSocket 已連接');
      isWebSocketConnected = true;
    };
    
    const handleDisconnected = () => {
      // console.log('[Room] WebSocket 已斷開');
      isWebSocketConnected = false;
    };
    
    ws.on('connected', handleConnected);
    ws.on('disconnected', handleDisconnected);
    
    // 檢查當前連接狀態
    if (ws.isConnected()) {
      isWebSocketConnected = true;
    }
    
    // 設置初始化和載入完成
    // console.log('[Room] 設置初始化狀態');
    isInitialized = true;
    isLoading = false;
    // console.log('[Room] canRender 狀態:', { isInitialized, isLoading, canRender });
    
    return () => {
      ws.off('connected', handleConnected);
      ws.off('disconnected', handleDisconnected);
      wsManager.getInstance().disconnect();
      isWebSocketConnected = false;
      window.removeEventListener('resize', updateScreenWidth);
      
      // 清理重試管理器
      messageRetryManager.clearAll();
    };
  });
</script>

<div class="chat-app">
  {#if !canRender}
    <!-- 載入中指示器 -->
    <div class="flex items-center justify-center h-screen" transition:fade>
      <div class="loading loading-spinner loading-lg"></div>
    </div>
  {:else if isDesktop}
    <!-- 桌面端布局 - 使用 Svelte 條件渲染 -->
    <div class="desktop-layout" transition:fade={{ duration: 200 }}>
      <!-- 左側：聊天室列表 -->
      <div class="room-sidebar" transition:fly={{ x: -300, duration: 300 }}>
        <RoomList
          currentRoomId={currentRoom?.id}
          onRoomSelected={handleRoomSelected}
        />
      </div>
      
      <!-- 中間：聊天區域 -->
      <div class="chat-area" transition:fade={{ duration: 200, delay: 100 }}>
        <!-- 聊天室資訊欄 -->
        <div class="room-header bg-base-50 border-b border-base-300 px-6 py-2">
          <div class="flex items-center justify-between">
            <div class="flex-1 min-w-0">
              <h1 class="text-lg font-bold text-primary flex items-center">
                <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-1.586l-4.414 4.414z" />
                </svg>
                {currentRoom ? currentRoom.name : '載入中...'}
              </h1>
              <div class="text-xs text-base-content opacity-60 mt-1 flex items-center space-x-3">
                <span class="flex items-center">
                  <svg class="w-3 h-3 mr-1 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <circle cx="10" cy="10" r="10"/>
                  </svg>
                  {onlineUserCount} 人在線
                </span>
                <span>•</span>
                <span>#{roomId.substring(0, 8)}...</span>
              </div>
            </div>
            <div class="flex items-center space-x-2">
              <!-- 搜尋按鈕 -->
              <button 
                class="btn btn-ghost btn-xs text-base-content opacity-70 hover:opacity-100"
                disabled={!hasCurrentRoom || currentLoadingRoomId !== null}
                onclick={() => showSearchModal = true}
                aria-label="搜尋訊息"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </button>
              
              <!-- 更多選項下拉菜單 -->
              <div class="dropdown dropdown-end">
                <button class="btn btn-ghost btn-xs text-base-content opacity-70 hover:opacity-100" tabindex="0">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                  </svg>
                </button>
                
                <ul class="dropdown-content z-10 menu p-2 shadow bg-base-100 rounded-box w-52">
                  <li>
                    <button onclick={() => showRoomSettings = true}>
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.50 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      聊天室設定
                    </button>
                  </li>
                  <li>
                    <button onclick={() => showToast('成員功能開發中', 'info')}>
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
                      </svg>
                      成員列表
                    </button>
                  </li>
                  <li><hr class="my-1" /></li>
                  <li>
                    <button 
                      onclick={() => currentRoom && handleLeaveRoom({ room: currentRoom })}
                      class="text-error"
                      disabled={!currentRoom}
                    >
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      離開聊天室
                    </button>
                  </li>
                  {#if canDeleteCurrentRoom}
                    <li>
                      <button 
                        onclick={() => currentRoom && handleDeleteRoom({ room: currentRoom })}
                        class="text-error"
                      >
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                        刪除聊天室
                      </button>
                    </li>
                  {/if}
                </ul>
              </div>
            </div>
          </div>
        </div>
        
        <div class="chat-content">
          <!-- 訊息列表區域 - 固定高度並允許內部滾動 -->
          <div class="message-container">
            {#if hasCurrentRoom}
              <MessageList
                bind:this={desktopMessageListComponent}
                messages={messages}
                loading={isMessageLoading}
                roomId={currentRoom.id}
              />
            {:else}
              <div class="h-full flex flex-col items-center justify-center p-8 text-center">
                <div class="empty-chat-icon mb-6">
                  <svg class="w-16 h-16 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <h2 class="text-2xl font-bold text-base-content mb-4">載入中...</h2>
                <!-- Debug 資訊 -->
                <div class="text-sm text-base-content/60 space-y-1">
                  <p>Debug: 當前房間 = {currentRoom ? currentRoom.name : 'null'}</p>
                  <p>認證狀態 = {isAuthenticated}</p>
                  <p>房間 ID = {roomId}</p>
                  <p>初始化狀態 = {isInitialized}</p>
                  <p>載入狀態 = {isLoading}</p>
                </div>
              </div>
            {/if}
          </div>
          
          <!-- 輸入框區域 - 總是顯示 -->
          <div class="input-area flex-shrink-0 border-t border-base-200">
            <MessageInput
              onSend={handleSendMessage}
              onFileUploaded={handleFileUploaded}
              onError={handleError}
              bind:this={messageInputComponent}
            />
          </div>
        </div>
      </div>
      
      <!-- 右側：用戶列表 - 暫時隱藏 -->
      <!-- <div class="user-sidebar" transition:fly={{ x: 300, duration: 300 }}>
      </div> -->
    </div>
  {:else}
    <!-- 移動端布局 - 使用 Svelte 條件渲染 -->
    <div class="mobile-layout" transition:fade={{ duration: 200 }}>
      <RoomHeader
        room={currentRoom}
        {onlineUserCount}
        {showMobileMenu}
        currentUserId={user?.id}
        onToggleMenu={toggleMobileMenu}
        onLeave={handleLeaveRoom}
        onDelete={handleDeleteRoom}
        onSettings={() => showRoomSettings = true}
        onMembers={() => showToast('成員功能開發中', 'info')}
        onSearch={() => showSearchModal = true}
      />
      
      <!-- 移動端菜單 -->
      {#if showMobileMenu}
        <div class="mobile-menu" transition:fade={{ duration: 200 }}>
          <div class="mobile-menu-backdrop" onclick={toggleMobileMenu} onkeydown={(e) => { if (e.key === 'Escape') toggleMobileMenu(); }} role="button" tabindex="0" aria-label="關閉菜單"></div>
          <div class="mobile-menu-content" transition:fly={{ x: -300, duration: 300 }}>
            <RoomList
              currentRoomId={currentRoom?.id}
              onRoomSelected={handleRoomSelected}
            />
          </div>
        </div>
      {/if}
      
      <!-- 聊天內容 -->
      <div class="mobile-chat-content" transition:fade={{ duration: 200, delay: 100 }}>
        {#if hasCurrentRoom}
          <MessageList
            bind:this={mobileMessageListComponent}
            messages={messages}
            loading={isMessageLoading}
            roomId={currentRoom.id}
          />
          
          <MessageInput
            onSend={handleSendMessage}
            onFileUploaded={handleFileUploaded}
            onError={handleError}
            bind:this={mobileMessageInputComponent}
          />
        {:else}
          <div class="empty-chat">
            <div class="empty-chat-icon">
              <svg class="w-16 h-16 text-base-content opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h2 class="empty-chat-title">載入中...</h2>
        </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- 連接狀態指示器 -->
<ConnectionStatus />

<!-- 房間設定模態框 -->
<RoomSettings 
  bind:show={showRoomSettings}
  room={currentRoom}
  onClose={() => showRoomSettings = false}
  onUpdate={(updatedRoom) => {
    currentRoom = updatedRoom;
    showToast('房間設定已更新', 'success');
  }}
/>

<!-- 通知 -->
<Toast
  bind:show={toastState.show}
  type={toastState.type}
  message={toastState.message}
  onClose={() => {
    toastState.show = false;
  }}
/>

<!-- 錯誤處理 -->
{#if errorStore.currentError}
  <ErrorToast
    show={true}
    title={errorStore.currentError.title}
    message={errorStore.currentError.message}
    type={errorStore.currentError.type}
    action={errorStore.currentError.action}
    autoHide={errorStore.currentError.autoHide}
    duration={errorStore.currentError.duration}
    onHide={() => {
      if (errorStore.currentError) {
        errorStore.removeError(errorStore.currentError.id);
      }
    }}
  />
{/if}

<!-- 搜尋模態框 -->
{#if currentRoom}
  <MessageSearch 
    roomId={currentRoom.id}
    bind:isOpen={showSearchModal}
    onClose={() => showSearchModal = false}
    onSelectMessage={handleSelectMessage}
  />
{/if}

<style>
  .chat-app {
    @apply h-full bg-base-100;
  }
  
  /* 桌面端布局 */
  .desktop-layout {
    @apply h-full flex overflow-hidden;
  }
  
  .room-sidebar {
    @apply w-80 border-r border-base-200 flex-shrink-0 h-full;
  }
  
  /* 滾動條美化 - 默認隱藏，懸停或聚焦時顯示 */
  .room-sidebar :global(.room-list) {
    @apply h-full;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar {
    @apply w-2;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar-track {
    @apply bg-base-200;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar-thumb {
    @apply bg-base-300 rounded-full transition-all duration-300;
  }
  
  .room-sidebar :global(.room-list-content):hover::-webkit-scrollbar-thumb {
    @apply bg-base-content opacity-30;
  }
  
  .room-sidebar :global(.room-list-content)::-webkit-scrollbar-thumb:hover {
    @apply bg-primary;
  }
  
  .chat-area {
    @apply flex-1 flex flex-col min-w-0 h-full overflow-hidden;
  }
  
  .room-header {
    @apply flex-shrink-0;
    height: 80px; /* 固定高度 */
  }
  
  .chat-content {
    @apply flex-1 flex flex-col overflow-hidden;
  }
  
  .message-container {
    @apply flex-1 overflow-hidden;
  }
  
  .input-area {
    @apply flex-shrink-0;
    min-height: 100px; /* 最小高度給輸入框 */
    max-height: 150px; /* 最大高度限制 */
  }
  
  .user-sidebar {
    @apply w-0 border-l border-base-200 flex-shrink-0 hidden;
  }
  
  /* 移動端布局 */
  .mobile-layout {
    @apply h-full flex flex-col;
  }
  
  .mobile-chat-content {
    @apply flex-1 flex flex-col min-h-0;
  }
  
  .mobile-menu {
    @apply fixed inset-0 z-50 flex;
  }
  
  .mobile-menu-backdrop {
    @apply absolute inset-0 bg-black opacity-50;
  }
  
  .mobile-menu-content {
    @apply relative w-80 max-w-sm bg-base-100 shadow-xl;
  }
  
  /* 空狀態 */
  .empty-chat {
    @apply flex-1 flex flex-col items-center justify-center p-8 text-center;
  }
  
  .empty-chat-icon {
    @apply mb-6;
  }
  
  .empty-chat-title {
    @apply text-2xl font-bold text-base-content mb-4;
  }
  
  .empty-chat-description {
    @apply text-base-content opacity-60 max-w-md;
  }
</style>