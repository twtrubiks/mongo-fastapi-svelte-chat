import { json } from '@sveltejs/kit';
import type { BFFResponse } from './bff-types';
import { nanoid } from 'nanoid';

// 創建標準 BFF 響應
export function createBFFResponse<T>(
  data: T,
  error?: { code: string; message: string; details?: any }
): BFFResponse<T>;
export function createBFFResponse<T>(
  data: undefined,
  error: { code: string; message: string; details?: any }
): BFFResponse<T>;
export function createBFFResponse<T>(
  data?: T,
  error?: { code: string; message: string; details?: any }
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
  details?: any
): BFFResponse<any> {
  return createBFFResponse(undefined, { code, message, details });
}

// 通用 BFF 錯誤回應：自動處理 401 並統一 status code 解析
export function toBffErrorResponse(
  error: any,
  fallbackMessage: string,
  errorCode = 'INTERNAL_ERROR',
  details?: any
) {
  if (error.code === 401) {
    return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
  }
  const status = typeof error.code === 'number' ? error.code : 500;
  return json(
    createBFFError(errorCode, error.message || fallbackMessage, details ?? error.details),
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

// 通知資料轉換函數
export function transformNotification(notification: any): any {
  if (!notification) return null;
  
  // 確保必要欄位存在
  const transformed = {
    ...notification,
    // 將 type 和 status 轉換為大寫
    type: notification.type?.toUpperCase() || 'SYSTEM',
    status: notification.status?.toUpperCase() || 'UNREAD',
    // 處理巢狀的 metadata/data 欄位
    metadata: notification.metadata || notification.data || {},
    data: notification.data || notification.metadata || {},
    // 確保 title 和 message 欄位存在
    title: notification.title || '通知',
    message: notification.message || notification.content || ''
  };
  
  // 如果沒有有效的內容，返回 null
  if (!transformed.title && !transformed.message) {
    return null;
  }
  
  return transformed;
}

// 批量轉換通知
export function transformNotifications(notifications: any[]): any[] {
  if (!Array.isArray(notifications)) return [];
  return notifications.map(transformNotification);
}

// 轉換通知列表響應
export function transformNotificationListResponse(response: any): any {
  if (!response) return response;
  
  return {
    ...response,
    notifications: transformNotifications(response.notifications || [])
  };
}

// 轉換通知統計響應：將後端欄位名映射為前端 NotificationStats 介面
export function transformNotificationStats(stats: any): any {
  if (!stats) return stats;

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