// BFF 層的後端 API 客戶端
// 專門用於從 SvelteKit API 路由調用後端服務

import axios, { type AxiosInstance } from 'axios';
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

  // 組合 per-request headers（含 token）
  private buildHeaders(options: { headers?: Record<string, string>; token?: string }): Record<string, string> | undefined {
    const authHeader = options.token ? { Authorization: `Bearer ${options.token}` } : undefined;
    if (!authHeader && !options.headers) return undefined;
    return { ...authHeader, ...options.headers };
  }

  // 統一的請求處理
  async request<T>(endpoint: string, options: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    data?: any;
    headers?: Record<string, string>;
    token?: string;
  } = {}): Promise<T> {
    try {
      const config: any = {
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
    } catch (error: any) {
      // 統一錯誤處理
      throw {
        code: error.response?.status || 'NETWORK_ERROR',
        message: error.response?.data?.detail ?? error.response?.data?.error?.message ?? error.message,
        details: error.response?.data,
      };
    }
  }

}

// 全域實例
export const bffBackendClient = new BFFBackendClient();