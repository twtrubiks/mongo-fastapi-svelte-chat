import type { BFFResponse, BFFErrorCode } from './bff-types';
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

// 從 cookies 或 headers 獲取認證 token
export function getAuthToken(cookies: any, headers?: any): string | null {
  
  // 首先嘗試從 cookie 獲取
  const cookieToken = cookies.get('auth_token') || cookies.get('token');
  
  if (cookieToken) return cookieToken;
  
  // 如果沒有 cookie，嘗試從 Authorization header 獲取
  if (headers) {
    const authHeader = headers.get('authorization');
    
    if (authHeader && authHeader.startsWith('Bearer ')) {
      const headerToken = authHeader.slice(7);
      return headerToken;
    }
  }
  
  return null;
}

// 驗證 token 是否過期
export function isTokenExpired(token: string | null): boolean {
  if (!token) {
    return true;
  }
  
  try {
    const parts = token.split('.');
    if (parts.length !== 3) {
      return true;
    }
    
    const payload = JSON.parse(atob(parts[1]!));
    const now = Math.floor(Date.now() / 1000);
    const isExpired = payload.exp < now;
    
    return isExpired;
  } catch (error) {
    return true;
  }
}

// 生成快取鍵
export function generateCacheKey(prefix: string, params: Record<string, any>): string {
  const sortedParams = Object.keys(params)
    .sort()
    .map(key => `${key}:${params[key]}`)
    .join('|');
  return `${prefix}:${sortedParams}`;
}

// 安全的 JSON 解析
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json);
  } catch {
    return fallback;
  }
}

// 延遲函數（用於演示和測試）
export function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// 重試機制
export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  let lastError: any;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      if (attempt === maxRetries) {
        break;
      }
      
      // 指數退避
      const delayMs = baseDelay * Math.pow(2, attempt);
      await delay(delayMs);
    }
  }
  
  throw lastError;
}

// 效能監控裝飾器
export function withPerformanceTracking<T extends (...args: any[]) => Promise<any>>(
  fn: T,
  name: string
): T {
  return (async (...args: any[]) => {
    const start = performance.now();
    try {
      const result = await fn(...args);
      const duration = performance.now() - start;
      
      // 記錄效能指標（在生產環境中可以發送到監控服務）
      
      return result;
    } catch (error) {
      const duration = performance.now() - start;
      throw error;
    }
  }) as T;
}

// 資料轉換工具
export function transformBackendData<T, R>(
  data: T,
  transformer: (item: T) => R
): R {
  try {
    return transformer(data);
  } catch (error) {
    throw new Error('Failed to transform backend data');
  }
}

// 批量資料轉換
export function transformBatch<T, R>(
  items: T[],
  transformer: (item: T) => R
): R[] {
  return items.map(item => transformBackendData(item, transformer));
}

// 資料聚合工具
export function aggregateData<T, K extends keyof T>(
  items: T[],
  groupBy: K
): Record<string, T[]> {
  return items.reduce((acc, item) => {
    const key = String(item[groupBy]);
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(item);
    return acc;
  }, {} as Record<string, T[]>);
}

// 資料去重
export function deduplicateBy<T, K extends keyof T>(
  items: T[],
  key: K
): T[] {
  const seen = new Set();
  return items.filter(item => {
    const value = item[key];
    if (seen.has(value)) {
      return false;
    }
    seen.add(value);
    return true;
  });
}

// 分頁工具
export function paginate<T>(
  items: T[],
  page: number,
  pageSize: number
): {
  items: T[];
  pagination: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
} {
  const total = items.length;
  const totalPages = Math.ceil(total / pageSize);
  const startIndex = (page - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  
  return {
    items: items.slice(startIndex, endIndex),
    pagination: {
      page,
      pageSize,
      total,
      totalPages,
      hasNext: page < totalPages,
      hasPrev: page > 1,
    },
  };
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

// 轉換通知統計響應
export function transformNotificationStats(stats: any): any {
  if (!stats) return stats;
  
  // 處理 type_counts 中的 key 轉換
  const transformedTypeCounts: Record<string, number> = {};
  if (stats.type_counts) {
    Object.entries(stats.type_counts).forEach(([key, value]) => {
      transformedTypeCounts[key.toUpperCase()] = value as number;
    });
  }
  
  return {
    ...stats,
    type_counts: transformedTypeCounts
  };
}