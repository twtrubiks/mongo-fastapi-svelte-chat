// BFF 層的後端 API 客戶端
// 專門用於從 SvelteKit API 路由調用後端服務

import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios';
import { env } from '$env/dynamic/private';

export class BFFBackendClient {
  private client: AxiosInstance;

  constructor(baseURL?: string) {
    // 動態決定後端 API URL
    const defaultBaseURL = this.getDefaultBaseURL();
    
    this.client = axios.create({
      baseURL: baseURL || defaultBaseURL,
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }
  
  private getDefaultBaseURL(): string {
    // BFFBackendClient 僅在 SSR server-side 環境中使用
    return env['BACKEND_URL'] || 'http://localhost:8000';
  }

  // 組合 per-request headers（含 token 與真實 client IP）
  private buildHeaders(options: { headers?: Record<string, string>; token?: string; clientIp?: string }): Record<string, string> | undefined {
    const authHeader = options.token ? { Authorization: `Bearer ${options.token}` } : undefined;
    // 轉發瀏覽器真實 IP 給後端 rate limiter 分桶（後端只信任來自 BFF 的此標頭）
    const ipHeader = options.clientIp ? { 'X-Forwarded-For': options.clientIp } : undefined;
    if (!authHeader && !ipHeader && !options.headers) return undefined;
    return { ...authHeader, ...ipHeader, ...options.headers };
  }

  // 統一的請求處理
  async request<T>(endpoint: string, options: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    data?: unknown;
    headers?: Record<string, string>;
    token?: string;
    clientIp?: string;
  } = {}): Promise<T> {
    try {
      const config: AxiosRequestConfig = {
        url: endpoint,
        method: options.method || 'GET',
        data: options.data,
      };

      const headers = this.buildHeaders(options);
      if (headers) {
        config.headers = headers;
      }

      const response = await this.client.request(config);
      return response.data;
    } catch (error: unknown) {
      // 統一錯誤處理
      if (axios.isAxiosError(error)) {
        throw {
          code: error.response?.status || 'NETWORK_ERROR',
          message: extractErrorMessage(error.response?.data) ?? error.message,
          details: error.response?.data,
        };
      }
      throw {
        code: 'NETWORK_ERROR',
        message: error instanceof Error ? error.message : '未知錯誤',
      };
    }
  }

}

// 從後端錯誤回應取出字串訊息（前端只認字串的 error.message）：
// 業務錯誤 {detail: "..."}、欄位驗證 {detail: [{msg}]}、全域錯誤 {error: {message}}、限流 {message}
function extractErrorMessage(data: unknown): string | undefined {
  if (typeof data !== 'object' || data === null) return undefined;
  const body = data as { detail?: unknown; error?: { message?: unknown }; message?: unknown };

  if (typeof body.detail === 'string') return body.detail;
  if (Array.isArray(body.detail)) {
    const messages = body.detail
      .map((item: { msg?: unknown }) => item?.msg)
      .filter((msg): msg is string => typeof msg === 'string');
    if (messages.length > 0) return messages.join('; ');
  }
  if (typeof body.error?.message === 'string') return body.error.message;
  if (typeof body.message === 'string') return body.message;
  return undefined;
}

// 全域實例
export const bffBackendClient = new BFFBackendClient();