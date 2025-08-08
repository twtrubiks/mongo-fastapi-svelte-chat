import axios, { type AxiosInstance, type AxiosRequestConfig, type AxiosResponse } from 'axios';
import type { 
  LoginData, 
  RegisterData, 
  AuthResponse, 
  RoomCreate, 
  MessageCreate, 
  User, 
  Room, 
  Message, 
  RequestOptions,
  RoomJoinRequest,
  RoomInvitation,
  InvitationCreate,
  JoinRequest,
  JoinRequestCreate,
  JoinRequestReview
} from '../types';

// BFF 響應類型定義
interface BFFResponse<T = any> {
  success: boolean;
  data: T;
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

// 導出類型
export type { BFFResponse, BFFError };

export class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;

  constructor(baseURL: string = '') {
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // 類型安全的 BFF 響應攔截器
    this.client.interceptors.response.use(
      (response: AxiosResponse) => {
        // 檢查是否為 BFF 響應格式
        if (this.isBFFResponse(response.data)) {
          const bffResponse = response.data as BFFResponse;
          
          if (bffResponse.success) {
            // 成功響應：解包數據並保留 meta 信息
            response.data = bffResponse.data;
            
            // 可選：將 meta 信息添加到響應 headers 中以供調試
            if (bffResponse.meta) {
              response.headers['x-bff-request-id'] = bffResponse.meta.requestId;
              response.headers['x-bff-timestamp'] = bffResponse.meta.timestamp;
            }
          } else {
            // 失敗響應：拋出類型化的 BFF 錯誤
            const error = bffResponse.error!;
            throw createBFFError(
              error.message,
              error.code,
              error.details,
              response
            );
          }
        }
        return response;
      },
      (error) => {
        // 處理網路錯誤或 HTTP 錯誤
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
        return Promise.reject(error);
      }
    );

    // 請求攔截器 - 自動添加認證 header
    this.client.interceptors.request.use(
      (config) => {
        if (this.token) {
          config.headers.Authorization = `Bearer ${this.token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // 移除重複的響應攔截器，只保留 BFF 響應攔截器
  }

  setToken(token: string | null) {
    this.token = token;
  }

  // BFF 響應檢測方法
  private isBFFResponse(data: any): data is BFFResponse {
    return (
      data &&
      typeof data === 'object' &&
      typeof data.success === 'boolean' &&
      ('data' in data || 'error' in data)
    );
  }

  // 類型安全的 BFF 請求方法
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
      
      // 正確處理 headers
      if (options.headers) {
        config.headers = { ...config.headers, ...options.headers };
      }
      
      const response = await this.client.request<T>(config);
      return response.data;
    } catch (error) {
      // 如果是 BFFError，直接拋出
      if (error instanceof Error && error.name === 'BFFError') {
        throw error;
      }
      // 否則包裝為標準錯誤
      throw error;
    }
  }

  // BFF 錯誤處理工具方法
  public static isBFFError(error: any): error is BFFError {
    return error instanceof Error && error.name === 'BFFError';
  }

  // 獲取 BFF 請求 ID（用於調試）
  public static getBFFRequestId(response: AxiosResponse): string | null {
    return response.headers['x-bff-request-id'] || null;
  }

  // 獲取 BFF 時間戳（用於調試）
  public static getBFFTimestamp(response: AxiosResponse): string | null {
    return response.headers['x-bff-timestamp'] || null;
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
      
      // 響應攔截器已經自動解包 BFF 響應格式
      this.setToken(response.data.access_token);
      return response.data;
    },

    register: async (userData: RegisterData): Promise<AuthResponse> => {
      return this.request<AuthResponse>('/api/auth/register', {
        method: 'POST',
        body: userData,
      });
    },

    verify: async (token: string): Promise<User> => {
      this.setToken(token);
      return this.request<User>('/api/auth/me');
    },

    me: async (): Promise<User> => {
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
      return this.bffRequest<User>('PUT', '/api/auth/profile', {
        data: userData,
      });
    },

    deleteAccount: async (): Promise<void> => {
      return this.bffRequest<void>('DELETE', '/api/auth/profile');
    },
  };

  // 聊天室相關 API
  rooms = {
    list: async (options?: { limit?: number; offset?: number; search?: string }): Promise<Room[]> => {
      const params = new URLSearchParams();
      if (options?.limit) params.append('limit', options.limit.toString());
      if (options?.offset) params.append('offset', options.offset.toString());
      if (options?.search) params.append('search', options.search);
      
      const queryString = params.toString();
      const url = queryString ? `/api/rooms?${queryString}` : '/api/rooms';
      
      return this.bffRequest<Room[]>('GET', url);
    },

    // 獲取用戶已加入的房間列表
    myRooms: async (): Promise<Room[]> => {
      return this.bffRequest<Room[]>('GET', '/api/rooms/my');
    },

    create: async (roomData: RoomCreate): Promise<Room> => {
      return this.bffRequest<Room>('POST', '/api/rooms/', {
        data: roomData,
      });
    },

    get: async (roomId: string): Promise<Room> => {
      return this.bffRequest<Room>('GET', `/api/rooms/${roomId}`);
    },

    join: async (roomId: string, joinRequest?: RoomJoinRequest): Promise<void> => {
      if (joinRequest) {
        // 使用進階加入 API
        await this.bffRequest<void>('POST', `/api/rooms/${roomId}/join-advanced`, {
          data: joinRequest,
        });
      } else {
        // 使用原本的加入 API
        await this.bffRequest<void>('POST', `/api/rooms/${roomId}/join`);
      }
    },

    // 檢查加入要求
    checkJoinRequirements: async (roomId: string): Promise<any> => {
      return this.bffRequest<any>('GET', `/api/rooms/${roomId}/join-advanced`);
    },

    // 進階加入房間
    joinAdvanced: async (roomId: string, joinRequest: RoomJoinRequest): Promise<any> => {
      return this.bffRequest<any>('POST', `/api/rooms/${roomId}/join-advanced`, {
        data: joinRequest,
      });
    },

    // 獲取房間權限
    getPermissions: async (roomId: string): Promise<any> => {
      return this.bffRequest<any>('GET', `/api/rooms/${roomId}/permissions`);
    },

    leave: async (roomId: string): Promise<void> => {
      await this.bffRequest<void>('POST', `/api/rooms/${roomId}/leave`);
    },

    getMembers: async (roomId: string): Promise<User[]> => {
      return this.bffRequest<User[]>('GET', `/api/rooms/${roomId}/members`);
    },

    // 更新房間設定
    updateSettings: async (roomId: string, settings: Partial<RoomCreate>): Promise<Room> => {
      return this.bffRequest<Room>('PUT', `/api/rooms/${roomId}`, {
        data: settings,
      });
    },
  };

  // 訊息相關 API
  messages = {
    list: async (roomId: string, limit: number = 50): Promise<Message[]> => {
      return this.bffRequest<Message[]>('GET', `/api/rooms/${roomId}/messages`, {
        params: { limit },
      });
    },

    send: async (roomId: string, messageData: MessageCreate): Promise<Message> => {
      return this.bffRequest<Message>('POST', `/api/rooms/${roomId}/messages`, {
        data: messageData,
      });
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

  // 檔案上傳相關 API
  files = {
    upload: async (file: File): Promise<{ url: string; filename: string }> => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('type', 'general'); // 通用文件上傳類型

      // 使用直接的 POST 請求，因為需要處理 FormData
      const response = await this.client.post<{ file: { url: string; filename: string } }>('/api/files', formData, {
        headers: {
          // 清除 Content-Type，讓瀏覽器自動設置 multipart/form-data 和 boundary
          'Content-Type': undefined as any
        }
      });

      // BFF 響應攔截器已經處理了響應解包
      return {
        url: response.data.file.url,
        filename: response.data.file.filename,
      };
    },

    uploadImage: async (data: File | FormData): Promise<{ url: string; filename: string }> => {
      const formData = data instanceof FormData ? data : new FormData();
      if (data instanceof File) {
        formData.append('file', data);
      }
      
      // 添加類型參數，讓 BFF 知道這是圖片上傳
      formData.append('type', 'image');

      // 使用直接的 POST 請求，因為需要處理 FormData
      const response = await this.client.post<{ file: { url: string; filename: string } }>('/api/files', formData, {
        headers: {
          // 清除 Content-Type，讓瀏覽器自動設置 multipart/form-data 和 boundary
          'Content-Type': undefined as any
        }
      });

      // BFF 響應攔截器已經處理了響應解包
      return {
        url: response.data.file.url,
        filename: response.data.file.filename,
      };
    },
  };

  // 邀請相關 API
  invitations = {
    // 創建邀請
    create: async (roomId: string, invitationData: InvitationCreate): Promise<RoomInvitation> => {
      return this.bffRequest<RoomInvitation>('POST', '/api/invitations/manage', {
        data: {
          action: 'create_invitation',
          data: { ...invitationData, room_id: roomId }
        }
      });
    },

    // 獲取房間邀請列表
    listForRoom: async (roomId: string): Promise<RoomInvitation[]> => {
      const response = await this.bffRequest<any>('GET', `/api/invitations/manage?room_id=${roomId}`);
      return response.invitations || [];
    },

    // 驗證邀請碼
    validate: async (inviteCode: string): Promise<any> => {
      return this.bffRequest<any>('POST', '/api/invitations/manage', {
        data: {
          action: 'validate_invitation',
          data: { inviteCode }
        }
      });
    },

    // 撤銷邀請
    revoke: async (inviteCode: string): Promise<void> => {
      await this.bffRequest<void>('POST', '/api/invitations/manage', {
        data: {
          action: 'revoke_invitation',
          data: { inviteCode }
        }
      });
    },

    // 創建加入申請
    createJoinRequest: async (roomId: string, requestData: JoinRequestCreate): Promise<JoinRequest> => {
      return this.bffRequest<JoinRequest>('POST', '/api/invitations/manage', {
        data: {
          action: 'create_join_request',
          data: { ...requestData, room_id: roomId }
        }
      });
    },

    // 獲取房間的加入申請
    getJoinRequests: async (roomId: string): Promise<JoinRequest[]> => {
      const response = await this.bffRequest<any>('GET', `/api/invitations/manage?room_id=${roomId}`);
      return response.joinRequests || [];
    },

    // 審核加入申請
    reviewJoinRequest: async (requestId: string, review: JoinRequestReview): Promise<void> => {
      await this.bffRequest<void>('POST', '/api/invitations/manage', {
        data: {
          action: 'review_join_request',
          data: { requestId, review }
        }
      });
    },

    // 獲取邀請管理資料
    getManageData: async (roomId: string): Promise<any> => {
      return this.bffRequest<any>('GET', `/api/invitations/manage?room_id=${roomId}`);
    },
  };
}

// 全域 API 客戶端實例
// 在瀏覽器中使用當前 origin，在 SSR 中需要完整 URL
const getBaseURL = () => {
  if (typeof window !== 'undefined') {
    return window.location.origin;
  }
  // SSR 環境中的默認值，這個應該從環境變數或配置中獲取
  // 使用環境變數 PUBLIC_APP_URL 或默認值
  return process.env.PUBLIC_APP_URL || 'http://localhost:5173';
};

export const apiClient = new ApiClient(getBaseURL());