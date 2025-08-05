/**
 * 重試工具函數
 */

export interface RetryOptions {
  maxAttempts?: number;
  delayMs?: number;
  exponentialBackoff?: boolean;
  shouldRetry?: (error: any) => boolean;
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
    shouldRetry = (error) => {
      // 預設重試條件：網路錯誤或服務器錯誤
      return error.status >= 500 || 
             error.code === 'ECONNREFUSED' || 
             error.code === 'ENOTFOUND' ||
             error.message?.includes('Network Error') ||
             error.message?.includes('timeout');
    }
  } = options;

  let lastError: any;
  
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
 * 房間相關的重試選項
 */
export const roomRetryOptions: RetryOptions = {
  maxAttempts: 3,
  delayMs: 500,
  exponentialBackoff: true,
  shouldRetry: (error) => {
    // 房間操作的重試條件
    const status = error.status || error.response?.status;
    
    // 不重試的錯誤：認證錯誤、權限錯誤、資源不存在
    if (status === 401 || status === 403 || status === 404) {
      return false;
    }
    
    // 重試的錯誤：網路錯誤、服務器錯誤、超時
    return status >= 500 || 
           error.code === 'ECONNREFUSED' || 
           error.code === 'ENOTFOUND' ||
           error.message?.includes('Network Error') ||
           error.message?.includes('timeout') ||
           error.message?.includes('Failed to fetch');
  }
};