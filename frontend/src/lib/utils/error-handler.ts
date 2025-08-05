// BFF 錯誤處理工具
import { ApiClient, type BFFError } from '$lib/api/client';

/**
 * 統一的錯誤處理函數
 */
export function handleApiError(error: unknown): {
  message: string;
  code?: string;
  details?: any;
  shouldRetry?: boolean;
} {
  // BFF 錯誤
  if (ApiClient.isBFFError(error)) {
    const bffError = error as BFFError;
    return {
      message: bffError.message,
      code: bffError.code,
      details: bffError.details,
      shouldRetry: shouldRetryError(bffError.code),
    };
  }

  // Axios 錯誤
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as any;
    return {
      message: axiosError.response?.data?.message || axiosError.message || '請求失敗',
      code: `HTTP_${axiosError.response?.status}`,
      shouldRetry: shouldRetryHttpStatus(axiosError.response?.status),
    };
  }

  // 網路錯誤
  if (error && typeof error === 'object' && 'message' in error) {
    const networkError = error as Error;
    return {
      message: networkError.message.includes('Network') ? '網路連接失敗' : networkError.message,
      code: 'NETWORK_ERROR',
      shouldRetry: true,
    };
  }

  // 未知錯誤
  return {
    message: '發生未知錯誤',
    code: 'UNKNOWN_ERROR',
    shouldRetry: false,
  };
}

/**
 * 判斷是否應該重試的錯誤代碼
 */
function shouldRetryError(code: string): boolean {
  const retryableCodes = [
    'NETWORK_ERROR',
    'TIMEOUT_ERROR',
    'RATE_LIMITED',
    'INTERNAL_ERROR',
  ];
  return retryableCodes.includes(code);
}

/**
 * 判斷是否應該重試的 HTTP 狀態碼
 */
function shouldRetryHttpStatus(status?: number): boolean {
  if (!status) return false;
  
  // 5xx 服務器錯誤通常可以重試
  if (status >= 500) return true;
  
  // 429 限流錯誤可以重試
  if (status === 429) return true;
  
  // 408 請求超時可以重試
  if (status === 408) return true;
  
  return false;
}

/**
 * 格式化用戶友好的錯誤訊息
 */
export function formatUserFriendlyError(error: unknown): string {
  const { message, code } = handleApiError(error);
  
  // 根據錯誤代碼提供用戶友好的訊息
  const userFriendlyMessages: Record<string, string> = {
    'UNAUTHORIZED': '請重新登入',
    'FORBIDDEN': '您沒有權限執行此操作',
    'NOT_FOUND': '請求的資源不存在',
    'VALIDATION_ERROR': '輸入的資料格式不正確',
    'RATE_LIMITED': '請求過於頻繁，請稍後再試',
    'NETWORK_ERROR': '網路連接失敗，請檢查您的網路連接',
    'TIMEOUT_ERROR': '請求超時，請稍後再試',
    'INTERNAL_ERROR': '伺服器發生錯誤，請稍後再試',
  };
  
  return code && userFriendlyMessages[code] ? userFriendlyMessages[code] : message;
}

/**
 * 錯誤重試工具
 */
export async function retryOnError<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  delay: number = 1000
): Promise<T> {
  let lastError: unknown;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      const errorInfo = handleApiError(error);
      
      // 如果是最後一次嘗試或錯誤不可重試，直接拋出
      if (attempt === maxRetries || !errorInfo.shouldRetry) {
        throw error;
      }
      
      // 指數退避延遲
      const waitTime = delay * Math.pow(2, attempt);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
  }
  
  throw lastError;
}