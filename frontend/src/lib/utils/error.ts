/**
 * 從錯誤物件中提取使用者友善的錯誤訊息
 * 支援 FastAPI（detail）、BFF（error.message）和一般 Error 格式
 */
export function extractErrorMessage(error: unknown, fallback = '發生錯誤'): string {
  if (!error) return fallback;
  const err = error as any;
  return err.response?.data?.detail
    ?? err.response?.data?.error?.message
    ?? err.message
    ?? fallback;
}
