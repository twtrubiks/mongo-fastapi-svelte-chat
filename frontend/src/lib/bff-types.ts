import type {
  User, RoomSummary, Notification,
} from './types';

// BFF API 響應格式
export interface BFFResponse<T = any> {
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
    performance?: {
      duration: number;
      queries: number;
    };
  };
}

// 儀表板聚合資料
export interface DashboardData {
  user: User;
  rooms: RoomSummary[];
  unreadCount: number;
  notifications: Notification[];
}

// 加入房間響應
export interface JoinRoomResponse {
  success: boolean;
  message: string;
  room?: RoomSummary;
  requiresAction?: {
    type: 'password' | 'invite_code' | 'error';
    message: string;
  };
}
