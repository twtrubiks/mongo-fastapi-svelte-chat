import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios';
import type {
  LoginData,
  RegisterData,
  AuthResponse,
  RoomCreate,
  MessageCreate,
  User,
  Room,
  RoomSummary,
  Message,
  Notification,
  RequestOptions,
  RoomJoinRequest,
} from '../types';
import type { NotificationStats } from '../stores/notification.svelte';

// 通知列表回應格式（非 BFF 包裝）
interface NotificationListResponse {
  notifications: Notification[];
  total?: number;
  page?: number;
  limit?: number;
}
import type { BFFResponse } from '../bff-types';

// BFF 錯誤類型
interface BFFError extends Error {
  code: string;
  details?: any;
  response?: AxiosResponse<BFFResponse<any>> | undefined;
}

// 創建 BFF 錯誤
function createBFFError(message: string, code: string, details?: any, response?: AxiosResponse | undefined): BFFError {
  const error = new Error(message) as BFFError;
  error.name = 'BFFError';
  error.code = code;
  error.details = details;
  error.response = response;
  return error;
}

/**
 * API 客戶端
 *
 * 不再管理 token —— token 由 httpOnly cookie 自動隨請求送出，
 * BFF 層負責從 cookie 讀取 token 並透明 refresh。
 */
export class ApiClient {
  private client: AxiosInstance;

  // 認證徹底失敗（BFF refresh 也失敗）後的回調
  onAuthFailure: (() => void) | null = null;

  constructor(baseURL: string = '') {
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
      // 確保瀏覽器自動帶上 cookie（同源請求預設就會）
      withCredentials: true,
    });

    // BFF 響應攔截器
    this.client.interceptors.response.use(
      (response: AxiosResponse) => {
        if (this.isBFFResponse(response.data)) {
          const bffResponse = response.data as BFFResponse;

          if (bffResponse.success) {
            response.data = bffResponse.data;

            if (bffResponse.meta) {
              response.headers['x-bff-request-id'] = bffResponse.meta.requestId;
              response.headers['x-bff-timestamp'] = bffResponse.meta.timestamp;
            }
          } else {
            const error = bffResponse.error!;
            throw createBFFError(error.message, error.code, error.details, response);
          }
        }
        return response;
      },
      async (error) => {
        // 處理 BFF 錯誤響應
        if (error.response && this.isBFFResponse(error.response.data)) {
          const bffResponse = error.response.data as BFFResponse;
          if (!bffResponse.success && bffResponse.error) {
            throw createBFFError(
              bffResponse.error.message,
              bffResponse.error.code,
              bffResponse.error.details,
              error.response
            );
          }
        }

        // 401 → BFF 的透明 refresh 已經嘗試過了，還是 401 表示徹底失敗
        if (error.response?.status === 401) {
          this.onAuthFailure?.();
        }

        return Promise.reject(error);
      }
    );
  }

  // BFF 響應檢測
  private isBFFResponse(data: any): data is BFFResponse {
    return (
      data &&
      typeof data === 'object' &&
      typeof data.success === 'boolean' &&
      ('data' in data || 'error' in data)
    );
  }

  // BFF 請求方法
  private async bffRequest<T>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    url: string,
    options: {
      data?: any;
      params?: any;
      headers?: Record<string, string>;
    } = {}
  ): Promise<T> {
    try {
      const config: AxiosRequestConfig = {
        method,
        url,
        data: options.data,
        params: options.params,
      };

      if (options.headers) {
        config.headers = { ...config.headers, ...options.headers };
      }

      const response = await this.client.request<T>(config);
      return response.data;
    } catch (error) {
      if (error instanceof Error && error.name === 'BFFError') {
        throw error;
      }
      throw error;
    }
  }

  // 通用請求方法
  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const config: AxiosRequestConfig = {
      method: options.method || 'GET',
      url: endpoint,
      data: options.body,
    };

    if (options.headers) {
      config.headers = options.headers;
    }

    const response = await this.client.request<T>(config);
    return response.data;
  }

  // 認證相關 API
  auth = {
    login: async (credentials: LoginData): Promise<AuthResponse> => {
      const formData = new URLSearchParams();
      formData.append('username', credentials.username);
      formData.append('password', credentials.password);

      const response = await this.client.post<AuthResponse>('/api/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      // BFF 回傳 { user }，token 已在 httpOnly cookie 中
      return response.data;
    },

    register: async (userData: RegisterData): Promise<AuthResponse> => {
      return this.request<AuthResponse>('/api/auth/register', {
        method: 'POST',
        body: userData,
      });
    },

    verify: async (): Promise<User> => {
      return this.request<User>('/api/auth/me');
    },

    getProfile: async (): Promise<User> => {
      return this.bffRequest<User>('GET', '/api/auth/profile');
    },

    updateProfile: async (userData: {
      full_name?: string;
      email?: string;
      password?: string;
      avatar?: string;
    }): Promise<User> => {
      return this.bffRequest<User>('PUT', '/api/auth/profile', { data: userData });
    },

    changePassword: async (data: {
      current_password: string;
      new_password: string;
    }): Promise<{ message: string }> => {
      return this.bffRequest<{ message: string }>('PUT', '/api/auth/change-password', { data });
    },

    logout: async (): Promise<void> => {
      return this.bffRequest<void>('POST', '/api/auth/logout');
    },
  };

  // 聊天室相關 API
  rooms = {
    list: async (options?: { limit?: number; offset?: number; search?: string; exclude_joined?: boolean }): Promise<RoomSummary[]> => {
      const params = new URLSearchParams();
      if (options?.limit) params.append('limit', options.limit.toString());
      if (options?.offset) params.append('offset', options.offset.toString());
      if (options?.search) params.append('search', options.search);
      if (options?.exclude_joined) params.append('exclude_joined', 'true');

      const queryString = params.toString();
      const url = queryString ? `/api/rooms?${queryString}` : '/api/rooms';
      return this.bffRequest<RoomSummary[]>('GET', url);
    },

    myRooms: async (options?: { limit?: number; offset?: number }): Promise<RoomSummary[]> => {
      const params: Record<string, number> = {};
      if (options?.limit != null) params['limit'] = options.limit;
      if (options?.offset != null) params['offset'] = options.offset;
      return this.bffRequest<RoomSummary[]>('GET', '/api/rooms/my', { params });
    },

    create: async (roomData: RoomCreate): Promise<Room> => {
      return this.bffRequest<Room>('POST', '/api/rooms/', { data: roomData });
    },

    get: async (roomId: string): Promise<Room> => {
      return this.bffRequest<Room>('GET', `/api/rooms/${roomId}`);
    },

    join: async (roomId: string, joinRequest?: RoomJoinRequest): Promise<void> => {
      if (joinRequest) {
        await this.bffRequest<void>('POST', `/api/rooms/${roomId}/join-advanced`, { data: joinRequest });
      } else {
        await this.bffRequest<void>('POST', `/api/rooms/${roomId}/join`);
      }
    },

    leave: async (roomId: string): Promise<void> => {
      await this.bffRequest<void>('POST', `/api/rooms/${roomId}/leave`);
    },

    getMembers: async (roomId: string, options?: { limit?: number; offset?: number }): Promise<User[]> => {
      const params: Record<string, number> = {};
      if (options?.limit != null) params['limit'] = options.limit;
      if (options?.offset != null) params['offset'] = options.offset;
      return this.bffRequest<User[]>('GET', `/api/rooms/${roomId}/members`, { params });
    },

    updateSettings: async (roomId: string, settings: Partial<RoomCreate>): Promise<Room> => {
      return this.bffRequest<Room>('PUT', `/api/rooms/${roomId}`, { data: settings });
    },

    delete: async (roomId: string): Promise<{ message: string; roomId: string }> => {
      return this.bffRequest<{ message: string; roomId: string }>('DELETE', `/api/rooms/${roomId}`);
    },
  };

  // 訊息相關 API
  messages = {
    list: async (roomId: string, limit: number = 50, offset: number = 0): Promise<Message[]> => {
      return this.bffRequest<Message[]>('GET', `/api/rooms/${roomId}/messages`, {
        params: { limit, offset },
      });
    },

    send: async (roomId: string, messageData: MessageCreate): Promise<Message> => {
      return this.bffRequest<Message>('POST', `/api/rooms/${roomId}/messages`, { data: messageData });
    },

    search: async (roomId: string, query: {
      keyword?: string;
      message_type?: 'text' | 'image' | 'file' | 'system';
      user_id?: string;
      start_date?: string;
      end_date?: string;
      page?: number;
      page_size?: number;
    }): Promise<Message[]> => {
      return this.request<Message[]>(`/api/messages/room/${roomId}/search`, {
        method: 'POST',
        body: query,
      });
    },
  };

  // 通知相關 API
  notifications = {
    list: async (options?: {
      page?: number;
      limit?: number;
      status?: 'UNREAD' | 'READ';
      type?: 'MESSAGE' | 'SYSTEM';
    }): Promise<NotificationListResponse> => {
      const params = new URLSearchParams();
      if (options?.page) params.append('page', options.page.toString());
      if (options?.limit) params.append('limit', options.limit.toString());
      if (options?.status) params.append('status', options.status);
      if (options?.type) params.append('type', options.type);

      const queryString = params.toString();
      const url = queryString ? `/api/notifications/?${queryString}` : '/api/notifications/';
      return this.request<NotificationListResponse>(url);
    },

    stats: async (): Promise<NotificationStats> => {
      return this.bffRequest<NotificationStats>('GET', '/api/notifications/stats');
    },

    markAsRead: async (notificationId: string): Promise<void> => {
      return this.bffRequest<void>('POST', `/api/notifications/${notificationId}/read`);
    },

    markAllAsRead: async (): Promise<void> => {
      return this.bffRequest<void>('POST', '/api/notifications/read-all');
    },

    delete: async (notificationId: string): Promise<void> => {
      return this.bffRequest<void>('DELETE', `/api/notifications/${notificationId}`);
    },

    clearAll: async (): Promise<void> => {
      return this.bffRequest<void>('DELETE', '/api/notifications/');
    },
  };

  // 檔案上傳相關 API
  files = {
    uploadImage: async (data: File | FormData): Promise<{ url: string; filename: string }> => {
      const formData = data instanceof FormData ? data : new FormData();
      if (data instanceof File) {
        formData.append('file', data);
      }
      formData.append('type', 'image');

      const response = await this.client.post<{ file: { url: string; filename: string } }>('/api/files', formData, {
        headers: { 'Content-Type': undefined as any }
      });

      return {
        url: response.data.file.url,
        filename: response.data.file.filename,
      };
    },
  };

  // WS ticket API（供 WS manager 使用）
  wsTicket = {
    create: async (roomId: string): Promise<string> => {
      const result = await this.bffRequest<{ ticket: string }>('POST', '/api/ws/ticket', {
        data: { room_id: roomId },
      });
      return result.ticket;
    },
  };
}

// 全域 API 客戶端實例
const getBaseURL = () => {
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  return 'http://localhost:5173';
};

export const apiClient = new ApiClient(getBaseURL());
