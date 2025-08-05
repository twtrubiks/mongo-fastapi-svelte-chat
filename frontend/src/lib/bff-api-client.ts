// 前端 BFF API 客戶端
// 專門用於調用 SvelteKit API 路由

import type { 
  BFFResponse, 
  DashboardData, 
  RoomSummaryData, 
  AuthAggregateData, 
  SearchAggregateData,
  RoomPermissionsData,
  JoinRoomResponse,
  InvitationManageData
} from './bff-types';
import type {
  RoomJoinRequest,
  InvitationCreate,
  JoinRequestCreate,
  JoinRequestReview
} from './types';

export class BFFApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = '') {
    this.baseUrl = baseUrl;
  }

  // 通用請求方法
  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<BFFResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    
    if (!response.ok) {
      // 如果響應不是 JSON，創建基本錯誤
      try {
        const errorData = await response.json();
        return errorData;
      } catch {
        return {
          success: false,
          error: {
            code: 'HTTP_ERROR',
            message: `HTTP ${response.status}: ${response.statusText}`,
          },
        };
      }
    }
    
    return await response.json();
  }

  // 儀表板 API
  dashboard = {
    // 獲取儀表板聚合資料
    get: async (): Promise<BFFResponse<DashboardData>> => {
      return this.request<DashboardData>('/api/dashboard');
    },

    // 刷新儀表板
    refresh: async (): Promise<BFFResponse<{ message: string }>> => {
      return this.request<{ message: string }>('/api/dashboard', {
        method: 'POST',
        body: JSON.stringify({ action: 'refresh' }),
      });
    },
  };

  // 聊天室摘要 API
  rooms = {
    // 獲取聊天室摘要
    getSummary: async (roomId: string): Promise<BFFResponse<RoomSummaryData>> => {
      return this.request<RoomSummaryData>(`/api/rooms/${roomId}/summary`);
    },

    // 刷新聊天室摘要
    refreshSummary: async (roomId: string): Promise<BFFResponse<{ message: string }>> => {
      return this.request<{ message: string }>(`/api/rooms/${roomId}/summary`, {
        method: 'POST',
        body: JSON.stringify({ action: 'refresh' }),
      });
    },

    // 標記房間訊息為已讀
    markAsRead: async (roomId: string): Promise<BFFResponse<{ message: string }>> => {
      return this.request<{ message: string }>(`/api/rooms/${roomId}/summary`, {
        method: 'POST',
        body: JSON.stringify({ action: 'mark_read' }),
      });
    },

    // 獲取房間權限
    getPermissions: async (roomId: string): Promise<BFFResponse<RoomPermissionsData>> => {
      return this.request<RoomPermissionsData>(`/api/rooms/${roomId}/permissions`);
    },

    // 檢查加入要求
    checkJoinRequirements: async (roomId: string): Promise<BFFResponse<any>> => {
      return this.request<any>(`/api/rooms/${roomId}/join-advanced`);
    },

    // 進階加入房間
    joinAdvanced: async (roomId: string, joinRequest: RoomJoinRequest): Promise<BFFResponse<JoinRoomResponse>> => {
      return this.request<JoinRoomResponse>(`/api/rooms/${roomId}/join-advanced`, {
        method: 'POST',
        body: JSON.stringify(joinRequest),
      });
    },
  };

  // 認證聚合 API
  auth = {
    // 獲取認證聚合資料
    getAggregate: async (): Promise<BFFResponse<AuthAggregateData>> => {
      return this.request<AuthAggregateData>('/api/auth');
    },

    // 刷新 token
    refreshToken: async (): Promise<BFFResponse<any>> => {
      return this.request('/api/auth', {
        method: 'POST',
        body: JSON.stringify({ action: 'refresh_token' }),
      });
    },

    // 更新用戶設置
    updateSettings: async (settings: any): Promise<BFFResponse<any>> => {
      return this.request('/api/auth', {
        method: 'POST',
        body: JSON.stringify({ 
          action: 'update_settings', 
          data: settings 
        }),
      });
    },

    // 登出
    logout: async (): Promise<BFFResponse<{ message: string }>> => {
      return this.request<{ message: string }>('/api/auth', {
        method: 'POST',
        body: JSON.stringify({ action: 'logout' }),
      });
    },

    // 更改密碼
    changePassword: async (passwordData: any): Promise<BFFResponse<any>> => {
      return this.request('/api/auth', {
        method: 'POST',
        body: JSON.stringify({ 
          action: 'change_password', 
          data: passwordData 
        }),
      });
    },
  };

  // 搜尋聚合 API
  search = {
    // 跨房間搜尋
    messages: async (searchParams: {
      keyword?: string;
      message_type?: string;
      room_id?: string;
      user_id?: string;
      start_date?: string;
      end_date?: string;
      page?: number;
      pageSize?: number;
    }): Promise<BFFResponse<SearchAggregateData>> => {
      return this.request<SearchAggregateData>('/api/messages/search', {
        method: 'POST',
        body: JSON.stringify(searchParams),
      });
    },
  };

  // 檔案 API
  files = {
    // 上傳檔案
    upload: async (
      file: File, 
      type: string = 'general',
      description?: string
    ): Promise<BFFResponse<any>> => {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('type', type);
      if (description) {
        formData.append('description', description);
      }

      const response = await fetch('/api/files', {
        method: 'POST',
        body: formData,
      });

      return await response.json();
    },

    // 獲取檔案資訊
    getInfo: async (
      type: string, 
      filename: string
    ): Promise<BFFResponse<any>> => {
      return this.request(`/api/files?type=${type}&filename=${filename}`);
    },

    // 刪除檔案
    delete: async (
      type: string, 
      filename: string
    ): Promise<BFFResponse<{ message: string }>> => {
      return this.request<{ message: string }>(
        `/api/files?type=${type}&filename=${filename}`,
        { method: 'DELETE' }
      );
    },
  };

  // 邀請管理 API
  invitations = {
    // 獲取邀請管理資料
    getManageData: async (roomId: string): Promise<BFFResponse<InvitationManageData>> => {
      return this.request<InvitationManageData>(`/api/invitations/manage?room_id=${roomId}`);
    },

    // 創建邀請
    create: async (roomId: string, invitationData: InvitationCreate): Promise<BFFResponse<any>> => {
      return this.request<any>('/api/invitations/manage', {
        method: 'POST',
        body: JSON.stringify({
          action: 'create_invitation',
          data: { ...invitationData, room_id: roomId }
        }),
      });
    },

    // 驗證邀請碼
    validate: async (inviteCode: string): Promise<BFFResponse<any>> => {
      const result = await this.request<any>('/api/invitations/validate', {
        method: 'POST',
        body: JSON.stringify({
          inviteCode
        }),
      });
      
      return result;
    },

    // 撤銷邀請
    revoke: async (inviteCode: string): Promise<BFFResponse<any>> => {
      return this.request<any>('/api/invitations/manage', {
        method: 'POST',
        body: JSON.stringify({
          action: 'revoke_invitation',
          data: { inviteCode }
        }),
      });
    },

    // 創建加入申請
    createJoinRequest: async (roomId: string, requestData: JoinRequestCreate): Promise<BFFResponse<any>> => {
      return this.request<any>('/api/invitations/manage', {
        method: 'POST',
        body: JSON.stringify({
          action: 'create_join_request',
          data: { ...requestData, room_id: roomId }
        }),
      });
    },

    // 審核加入申請
    reviewJoinRequest: async (requestId: string, review: JoinRequestReview): Promise<BFFResponse<any>> => {
      return this.request<any>('/api/invitations/manage', {
        method: 'POST',
        body: JSON.stringify({
          action: 'review_join_request',
          data: { requestId, review }
        }),
      });
    },
  };

  // 批量請求工具
  async batch<T extends Record<string, () => Promise<BFFResponse<any>>>>(
    requests: T
  ): Promise<{ [K in keyof T]: Awaited<ReturnType<T[K]>> }> {
    const entries = Object.entries(requests) as [keyof T, () => Promise<any>][];
    const promises = entries.map(async ([key, request]) => {
      try {
        const result = await request();
        return [key, result];
      } catch (error) {
        return [key, {
          success: false,
          error: {
            code: 'REQUEST_FAILED',
            message: '請求失敗',
            details: error,
          },
        }];
      }
    });

    const results = await Promise.all(promises);
    return Object.fromEntries(results) as { [K in keyof T]: Awaited<ReturnType<T[K]>> };
  }
}

// 全域 BFF API 客戶端實例
export const bffApiClient = new BFFApiClient();

// 類型守衛函數
export function isSuccessResponse<T>(response: BFFResponse<T>): response is BFFResponse<T> & { success: true; data: T } {
  return response.success && response.data !== undefined;
}

export function isErrorResponse<T>(response: BFFResponse<T>): response is BFFResponse<T> & { success: false; error: NonNullable<BFFResponse<T>['error']> } {
  return !response.success && response.error !== undefined;
}