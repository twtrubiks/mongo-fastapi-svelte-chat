/**
 * 重試工具函數
 */

export interface RetryOptions {
  maxAttempts?: number;
  delayMs?: number;
  exponentialBackoff?: boolean;
  shouldRetry?: (error: unknown) => boolean;
}

/**
 * 執行帶有重試機制的異步函數
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  const {
    maxAttempts = 3,
    delayMs = 1000,
    exponentialBackoff = true,
    shouldRetry = isRetryableError
  } = options;

  let lastError: unknown;
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const result = await fn();
      
      // 成功則返回結果
      if (attempt > 1) {
        // 重試成功
      }
      
      return result;
    } catch (error) {
      lastError = error;
      
      console.warn(`[Retry] 第 ${attempt} 次嘗試失敗:`, error);
      
      // 如果是最後一次嘗試，或者錯誤不應該重試，直接拋出
      if (attempt === maxAttempts || !shouldRetry(error)) {
        throw error;
      }
      
      // 計算延遲時間
      const delay = exponentialBackoff 
        ? delayMs * Math.pow(2, attempt - 1)
        : delayMs;
      
      // 延遲後進行下次重試
      
      // 等待後重試
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  
  throw lastError;
}

/**
 * 判斷錯誤是否值得重試（網路錯誤或服務器錯誤）
 * 排除認證、權限、資源不存在等不可重試的錯誤
 */
export function isRetryableError(error: unknown): boolean {
  const err = error as { status?: number; response?: { status?: number }; code?: string; message?: string };
  const status = err.status || err.response?.status;

  // 不重試的錯誤：認證錯誤、權限錯誤、資源不存在
  if (status === 401 || status === 403 || status === 404) {
    return false;
  }

  // 重試的錯誤：網路錯誤、服務器錯誤、超時
  return (status ?? 0) >= 500 ||
         err.code === 'ECONNREFUSED' ||
         err.code === 'ENOTFOUND' ||
         (err.message?.includes('Network Error') ?? false) ||
         (err.message?.includes('timeout') ?? false) ||
         (err.message?.includes('Failed to fetch') ?? false);
}

/**
 * 房間相關的重試選項
 */
export const roomRetryOptions: RetryOptions = {
  maxAttempts: 3,
  delayMs: 500,
  exponentialBackoff: true,
  shouldRetry: isRetryableError,
};