import { json } from '@sveltejs/kit';
import type { BFFResponse } from './bff-types';
import type { Notification } from './types';
import { nanoid } from 'nanoid';

/** 後端通知 API / WS 推送的原始格式 */
export interface RawNotification {
  id: string;
  user_id: string;
  type?: string;
  status?: string;
  title?: string;
  message?: string;
  content?: string;
  data?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  room_id?: string;
  sender_id?: string;
  created_at: string;
  updated_at: string;
}

/** 後端通知列表回應的原始格式 */
interface RawNotificationListResponse {
  notifications: RawNotification[];
  [key: string]: unknown;
}

/** 後端通知統計的原始格式 */
interface RawNotificationStats {
  total_count?: number;
  unread_count?: number;
  type_counts?: Record<string, number>;
}

// 創建標準 BFF 響應
export function createBFFResponse<T>(
  data: T,
  error?: { code: string; message: string; details?: unknown }
): BFFResponse<T>;
export function createBFFResponse<T>(
  data: undefined,
  error: { code: string; message: string; details?: unknown }
): BFFResponse<T>;
export function createBFFResponse<T>(
  data?: T,
  error?: { code: string; message: string; details?: unknown }
): BFFResponse<T> {
  const requestId = nanoid();
  const timestamp = new Date().toISOString();

  return {
    success: !error,
    data: data as T,
    error,
    meta: {
      timestamp,
      requestId,
    },
  } as BFFResponse<T>;
}

// 創建錯誤響應
export function createBFFError(
  code: string,
  message: string,
  details?: unknown
): BFFResponse<never> {
  return createBFFResponse<never>(undefined, { code, message, details });
}

// 通用 BFF 錯誤回應：自動處理 401 並統一 status code 解析
export function toBffErrorResponse(
  error: unknown,
  fallbackMessage: string,
  errorCode = 'INTERNAL_ERROR',
  details?: unknown
) {
  const err = error as { code?: unknown; message?: string; details?: unknown };
  if (err.code === 401) {
    return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
  }
  const status = typeof err.code === 'number' ? err.code : 500;
  return json(
    createBFFError(errorCode, err.message || fallbackMessage, details ?? err.details),
    { status }
  );
}

// 檢查 token 是否即將過期（預設 5 分鐘內），thresholdSeconds=0 等同於「已過期」
export function isTokenExpiringSoon(token: string | null, thresholdSeconds: number = 300): boolean {
  if (!token) return true;

  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;

    const payload = JSON.parse(atob(parts[1]!));
    const now = Math.floor(Date.now() / 1000);
    return (payload.exp - now) < thresholdSeconds;
  } catch {
    return true;
  }
}

// 驗證 token 是否已過期
export function isTokenExpired(token: string | null): boolean {
  return isTokenExpiringSoon(token, 0);
}

/** 通知統計前端格式 */
interface NotificationStatsResult {
  total: number;
  unread: number;
  by_type: Record<string, number>;
}

/** 通知列表回應前端格式 */
interface NotificationListResult {
  notifications: Notification[];
  [key: string]: unknown;
}

/** 檢查原始通知資料是否包含最低必要欄位 */
function isValidRawNotification(data: unknown): data is RawNotification {
  if (typeof data !== 'object' || data === null) return false;
  const obj = data as Record<string, unknown>;
  return (
    typeof obj['id'] === 'string' &&
    typeof obj['user_id'] === 'string' &&
    typeof obj['created_at'] === 'string' &&
    typeof obj['updated_at'] === 'string'
  );
}

// 通知資料轉換函數
export function transformNotification(notification: unknown): Notification | null {
  if (!isValidRawNotification(notification)) {
    if (notification != null) {
      console.error('[transformNotification] 通知資料缺少必填欄位:', notification);
    }
    return null;
  }

  // 確保必要欄位存在
  const transformed: Notification = {
    id: notification.id,
    user_id: notification.user_id,
    // 將 type 和 status 轉換為大寫
    type: (notification.type?.toUpperCase() || 'SYSTEM') as Notification['type'],
    status: (notification.status?.toUpperCase() || 'UNREAD') as Notification['status'],
    // 處理巢狀的 metadata/data 欄位
    metadata: notification.metadata || notification.data || {},
    data: notification.data || notification.metadata || {},
    // 確保 title 和 message 欄位存在
    title: notification.title || '通知',
    message: notification.message || notification.content || '',
    created_at: notification.created_at,
    updated_at: notification.updated_at,
    ...(notification.content != null && { content: notification.content }),
    ...(notification.room_id != null && { room_id: notification.room_id }),
    ...(notification.sender_id != null && { sender_id: notification.sender_id }),
  };

  // 如果沒有有效的內容，返回 null
  if (!transformed.title && !transformed.message) {
    return null;
  }

  return transformed;
}

// 批量轉換通知
export function transformNotifications(notifications: RawNotification[]): Notification[] {
  if (!Array.isArray(notifications)) return [];
  return notifications.map(transformNotification).filter((n): n is Notification => n !== null);
}

// 轉換通知列表響應
export function transformNotificationListResponse(response: RawNotificationListResponse): NotificationListResult {
  return {
    ...response,
    notifications: transformNotifications(response.notifications || [])
  };
}

// 轉換通知統計響應：將後端欄位名映射為前端 NotificationStats 介面
export function transformNotificationStats(stats: RawNotificationStats): NotificationStatsResult {
  // 處理 type_counts 中的 key 轉換（大寫化）
  const transformedTypeCounts: Record<string, number> = {};
  if (stats.type_counts) {
    Object.entries(stats.type_counts).forEach(([key, value]) => {
      transformedTypeCounts[key.toUpperCase()] = value as number;
    });
  }

  return {
    total: stats.total_count ?? 0,
    unread: stats.unread_count ?? 0,
    by_type: transformedTypeCounts
  };
}