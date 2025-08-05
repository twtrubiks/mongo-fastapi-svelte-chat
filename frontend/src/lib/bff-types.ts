import type { 
  User, Room, Message, Notification, 
  RoomInvitation, JoinRequest, MemberRole 
} from './types';

// BFF API 響應格式
export interface BFFResponse<T> {
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
  rooms: Room[];
  unreadCount: number;
  recentActivity: Activity[];
  notifications: Notification[];
  onlineUsers: number;
  totalMessages: number;
}

// 聊天室摘要資料
export interface RoomSummaryData {
  room: Room;
  onlineUsers: User[];
  recentMessages: Message[];
  unreadCount: number;
  userPermissions: UserPermission[];
  messageStats: MessageStats;
}

// 活動記錄
export interface Activity {
  id: string;
  type: 'message' | 'room_join' | 'room_create' | 'user_register';
  user: {
    id: string;
    username: string;
    avatar?: string;
  };
  room?: {
    id: string;
    name: string;
  };
  content: string;
  timestamp: string;
}

// 用戶權限
export interface UserPermission {
  user_id: string;
  room_id: string;
  role: 'owner' | 'admin' | 'member';
  permissions: string[];
}

// 訊息統計
export interface MessageStats {
  total: number;
  today: number;
  thisWeek: number;
  byType: {
    text: number;
    image: number;
    system: number;
  };
  topUsers: Array<{
    user_id: string;
    username: string;
    count: number;
  }>;
}

// 搜尋聚合結果
export interface SearchAggregateData {
  results: SearchResult[];
  facets: SearchFacets;
  pagination: PaginationInfo;
  suggestions: string[];
  relatedRooms: Room[];
}

export interface SearchResult {
  message: Message;
  room: Room;
  highlights: string[];
  relevanceScore: number;
}

export interface SearchFacets {
  messageTypes: Array<{
    type: string;
    count: number;
  }>;
  users: Array<{
    user_id: string;
    username: string;
    count: number;
  }>;
  rooms: Array<{
    room_id: string;
    room_name: string;
    count: number;
  }>;
  timeRanges: Array<{
    range: string;
    count: number;
  }>;
}

export interface PaginationInfo {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

// 認證聚合響應
export interface AuthAggregateData {
  user: User;
  permissions: string[];
  activeRooms: Room[];
  recentActivity: Activity[];
  settings: UserSettings;
}

export interface UserSettings {
  theme: 'light' | 'dark' | 'auto';
  language: string;
  notifications: {
    email: boolean;
    push: boolean;
    sound: boolean;
  };
  privacy: {
    showOnlineStatus: boolean;
    allowDirectMessages: boolean;
  };
}

// 錯誤代碼
export enum BFFErrorCode {
  UNAUTHORIZED = 'UNAUTHORIZED',
  FORBIDDEN = 'FORBIDDEN',
  NOT_FOUND = 'NOT_FOUND',
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  NETWORK_ERROR = 'NETWORK_ERROR',
  INTERNAL_ERROR = 'INTERNAL_ERROR',
  RATE_LIMITED = 'RATE_LIMITED',
  SERVICE_UNAVAILABLE = 'SERVICE_UNAVAILABLE',
}

// 快取配置
export interface CacheConfig {
  ttl: number; // 秒
  key: string;
  tags?: string[];
}

// 效能監控
export interface PerformanceMetrics {
  apiCalls: number;
  totalDuration: number;
  cacheHits: number;
  cacheMisses: number;
  errors: number;
}

// 房間權限聚合資料
export interface RoomPermissionsData {
  room: Room;
  currentUserRole: MemberRole;
  permissions: string[];
  members: Array<{
    user: User;
    role: MemberRole;
    joined_at: string;
  }>;
  pendingInvitations?: RoomInvitation[];
  pendingRequests?: JoinRequest[];
  canManageRoom: boolean;
  canInviteMembers: boolean;
  canApproveRequests: boolean;
  canKickMembers: boolean;
}

// 加入房間響應
export interface JoinRoomResponse {
  success: boolean;
  message: string;
  room?: Room;
  requiresAction?: {
    type: 'password' | 'invite_code' | 'approval' | 'error';
    message: string;
  };
}

// 邀請管理聚合資料
export interface InvitationManageData {
  invitations: RoomInvitation[];
  joinRequests: JoinRequest[];
  canCreateInvitation: boolean;
  canReviewRequests: boolean;
}