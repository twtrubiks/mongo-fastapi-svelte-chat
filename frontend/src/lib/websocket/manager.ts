import { messageStore, roomStore, notificationStore, browserNotificationManager, soundNotificationManager, notificationSettings, currentUser, messageStatusStore } from '$lib/stores';
import type { WebSocketMessage, Message, User } from '$lib/types';
import type { Notification } from '$lib/stores/notification.svelte';
import { transformNotification } from '$lib/bff-utils';
// get 函數已不需要，Svelte 5 使用直接訪問

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10; // 增加重連次數，對手機更友好
  private baseReconnectDelay = 1000;
  private currentReconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private heartbeatInterval: number | null = null;
  private reconnectTimeout: number | null = null;
  private isReconnecting = false;
  private connectionState: 'disconnected' | 'connecting' | 'connected' = 'disconnected';
  private lastConnectTime = 0;
  private connectionId = 0;
  private lastRoomUsersTime = 0; // 追蹤最後收到 room_users 事件的時間
  private pingTimeout: number | null = null; // 添加 ping 超時檢測
  private lastPingTime = 0; // 記錄最後 ping 時間

  private roomId: string | null = null;
  private token: string | null = null;

  // 事件監聽器
  private eventListeners: {
    [key: string]: Array<(data: any) => void>;
  } = {};

  constructor() {
    // 只在瀏覽器環境中初始化事件監聽器
    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
      // 監聽頁面可見性變化
      document.addEventListener('visibilitychange', this.handleVisibilityChange.bind(this));

      // 監聽網路狀態變化
      window.addEventListener('online', this.handleOnline.bind(this));
      window.addEventListener('offline', this.handleOffline.bind(this));
    }
  }

  // 連接 WebSocket
  connect(roomId: string, token: string): Promise<void> {
    // console.log('[WebSocket] 開始連接流程:', { roomId, tokenLength: token?.length || 0 });

    return new Promise((resolve, reject) => {
      this.roomId = roomId;
      this.token = token;

      if (this.ws?.readyState === WebSocket.OPEN) {
        // console.log('[WebSocket] 關閉現有連接');
        this.disconnect();
      }

      // 防止連接太頻繁（只在重連時檢查，正常連接不限制）
      const timeSinceLastConnect = Date.now() - this.lastConnectTime;
      if (this.isReconnecting && timeSinceLastConnect < 500) {
        console.warn('[WebSocket] 連接嘗試太頻繁，拒絕連接');
        reject(new Error('連接嘗試太頻繁，請稍後再試'));
        return;
      }

      this.lastConnectTime = Date.now();
      this.connectionId++;
      const currentConnectionId = this.connectionId;

      // console.log('[WebSocket] 設置連接狀態為 connecting, connectionId:', currentConnectionId);
      this.setConnectionState('connecting');

      // 動態獲取 WebSocket URL
      let wsUrl: string;

      // 檢查是否有環境變數配置的 WebSocket URL
      if (import.meta.env.PUBLIC_WS_URL && window.location.hostname === 'localhost') {
        // 開發環境且有配置時使用配置的 URL
        wsUrl = `${import.meta.env.PUBLIC_WS_URL}/ws/${roomId}?token=${token}`;
      } else {
        // 動態計算 WebSocket URL
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;

        // 根據不同情況決定端口
        let port = '';
        if (host === 'localhost' || host === '127.0.0.1') {
          // 本地開發環境，連接到後端的 8000 端口
          port = ':8000';
        } else if (host.startsWith('192.168.') || host.startsWith('10.') || host.startsWith('172.')) {
          // 局域網 IP，連接到後端的 8000 端口
          port = ':8000';
        } else if (window.location.port) {
          // 其他情況，如果有端口就使用當前端口
          port = `:${window.location.port}`;
        }

        wsUrl = `${protocol}//${host}${port}/ws/${roomId}?token=${token}`;
      }

      // console.log('[WebSocket] 連接 URL:', wsUrl.replace(/token=[^&]+/, 'token=***'));

      try {
        // console.log('[WebSocket] 創建 WebSocket 實例');
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          // console.log('[WebSocket] 連接已打開, connectionId:', currentConnectionId);

          // 檢查是否還是當前連接
          if (currentConnectionId !== this.connectionId) {
            console.warn('[WebSocket] 連接ID不匹配，忽略此連接:', {
              current: currentConnectionId,
              latest: this.connectionId
            });
            return;
          }

          // console.log('[WebSocket] 設置連接狀態為 connected');
          this.setConnectionState('connected');
          this.reconnectAttempts = 0;
          this.currentReconnectDelay = this.baseReconnectDelay;
          this.isReconnecting = false;
          this.clearReconnectTimeout();
          // console.log('[WebSocket] 啟動心跳檢測');
          this.startHeartbeat();
          // console.log('[WebSocket] 發送 connected 事件');
          this.emit('connected');
          // console.log('[WebSocket] 連接初始化完成');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const data: WebSocketMessage = JSON.parse(event.data);
            this.handleMessage(data);
          } catch (error) {
            console.error('[WebSocket] 解析訊息失敗:', error);
          }
        };

        this.ws.onclose = (event) => {

          // 檢查是否還是當前連接
          if (currentConnectionId !== this.connectionId) {
            // console.log('[WebSocket] 忽略舊連接的關閉事件');
            return;
          }

          this.setConnectionState('disconnected');
          this.stopHeartbeat();
          this.emit('disconnected', { code: event.code, reason: event.reason });

          // 判斷是否需要重連
          if (!event.wasClean && this.shouldReconnect(event.code)) {
            // console.log('[WebSocket] 排程重連');
            this.scheduleReconnect();
          } else {
            // console.log('[WebSocket] 不需要重連');
          }
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocket] 連接錯誤:', error);
          this.emit('error', error);

          if (this.connectionState === 'connecting') {
            console.error('[WebSocket] 初始連接失敗');
            reject(new Error('WebSocket connection failed'));
          }
        };

        // 連接超時處理
        // console.log('[WebSocket] 設置10秒連接超時');
        setTimeout(() => {
          if (this.connectionState === 'connecting') {
            console.error('[WebSocket] 連接超時');
            this.disconnect();
            reject(new Error('WebSocket connection timeout'));
          }
        }, 10000);

      } catch (error) {
        console.error('[WebSocket] 創建 WebSocket 實例失敗:', error);
        this.setConnectionState('disconnected');
        reject(error);
      }
    });
  }

  // 斷開連接
  disconnect() {
    this.connectionId++; // 增加連接 ID，使舊連接失效
    this.clearReconnectTimeout();

    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.setConnectionState('disconnected');
    this.stopHeartbeat();
    this.isReconnecting = false;
    this.reconnectAttempts = 0;
    this.currentReconnectDelay = this.baseReconnectDelay;

    // 重置 room_users 事件時間，避免影響新房間的事件處理
    this.lastRoomUsersTime = 0;

    // 注意：不要在這裡清空用戶列表，因為可能導致 UI 閃爍
    // 新的房間會在載入時自動更新用戶列表
    // roomStore.setUsers([]);

    // 清除房間已讀請求緩存
    this.roomReadRequestCache.clear();

    // 暫停一下再清除 roomId 和 token，避免重連期間的競爭條件
    setTimeout(() => {
      this.roomId = null;
      this.token = null;
    }, 100);
  }

  // 發送訊息
  sendMessage(content: string, type: 'text' | 'image' | 'file' = 'text', messageId?: string, metadata?: any) {
    if (!this.isConnected()) {
      console.error('[WebSocket] 訊息發送失敗 - WebSocket 未連接', {
        messageId,
        readyState: this.ws?.readyState,
        connectionState: this.connectionState,
        isReconnecting: this.isReconnecting
      });
      if (messageId) {
        messageStatusStore.setFailed(messageId, 'WebSocket 未連接');
      }
      return false;
    }

    // 如果提供了 messageId，設置為發送中狀態
    if (messageId) {
      messageStatusStore.setSending(messageId);
    }

    try {
      const message = {
        type: 'message',
        content,
        message_type: type,
        temp_id: messageId, // 添加臨時 ID 用於狀態追蹤
        metadata: metadata || null, // 添加元數據支援
      };

      console.debug('[WebSocket] 發送訊息', { messageId, type, contentLength: content.length });
      this.ws!.send(JSON.stringify(message));

      // 發送成功後設置狀態
      if (messageId) {
        messageStatusStore.setSent(messageId);
      }

      return true;
    } catch (error) {
      console.error('[WebSocket] 訊息發送異常', {
        messageId,
        error: error instanceof Error ? error.message : error,
        readyState: this.ws?.readyState
      });
      if (messageId) {
        messageStatusStore.setFailed(messageId, `發送失敗: ${error instanceof Error ? error.message : '未知錯誤'}`);
      }
      return false;
    }
  }

  // 發送已讀狀態變更請求
  markNotificationRead(notificationId: string, readType: 'notification' | 'room' | 'all' = 'notification') {
    if (!this.isConnected()) {
      return false;
    }

    try {
      const message = {
        type: 'notification_read',
        notification_id: notificationId,
        read_type: readType,
        target_room_id: this.roomId,
      };

      this.ws!.send(JSON.stringify(message));
      return true;
    } catch (error) {
      return false;
    }
  }

  // 批量標記已讀
  markAllNotificationsRead() {
    return this.markNotificationRead('', 'all');
  }

  // 房間已讀請求緩存，防止重複請求
  private roomReadRequestCache = new Set<string>();

  // 標記房間消息已讀
  markRoomMessagesRead(roomId?: string) {
    const targetRoomId = roomId || this.roomId;
    if (!targetRoomId) {
      return false;
    }

    if (!this.isConnected()) {
      return false;
    }

    // 防止重複請求同一房間的已讀操作
    const cacheKey = `room_read_${targetRoomId}`;
    if (this.roomReadRequestCache.has(cacheKey)) {
      console.debug('[WebSocket] 跳過重複的房間已讀請求:', targetRoomId);
      return true; // 返回 true 表示已經處理過
    }

    try {
      const message = {
        type: 'notification_read',
        read_type: 'room',
        target_room_id: targetRoomId,
        // 對於房間已讀，不傳送 notification_id 欄位
      };

      // 添加到緩存
      this.roomReadRequestCache.add(cacheKey);

      // 3秒後清除緩存，允許新的請求
      setTimeout(() => {
        this.roomReadRequestCache.delete(cacheKey);
      }, 3000);

      this.ws!.send(JSON.stringify(message));
      return true;
    } catch (error) {
      // 如果發送失敗，立即清除緩存
      this.roomReadRequestCache.delete(cacheKey);
      return false;
    }
  }

  // 處理收到的訊息
  private handleMessage(data: WebSocketMessage) {
    switch (data.type) {
      case 'message':
        this.handleNewMessage(data.payload);
        break;

      case 'user_joined':
        this.handleUserJoined(data.user || data.payload, data.timestamp);
        break;

      case 'user_left':
        this.handleUserLeft(data.user || data.payload, data.timestamp);
        break;

      case 'room_users':
        this.handleRoomUsers(data);
        break;

      case 'welcome':
        this.handleWelcomeMessage(data);
        break;

      case 'message_history':
        this.handleMessageHistory(data);
        break;

      case 'pong':
        this.handlePong(data);
        break;

      case 'notification':
        // 檢查是否為特殊事件（如 room_created）
        const notificationData = data.data || data.payload;
        
        // 確保通知資料存在且有效
        if (!notificationData) {
          console.warn('[WebSocket] 收到空的通知資料:', data);
          break;
        }
        
        if (notificationData.type === 'room_created') {
          // 這是房間創建事件，觸發 room_created 事件
          this.emit('room_created', notificationData);
        } else {
          // 轉換通知資料格式
          const transformedNotification = transformNotification(notificationData);
          
          // 只處理有效的通知
          if (transformedNotification && transformedNotification.title && transformedNotification.message) {
            this.handleNotification(transformedNotification);
          } else {
            console.warn('[WebSocket] 通知資料格式不正確:', notificationData);
          }
        }
        break;

      case 'notification_status_changed':
        this.handleNotificationStatusChanged(data.data || data.payload);
        break;

      case 'room_created':
        this.handleRoomCreated(data.data || data.payload || data);
        break;

      case 'room_deleted':
        this.handleRoomDeleted(data.data || data.payload || data);
        break;

      case 'room_updated':
        this.handleRoomUpdated(data.data || data.payload || data);
        break;

      case 'read_status_response':
        this.handleReadStatusResponse(data.data || data.payload);
        break;

      case 'error':
        this.handleError(data.payload);
        break;

      default:
    }

    // 觸發自定義事件
    this.emit(data.type, data.payload);
  }

  // 處理新訊息
  private handleNewMessage(message: Message) {
    messageStore.addMessage(message);

    // 移除自動刷新通知列表的邏輯
    // 通知應該只透過 WebSocket 的 notification 事件接收
    // 這樣可以避免重複處理和 API 呼叫
    const currentUserData = currentUser();
    if (currentUserData && message.user_id !== currentUserData.id) {
      // console.log('[WebSocket] 收到其他用戶的訊息，等待通知事件');
      // 通知會透過獨立的 notification 事件發送
    }
  }

  // 處理用戶加入
  private handleUserJoined(user: User, eventTimestamp?: string) {
    // 檢查是否是當前用戶自己，避免重複添加
    const currentUserData = currentUser();
    if (currentUserData && user.id === currentUserData.id) {
      return;
    }

    // 檢查最近是否收到了 room_users 事件（3秒內）
    // 如果是，則跳過此 user_joined 事件，避免重複添加
    const timeSinceRoomUsers = Date.now() - this.lastRoomUsersTime;
    if (timeSinceRoomUsers < 3000) {

      // 仍然創建系統訊息，但不添加用戶到列表
      if (eventTimestamp) {
        const systemMessage: Message = {
          id: `system_${Date.now()}_${user.username}`,
          room_id: this.roomId!,
          user_id: 'system',
          content: `${user.username} 加入了聊天室`,
          message_type: 'system',
          created_at: eventTimestamp,
          updated_at: eventTimestamp,
          user: {
            id: 'system',
            username: 'System',
            created_at: eventTimestamp,
          },
        };

        messageStore.addMessage(systemMessage);
      }
      return;
    }

    // 檢查用戶是否已經在列表中（額外的安全檢查）
    const currentRoomState = roomStore.state;
    const existingUser = currentRoomState.users.find(u => u.id === user.id);
    if (existingUser) {

      // 仍然創建系統訊息，但不添加用戶到列表
      if (eventTimestamp) {
        const systemMessage: Message = {
          id: `system_${Date.now()}_${user.username}`,
          room_id: this.roomId!,
          user_id: 'system',
          content: `${user.username} 加入了聊天室`,
          message_type: 'system',
          created_at: eventTimestamp,
          updated_at: eventTimestamp,
          user: {
            id: 'system',
            username: 'System',
            created_at: eventTimestamp,
          },
        };

        messageStore.addMessage(systemMessage);
      }
      return;
    }

    roomStore.addUser(user);

    // 只有當後端提供事件時間戳時才創建系統訊息
    // 這確保時間戳來自後端的 UTC 時間
    if (eventTimestamp) {
      const systemMessage: Message = {
        id: `system_${Date.now()}_${user.username}`,
        room_id: this.roomId!,
        user_id: 'system',
        content: `${user.username} 加入了聊天室`,
        message_type: 'system',
        created_at: eventTimestamp,
        updated_at: eventTimestamp,
        user: {
          id: 'system',
          username: 'System',
          created_at: eventTimestamp,
        },
      };

      messageStore.addMessage(systemMessage);
    }
  }

  // 處理用戶離開
  private handleUserLeft(user: User | string, eventTimestamp?: string) {
    // 如果傳入的是用戶對象，從中提取用戶 ID；否則直接使用字符串
    const userId = typeof user === 'string' ? user : user.id;
    const username = typeof user === 'string' ? '用戶' : user.username;

    if (userId) {
      roomStore.removeUser(userId);
    }

    // 只有當後端提供事件時間戳時才創建系統訊息
    // 這確保時間戳來自後端的 UTC 時間
    if (eventTimestamp) {
      const systemMessage: Message = {
        id: `system_${Date.now()}`,
        room_id: this.roomId!,
        user_id: 'system',
        content: `${username} 離開了聊天室`,
        message_type: 'system',
        created_at: eventTimestamp,
        updated_at: eventTimestamp,
        user: {
          id: 'system',
          username: 'System',
          created_at: eventTimestamp,
        },
      };

      messageStore.addMessage(systemMessage);
    }
  }

  // 處理房間用戶列表
  private handleRoomUsers(data: any) {


    if (!data) {
      console.warn('[WebSocket] room_users 數據為空');
      return;
    }

    if (!data.users) {
      console.warn('[WebSocket] room_users 沒有 users 字段');
      return;
    }

    if (!Array.isArray(data.users)) {
      console.warn('[WebSocket] room_users.users 不是數組');
      return;
    }

    try {
      // 記錄收到 room_users 事件的時間
      this.lastRoomUsersTime = Date.now();

      // 獲取當前的用戶列表
      const currentRoomState = roomStore.state;
      const existingUsers = currentRoomState.users || [];

      // 創建一個 Map 來合併用戶列表
      const userMap = new Map<string, any>();

      // 先添加現有的用戶（保留完整資訊）
      existingUsers.forEach(user => {
        if (user.id) {
          userMap.set(user.id, user);
        }
      });

      // 更新在線用戶的狀態（room_users 事件只包含在線用戶）
      const onlineUserIds = new Set(data.users.map((u: any) => u.id));

      // 更新或添加在線用戶
      data.users.forEach((user: any) => {
        const existingUser = userMap.get(user.id);
        if (existingUser) {
          // 如果用戶已存在，只更新 is_active 狀態
          userMap.set(user.id, {
            ...existingUser,
            is_active: true
          });
        } else {
          // 如果是新用戶，添加到列表
          userMap.set(user.id, {
            ...user,
            is_active: true
          });
        }
      });

      // 將不在線上列表中的用戶標記為離線
      userMap.forEach((user, userId) => {
        if (!onlineUserIds.has(userId)) {
          userMap.set(userId, {
            ...user,
            is_active: false
          });
        }
      });

      // 轉換回陣列
      const mergedUsers = Array.from(userMap.values());

      // console.log('[WebSocket] 更新房間用戶列表:', mergedUsers);
      roomStore.setUsers(mergedUsers);
    } catch (error) {
      console.error('[WebSocket] 處理房間用戶列表失敗:', error);
    }
  }

  // 處理歡迎訊息
  private handleWelcomeMessage(data: any) {

    // 歡迎訊息不生成系統訊息，避免與 user_joined 重複
    // 用戶加入的系統訊息由 user_joined 事件處理
  }

  // 處理歷史訊息
  private handleMessageHistory(data: any) {

    if (data.messages && Array.isArray(data.messages)) {
      // 批量添加歷史訊息到 store，但過濾掉系統訊息
      // 系統訊息應該由實時事件生成，而不是從歷史記錄載入
      data.messages.forEach((message: Message) => {
        if (message.message_type !== 'system') {
          messageStore.addMessage(message);
        }
      });
    }
  }

  // 處理 pong 回應
  private handlePong(data: any) {
    // 清除 ping 超時計時器
    if (this.pingTimeout) {
      clearTimeout(this.pingTimeout);
      this.pingTimeout = null;
    }

    // 計算延遲
    if (this.lastPingTime > 0) {
      const latency = Date.now() - this.lastPingTime;
      // console.log(`[WebSocket] 延遲: ${latency}ms`);

      // 如果延遲太高，可能需要警告
      if (latency > 5000) {
        console.warn(`[WebSocket] 高延遲警告: ${latency}ms`);
      }
    }
  }

  // 處理房間創建事件
  private handleRoomCreated(data: any) {
    // console.log('[WebSocket] 收到房間創建事件:', data);

    try {
      // 檢查是否有新房間資料
      if (!data || !data.room) {
        console.warn('[WebSocket] 房間創建事件缺少房間數據');
        return;
      }

      const newRoom = data.room;
      const creatorId = data.creator_id;

      // console.log('[WebSocket] 新房間已創建:', newRoom.name, 'by', creatorId);

      // 觸發房間創建事件給監聽者
      this.emit('room_created', data);

    } catch (error) {
      console.error('[WebSocket] 處理房間創建事件失敗:', error);
    }
  }

  // 處理房間刪除事件
  private handleRoomDeleted(data: any) {

    try {
      const roomId = data.room_id || data.roomId;

      if (!roomId) {
        return;
      }

      // 房間刪除事件處理
      // console.log('房間已刪除:', roomId);


    } catch (error) {
    }
  }

  // 處理房間更新事件
  private handleRoomUpdated(data: any) {

    try {
      if (!data || !data.room) {
        return;
      }

      const updatedRoom = data.room;

      // 房間更新事件處理
      // console.log('房間已更新:', updatedRoom);


    } catch (error) {
    }
  }

  // 處理通知
  private handleNotification(notification: Notification) {
    // console.log('[WebSocket] 收到通知:', notification);

    // 檢查通知是否有效
    if (!notification || !notification.title || !notification.message) {
      console.warn('[WebSocket] 收到無效通知:', notification);
      return;
    }

    // 檢查是否為新通知（避免重複播放音效）
    const existingNotifications = notificationStore.notifications;
    const isExistingNotification = existingNotifications.some(n => n.id === notification.id);

    // 無論是否為當前房間，都添加到通知 store
    notificationStore.addNotification(notification);
    // console.log('[WebSocket] 已添加通知到 store');

    // 如果是當前房間的通知，可以選擇性地標記為已讀
    // 但建議讓用戶自己決定是否已讀
    if (notification.room_id && notification.room_id === this.roomId) {
      // console.log('[WebSocket] 通知屬於當前房間，保留未讀狀態');
      // 不自動標記為已讀，讓用戶看到通知徽章
    }

    // 獲取當前通知設置
    const currentSettings = notificationSettings.value;

    // 播放聲音通知 - 只有新通知才播放音效
    if (currentSettings.sound && !isExistingNotification && notification.status === 'UNREAD') {
      // console.log('[WebSocket] 播放新通知音效');
      soundNotificationManager.playNotificationSound();
    } else if (isExistingNotification) {
      // console.log('[WebSocket] 跳過音效播放，這是已存在的通知');
    }

    // 顯示瀏覽器通知
    if (currentSettings.browserNotifications && typeof window !== 'undefined') {
      // 檢查頁面是否可見，如果不可見才顯示瀏覽器通知
      if (document.hidden || document.visibilityState === 'hidden') {
        browserNotificationManager.showNotification(notification.title, {
          body: notification.message,
          icon: '/favicon.svg',
          badge: '/favicon.svg',
          tag: notification.id, // 避免重複通知
          requireInteraction: notification.type === 'MENTION', // 提及時要求用戶交互
          data: {
            notificationId: notification.id,
            roomId: notification.data?.['room_id']
          }
        });
      }
    }
  }

  // 處理通知狀態變更
  private handleNotificationStatusChanged(data: any) {

    try {
      const { type, id, status, timestamp, room_id } = data;

      if (status === 'read') {
        if (type === 'notification') {
          // 更新通知狀態
          notificationStore.markAsRead(id);
        } else if (type === 'room' && room_id) {
          // 標記房間消息為已讀 - 刷新通知列表
          // 從 API 重新獲取通知列表以確保狀態同步
          setTimeout(async () => {
            try {
              const response = await fetch('/api/notifications/', {
                credentials: 'include'
              });
              if (response.ok) {
                const data = await response.json();
                notificationStore.setNotifications(data.notifications || []);
              }
            } catch (error) {
              console.error('[WebSocket] 刷新通知列表失敗:', error);
            }
          }, 500); // 延遲 500ms 確保後端已經處理完成
        } else if (type === 'all') {
          // 標記所有通知為已讀
          notificationStore.markAllAsRead();
        }
      }

      // 觸發自定義事件，讓其他組件可以監聽
      this.emit('read_status_updated', { type, id, status, timestamp });

    } catch (error) {
    }
  }

  // 處理已讀狀態響應
  private handleReadStatusResponse(data: any) {

    if (data.success) {
      // 可以在這裡添加成功的 UI 反饋
      this.emit('read_operation_success', data);
    } else {
      // 處理失敗情況
      // 如果是房間已讀操作失敗，可能是因為沒有需要標記的通知，使用較低的日誌級別
      // if (data.read_type === 'room' && (data.notification_id === '' || data.notification_id === null || data.notification_id === undefined)) {
      //   console.debug('[WebSocket] 房間已讀操作失敗（可能沒有需要標記的通知）:', {
      //     read_type: data.read_type,
      //     target_room_id: data.target_room_id,
      //     reason: data.message || '沒有找到需要標記的通知'
      //   });
      // } else {
      //   console.warn('[WebSocket] 已讀操作失敗:', data);
      // }
      this.emit('read_operation_failed', data);
    }
  }

  // 處理錯誤
  private handleError(error: any) {

    // 如果錯誤包含 temp_id，更新對應訊息的狀態
    if (error.temp_id) {
      messageStatusStore.setFailed(error.temp_id, error.message || '未知錯誤');
    }

    // 觸發錯誤事件
    this.emit('message_error', error);
  }

  // 安排重連
  private scheduleReconnect() {
    if (this.isReconnecting || this.reconnectAttempts >= this.maxReconnectAttempts) {
      return;
    }

    this.isReconnecting = true;
    this.reconnectAttempts++;

    // 計算重連延遲（指數退避 + 隨機抖動）
    const jitter = Math.random() * 0.3; // 30% 隨機抖動
    const delay = Math.min(
      this.currentReconnectDelay * (1 + jitter),
      this.maxReconnectDelay
    );


    this.reconnectTimeout = window.setTimeout(() => {
      this.performReconnect();
    }, delay);

    // 更新下次重連延遲（指數退避）
    this.currentReconnectDelay = Math.min(this.currentReconnectDelay * 2, this.maxReconnectDelay);
  }

  // 執行重連
  private async performReconnect() {
    if (!this.roomId || !this.token || !this.isReconnecting) {
      this.isReconnecting = false;
      return;
    }

    try {

      await this.connect(this.roomId, this.token);

      // 重連成功，重置狀態
      this.isReconnecting = false;

    } catch (error) {
      this.isReconnecting = false;

      // 如果還有重連次數，繼續嘗試
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.scheduleReconnect();
      } else {
        this.emit('reconnect_failed', {
          attempts: this.reconnectAttempts,
          lastError: error
        });
      }
    }
  }

  // 清除重連超時
  private clearReconnectTimeout() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  // 判斷是否應該重連
  private shouldReconnect(closeCode?: number): boolean {
    // 檢查基本條件
    if (!this.roomId || !this.token) {
      return false;
    }

    // 某些關閉代碼不應該重連
    if (closeCode) {
      // 1000: 正常關閉
      // 1001: 端點離開
      // 4001: 認證失敗（我們的自定義代碼）
      // 4003: 禁止訪問
      const noReconnectCodes = [1000, 1001, 4001, 4003];
      if (noReconnectCodes.includes(closeCode)) {
        return false;
      }
    }

    return true;
  }

  // 心跳檢測（針對移動設備優化）
  private startHeartbeat() {
    // 更頻繁的心跳，防止移動設備斷線
    const heartbeatDelay = 20000; // 20秒，比原來的30秒更頻繁

    this.heartbeatInterval = window.setInterval(() => {
      if (this.isConnected()) {
        // 發送 ping
        this.lastPingTime = Date.now();
        this.ws!.send(JSON.stringify({ type: 'ping' }));

        // 設置超時檢測，如果10秒內沒收到 pong，認為連接斷開
        this.pingTimeout = window.setTimeout(() => {
          console.warn('[WebSocket] Ping 超時，強制重連');
          // 強制關閉連接並重連
          if (this.ws) {
            this.ws.close(4000, 'Ping timeout');
          }
        }, 10000);
      }
    }, heartbeatDelay);
  }

  private stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
    if (this.pingTimeout) {
      clearTimeout(this.pingTimeout);
      this.pingTimeout = null;
    }
  }

  // 處理頁面可見性變化
  private handleVisibilityChange() {
    if (typeof document !== 'undefined' && document.hidden) {
      // 頁面隱藏時，停止心跳但不斷開連接
      this.stopHeartbeat();
    } else {
      // 頁面顯示時，恢復心跳
      if (this.isConnected()) {
        this.startHeartbeat();
      } else if (this.roomId && this.token && !this.isReconnecting) {
        // 如果連接斷開且沒在重連，嘗試重連
        this.scheduleReconnect();
      }
    }
  }

  // 處理網路狀態變化
  private handleOnline() {
    if (this.roomId && this.token && !this.isConnected() && !this.isReconnecting) {
      // 網路恢復時立即嘗試重連
      this.reconnectAttempts = 0; // 重置重連次數
      this.currentReconnectDelay = this.baseReconnectDelay; // 重置延遲
      this.scheduleReconnect();
    }
  }

  private handleOffline() {
    this.emit('offline');
  }

  // 檢查連接狀態
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  getConnectionState(): 'disconnected' | 'connecting' | 'connected' {
    return this.connectionState;
  }

  // 設置連接狀態並發送狀態變化事件
  private setConnectionState(state: 'disconnected' | 'connecting' | 'connected') {
    if (this.connectionState !== state) {
      const previousState = this.connectionState;
      this.connectionState = state;
      this.emit('connection_state_changed', state);
    }
  }

  // 事件監聽
  on(event: string, callback: (data: any) => void) {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback);
  }

  off(event: string, callback: (data: any) => void) {
    if (this.eventListeners[event]) {
      this.eventListeners[event] = this.eventListeners[event].filter(cb => cb !== callback);
    }
  }

  private emit(event: string, data?: any) {
    if (this.eventListeners[event]) {
      this.eventListeners[event].forEach(callback => callback(data));
    }
  }

  // 手動重連（用於 UI 觸發）
  manualReconnect(): Promise<void> {
    if (!this.roomId || !this.token) {
      return Promise.reject(new Error('No room or token available'));
    }

    // 重置重連狀態
    this.reconnectAttempts = 0;
    this.currentReconnectDelay = this.baseReconnectDelay;
    this.isReconnecting = false;
    this.clearReconnectTimeout();

    // 斷開當前連接
    this.disconnect();

    // 重新連接
    return this.connect(this.roomId, this.token);
  }

  // 獲取重連信息
  getReconnectInfo() {
    return {
      isReconnecting: this.isReconnecting,
      attempts: this.reconnectAttempts,
      maxAttempts: this.maxReconnectAttempts,
      currentDelay: this.currentReconnectDelay
    };
  }

  // 清理資源
  destroy() {
    this.disconnect();
    this.clearReconnectTimeout();
    this.eventListeners = {};

    // 只在瀏覽器環境中移除事件監聽器
    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', this.handleVisibilityChange);
      window.removeEventListener('online', this.handleOnline);
      window.removeEventListener('offline', this.handleOffline);
    }
  }
}

// 全域 WebSocket 管理器實例
let _wsManager: WebSocketManager | null = null;

export const wsManager = {
  getInstance(): WebSocketManager {
    if (!_wsManager) {
      _wsManager = new WebSocketManager();
    }
    return _wsManager;
  }
};