// BFF 層的後端 API 客戶端
// 專門用於從 SvelteKit API 路由調用後端服務

import axios, { type AxiosInstance } from 'axios';

export interface BFFApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  meta?: {
    timestamp: string;
    requestId: string;
  };
}

export class BFFBackendClient {
  private client: AxiosInstance;

  constructor(baseURL: string = 'http://localhost:8000') {
    this.client = axios.create({
      baseURL,
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  // 設置認證 token
  setAuth(token: string) {
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  // 移除認證
  clearAuth() {
    delete this.client.defaults.headers.common['Authorization'];
  }

  // 統一的請求處理
  async request<T>(endpoint: string, options: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    data?: any;
    headers?: Record<string, string>;
  } = {}): Promise<T> {
    try {
      const config: any = {
        url: endpoint,
        method: options.method || 'GET',
        data: options.data,
      };
      
      if (options.headers) {
        config.headers = options.headers;
      }
      
      const response = await this.client.request(config);
      return response.data;
    } catch (error: any) {
      // 統一錯誤處理
      throw {
        code: error.response?.status || 'NETWORK_ERROR',
        message: error.response?.data?.detail || error.message,
        details: error.response?.data,
      };
    }
  }

  // 原始請求處理（用於二進制數據如圖片）
  async requestRaw(endpoint: string, options: {
    method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
    data?: any;
    headers?: Record<string, string>;
    responseType?: 'arraybuffer' | 'blob' | 'stream';
  } = {}) {
    try {
      const config: any = {
        url: endpoint,
        method: options.method || 'GET',
        data: options.data,
        responseType: options.responseType || 'arraybuffer',
      };
      
      if (options.headers) {
        config.headers = options.headers;
      }
      
      const response = await this.client.request(config);
      return {
        data: response.data,
        headers: response.headers,
        status: response.status,
      };
    } catch (error: any) {
      // 統一錯誤處理
      throw {
        code: error.response?.status || 'NETWORK_ERROR',
        message: error.response?.data?.detail || error.message,
        details: error.response?.data,
      };
    }
  }

  // 並行請求工具
  async parallel<T extends Record<string, any>>(
    requests: Record<keyof T, () => Promise<any>>
  ): Promise<T> {
    const entries = Object.entries(requests) as [keyof T, () => Promise<any>][];
    const promises = entries.map(async ([key, fn]) => {
      try {
        const result = await fn();
        return [key, result];
      } catch (error) {
        console.error(`Request failed for ${String(key)}:`, error);
        return [key, null];
      }
    });

    const results = await Promise.all(promises);
    return Object.fromEntries(results) as T;
  }
}

// 全域實例
export const bffBackendClient = new BFFBackendClient();