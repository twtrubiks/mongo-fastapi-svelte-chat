/**
 * WebSocket handler 事件定義與共享 context。
 */
import type {
  WSRoomCreatedMessage,
  WSRoomDeletedMessage,
  WSRoomUpdatedMessage,
  WSErrorMessage,
  NotificationStatusData,
} from '$lib/types';

/**
 * Handler 領域事件的 payload 映射表，
 * 讓 emit / on / off 在編譯時期就擋住型別不符的呼叫。
 */
export interface HandlerEventPayloadMap {
  // manager 自身事件
  connected: void;
  disconnected: { code: number; reason: string };
  reconnect_failed: { attempts: number; lastError: unknown };
  offline: void;
  connection_state_changed: 'disconnected' | 'connecting' | 'connected';
  // handler 領域事件
  room_created: WSRoomCreatedMessage;
  room_deleted: WSRoomDeletedMessage;
  room_updated: WSRoomUpdatedMessage;
  read_status_updated: NotificationStatusData;
  message_error: WSErrorMessage;
}

/** 所有 handler 事件名稱的 union type */
export type HandlerEvent = keyof HandlerEventPayloadMap;

/**
 * 從 WebSocketManager 傳遞給抽出的 handler 函式的共享 context。
 * 讓 handler 與 class 解耦，同時保留必要的狀態存取。
 */
export interface HandlerContext {
  roomId: string | null;
  emit: <E extends HandlerEvent>(event: E, data?: HandlerEventPayloadMap[E]) => void;
}
