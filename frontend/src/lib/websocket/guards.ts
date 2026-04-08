import type { WebSocketMessage } from '$lib/types';

/** WS 訊息的已知 type 值集合（與 WebSocketMessage union 的 discriminator 同步，型別約束確保新增 type 時編譯期報錯） */
const KNOWN_WS_TYPES = new Set<WebSocketMessage['type']>([
  'welcome',
  'room_users',
  'message_history',
  'message',
  'typing',
  'user_joined',
  'user_left',
  'user_status_changed',
  'pong',
  'notification',
  'notification_status_changed',
  'read_status_response',
  'notification_stats_update',
  'room_created',
  'room_updated',
  'room_deleted',
  'error',
]);

/** 檢查 JSON.parse 結果是否為合法的 WS 訊息結構 */
export function isValidWSMessage(data: unknown): data is WebSocketMessage {
  if (typeof data !== 'object' || data === null || !('type' in data)) return false;
  const type = (data as { type: unknown }).type;
  return typeof type === 'string' && KNOWN_WS_TYPES.has(type as WebSocketMessage['type']);
}
