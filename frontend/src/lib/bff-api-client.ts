// 前端 BFF API 客戶端
// 專門用於調用 SvelteKit API 路由

import type {
  BFFResponse,
  DashboardData,
  JoinRoomResponse,
} from './bff-types';
import type {
  RoomJoinRequest,
} from './types';

/** checkJoinRequirements 回傳結構 */
export interface JoinRequirementsData {
  isMember: boolean;
  requirements: {
    canDirectJoin: boolean;
    needsPassword: boolean;
    needsInviteCode: boolean;
  };
  room?: {
    member_count: number;
    [key: string]: unknown;
  };
  room_name?: string;
}

/** 檔案上傳回傳結構 */
export interface FileUploadData {
  file: {
    id: string;
    filename: string;
    original_name: string;
    file_type: string;
    content_type: string;
    size: number;
    url: string;
    created_at: string;
  };
  message?: string;
}

/** 邀請碼驗證回傳結構（BFF 轉換後的格式） */
export interface InvitationValidation {
  valid: boolean;
  room?: {
    id: string;
    name: string;
    inviter_name?: string;
  };
}

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

  };

  // 聊天室 API
  rooms = {
    // 檢查加入要求
    checkJoinRequirements: async (roomId: string): Promise<BFFResponse<JoinRequirementsData>> => {
      return this.request<JoinRequirementsData>(`/api/rooms/${roomId}/join-advanced`);
    },

    // 進階加入房間
    joinAdvanced: async (roomId: string, joinRequest: RoomJoinRequest): Promise<BFFResponse<JoinRoomResponse>> => {
      return this.request<JoinRoomResponse>(`/api/rooms/${roomId}/join-advanced`, {
        method: 'POST',
        body: JSON.stringify(joinRequest),
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
    ): Promise<BFFResponse<FileUploadData>> => {
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

      if (!response.ok) {
        try {
          return await response.json();
        } catch {
          return {
            success: false,
            error: { code: 'HTTP_ERROR', message: `HTTP ${response.status}: ${response.statusText}` },
          };
        }
      }

      return await response.json();
    },
  };

  // 邀請 API
  invitations = {
    // 驗證邀請碼
    validate: async (inviteCode: string): Promise<BFFResponse<InvitationValidation>> => {
      const result = await this.request<InvitationValidation>('/api/invitations/validate', {
        method: 'POST',
        body: JSON.stringify({
          inviteCode
        }),
      });

      return result;
    },
  };
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