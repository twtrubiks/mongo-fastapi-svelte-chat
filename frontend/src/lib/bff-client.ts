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
          message: error.response?.data?.detail ?? error.response?.data?.error?.message ?? error.message,
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

// 全域實例
export const bffBackendClient = new BFFBackendClient();