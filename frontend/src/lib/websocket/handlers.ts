/**
 * WebSocket 事件名稱（handler 與 manager 共用），避免裸字串拼錯。
 */
export type HandlerEvent =
  // manager 自身事件
  | 'connected'
  | 'disconnected'
  | 'reconnect_failed'
  | 'offline'
  | 'connection_state_changed'
  // handler 領域事件
  | 'room_created'
  | 'room_deleted'
  | 'room_updated'
  | 'read_status_updated'
  | 'message_error';

/**
 * 從 WebSocketManager 傳遞給抽出的 handler 函式的共享 context。
 * 讓 handler 與 class 解耦，同時保留必要的狀態存取。
 */
export interface HandlerContext {
  roomId: string | null;
  emit: (event: HandlerEvent, data?: any) => void;
}
