import { messageStatusStore } from '$lib/stores';
import type { WebSocketMessage, WSPongMessage } from '$lib/types';
import { apiClient } from '$lib/api/client';
import type { HandlerContext, HandlerEvent, HandlerEventPayloadMap } from './handlers';
import { isValidWSMessage } from './guards';
import { handleUserJoined, handleUserLeft, handleUserStatusChanged, handleRoomUsers, handleRoomCreated, handleRoomDeleted, handleRoomUpdated, resetLastRoomUsersTime } from './roomHandlers';
import { handleNewMessage, handleMessageHistory, handleTypingIndicator, handleError } from './messageHandlers';
import { dispatchNotification, handleNotificationStatusChanged, cancelPendingNotificationRefresh } from './notificationHandlers';

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
  private pingTimeout: number | null = null; // 添加 ping 超時檢測
  private lastPingTime = 0; // 記錄最後 ping 時間

  private roomId: string | null = null;

  // 事件監聽器
  private eventListeners: {
    [key: string]: Array<(data: any) => void>;
  } = {};

  // 保存 bound 方法引用，確保 removeEventListener 能正確移除
  private boundHandleVisibilityChange = this.handleVisibilityChange.bind(this);
  private boundHandleOnline = this.handleOnline.bind(this);
  private boundHandleOffline = this.handleOffline.bind(this);

  constructor() {
    // 只在瀏覽器環境中初始化事件監聽器
    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', this.boundHandleVisibilityChange);
      window.addEventListener('online', this.boundHandleOnline);
      window.addEventListener('offline', this.boundHandleOffline);
    }
  }

  // 建構 WebSocket URL（使用 ticket 而非 token）
  private buildWsUrl(roomId: string, ticket: string): string {
    if (import.meta.env['PUBLIC_WS_URL'] && window.location.hostname === 'localhost') {
      return `${import.meta.env['PUBLIC_WS_URL']}/ws/${roomId}?ticket=${ticket}`;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;

    let port = '';
    if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0') {
      port = ':8000';
    } else if (host.startsWith('192.168.') || host.startsWith('10.') || host.startsWith('172.')) {
      port = ':8000';
    } else if (window.location.port) {
      port = `:${window.location.port}`;
    }

    return `${protocol}//${host}${port}/ws/${roomId}?ticket=${ticket}`;
  }

  // 連接 WebSocket（透過 BFF 取得一次性 ticket）
  async connect(roomId: string): Promise<void> {
    // 先透過 BFF 取得一次性 ticket
    const ticket = await apiClient.wsTicket.create(roomId);

    return new Promise((resolve, reject) => {
      // 先斷舊連線再設新 roomId，避免 disconnect() 同步清除剛設好的值
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.disconnect();
      }
      this.roomId = roomId;

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

      this.setConnectionState('connecting');

      const wsUrl = this.buildWsUrl(roomId, ticket);

      try {
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
          // 檢查是否還是當前連接
          if (currentConnectionId !== this.connectionId) {
            console.warn('[WebSocket] 連接ID不匹配，忽略此連接:', {
              current: currentConnectionId,
              latest: this.connectionId
            });
            return;
          }

          this.setConnectionState('connected');
          this.reconnectAttempts = 0;
          this.currentReconnectDelay = this.baseReconnectDelay;
          this.isReconnecting = false;
          this.clearReconnectTimeout();
          this.startHeartbeat();
          this.emit('connected');
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const raw: unknown = JSON.parse(event.data);
            if (!isValidWSMessage(raw)) {
              console.error('[WebSocket] 收到不符預期的訊息格式:', raw);
              return;
            }
            this.handleMessage(raw);
          } catch (error) {
            console.error('[WebSocket] 解析訊息失敗:', error);
          }
        };

        this.ws.onclose = (event) => {

          // 檢查是否還是當前連接
          if (currentConnectionId !== this.connectionId) {
            return;
          }

          this.setConnectionState('disconnected');
          this.stopHeartbeat();
          this.emit('disconnected', { code: event.code, reason: event.reason });

          // 判斷是否需要重連
          if (!event.wasClean && this.shouldReconnect(event.code)) {
            this.scheduleReconnect();
          }
        };

        this.ws.onerror = (error) => {
          console.error('[WebSocket] 連接錯誤:', error);

          if (this.connectionState === 'connecting') {
            console.error('[WebSocket] 初始連接失敗');
            reject(new Error('WebSocket connection failed'));
          }
        };

        // 連接超時處理
        // 不使用 disconnect()，避免清除 roomId 導致無法自動重連
        setTimeout(() => {
          if (this.connectionState === 'connecting') {
            console.error('[WebSocket] 連接超時');
            this.setConnectionState('disconnected');
            this.stopHeartbeat();
            if (this.ws) {
              try {
                this.ws.close(4000, 'Connection timeout');
              } catch { /* ignore close errors */ }
              this.ws = null;
            }
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
    resetLastRoomUsersTime();
    cancelPendingNotificationRefresh();

    // 注意：不要在這裡清空用戶列表，因為可能導致 UI 閃爍
    // 新的房間會在載入時自動更新用戶列表
    // roomStore.setUsers([]);

    // 清除房間已讀請求緩存
    this.roomReadRequestCache.clear();

    // disconnect() 已透過 connectionId++ 使舊連接失效，
    // 且 isReconnecting=false 阻止了重連，可直接清除 roomId。
    // 不使用 setTimeout 延遲，避免與新房間的 connect() 設定 roomId 競爭。
    this.roomId = null;
  }

  // 發送訊息
  sendMessage(content: string, type: 'text' | 'image' | 'file' = 'text', messageId?: string, metadata?: Record<string, unknown>) {
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

  // 發送打字指示器
  sendTypingIndicator(isTyping: boolean): boolean {
    if (!this.isConnected()) {
      return false;
    }
    try {
      this.ws!.send(JSON.stringify({ type: 'typing', is_typing: isTyping }));
      return true;
    } catch {
      return false;
    }
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
    } catch {
      // 如果發送失敗，立即清除緩存
      this.roomReadRequestCache.delete(cacheKey);
      return false;
    }
  }

  // 處理收到的訊息（dispatch 到各領域 handler，switch 自動收窄型別）
  private handleMessage(data: WebSocketMessage) {
    const ctx: HandlerContext = {
      roomId: this.roomId,
      emit: <E extends HandlerEvent>(event: E, payload?: HandlerEventPayloadMap[E]) => this.emit(event, payload),
    };

    switch (data.type) {
      case 'message':
        handleNewMessage(data.payload);
        break;

      case 'user_joined':
        handleUserJoined(data.user, data.timestamp, ctx);
        break;

      case 'user_left':
        handleUserLeft(data.user, data.timestamp, ctx, data.removed);
        break;

      case 'room_users':
        handleRoomUsers(data);
        break;

      case 'user_status_changed':
        handleUserStatusChanged(data);
        break;

      case 'welcome':
        break; // no-op，系統訊息由 user_joined 事件處理

      case 'message_history':
        handleMessageHistory(data);
        break;

      case 'pong':
        this.handlePong(data);
        break;

      case 'notification':
        dispatchNotification(data, ctx);
        break;

      case 'notification_status_changed':
        handleNotificationStatusChanged(data.data, ctx);
        break;

      case 'room_created':
        handleRoomCreated(data, ctx);
        break;

      case 'room_deleted':
        handleRoomDeleted(data, ctx);
        break;

      case 'room_updated':
        handleRoomUpdated(data, ctx);
        break;

      case 'typing':
        handleTypingIndicator(data, ctx);
        break;

      case 'error':
        handleError(data, ctx);
        break;

      case 'read_status_response':
      case 'notification_stats_update':
        break; // 目前前端不處理，保留為 no-op

      default:
        // 後端可能新增的未知事件類型，記錄以便排查
        console.debug('[WebSocket] 未處理的事件類型:', (data as { type: string }).type);
        break;
    }
  }

  // 處理 pong 回應
  private handlePong(_data: WSPongMessage) {
    // 清除 ping 超時計時器
    if (this.pingTimeout) {
      clearTimeout(this.pingTimeout);
      this.pingTimeout = null;
    }

    // 計算延遲
    if (this.lastPingTime > 0) {
      const latency = Date.now() - this.lastPingTime;
      // 如果延遲太高，可能需要警告
      if (latency > 5000) {
        console.warn(`[WebSocket] 高延遲警告: ${latency}ms`);
      }
    }
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

  // 執行重連（每次重連都取得新的 ticket）
  private async performReconnect() {
    if (!this.roomId || !this.isReconnecting) {
      this.isReconnecting = false;
      return;
    }

    try {
      await this.connect(this.roomId);

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
    if (!this.roomId) {
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
      } else if (this.roomId && !this.isReconnecting) {
        // 如果連接斷開且沒在重連，嘗試重連
        this.scheduleReconnect();
      }
    }
  }

  // 處理網路狀態變化
  private handleOnline() {
    if (this.roomId && !this.isConnected() && !this.isReconnecting) {
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
      this.connectionState = state;
      this.emit('connection_state_changed', state);
    }
  }

  // 事件監聽（泛型確保 event 與 callback payload 型別一致）
  on<E extends HandlerEvent>(event: E, callback: (data: HandlerEventPayloadMap[E]) => void): void {
    if (!this.eventListeners[event]) {
      this.eventListeners[event] = [];
    }
    this.eventListeners[event].push(callback as (data: any) => void);
  }

  off<E extends HandlerEvent>(event: E, callback: (data: HandlerEventPayloadMap[E]) => void): void {
    if (this.eventListeners[event]) {
      this.eventListeners[event] = this.eventListeners[event].filter(cb => cb !== (callback as (data: any) => void));
    }
  }

  private emit(event: string, data?: unknown): void {
    if (this.eventListeners[event]) {
      this.eventListeners[event].forEach(callback => callback(data));
    }
  }

  // 手動重連（用於 UI 觸發）
  manualReconnect(): Promise<void> {
    if (!this.roomId) {
      return Promise.reject(new Error('No room available'));
    }

    const roomId = this.roomId;

    // 重置重連狀態
    this.reconnectAttempts = 0;
    this.currentReconnectDelay = this.baseReconnectDelay;
    this.isReconnecting = false;
    this.clearReconnectTimeout();

    // 斷開當前連接
    this.disconnect();

    // 重新連接（取得新 ticket）
    return this.connect(roomId);
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
      document.removeEventListener('visibilitychange', this.boundHandleVisibilityChange);
      window.removeEventListener('online', this.boundHandleOnline);
      window.removeEventListener('offline', this.boundHandleOffline);
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
  },
  destroy(): void {
    if (_wsManager) {
      _wsManager.destroy();
      _wsManager = null;
    }
  },
};
