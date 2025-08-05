// 基礎型別定義
export interface User {
  id?: string;
  _id?: string;  // MongoDB 格式
  user_id?: string;  // 其他可能的格式
  username: string;
  email?: string;
  full_name?: string;
  avatar?: string;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
  // 其他可能的屬性
  [key: string]: any;
}

// 房間權限相關枚舉
export enum RoomType {
  PUBLIC = 'public',        // 公開房間 - 任何人可見可加入
  PRIVATE = 'private'       // 私人房間 - 僅邀請加入
}

export enum JoinPolicy {
  DIRECT = 'direct',       // 直接加入
  INVITE = 'invite',       // 邀請鏈接
  PASSWORD = 'password'    // 密碼加入
}

export enum MemberRole {
  OWNER = 'owner',     // 房主 - 完全控制權
  ADMIN = 'admin',     // 管理員 - 成員管理權
  MEMBER = 'member',   // 成員 - 基本使用權
  GUEST = 'guest'      // 訪客 - 只讀權限
}

export interface Room {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  members: string[];
  member_roles?: Record<string, MemberRole>; // user_id -> role 映射
  is_public: boolean;  // 保留向後相容
  room_type?: RoomType;
  join_policy?: JoinPolicy;
  has_password?: boolean;
  invite_code?: string;
  created_at: string;
  updated_at?: string;
}

export interface Message {
  id: string;
  room_id: string;
  user_id: string;
  username?: string;  // 直接包含用戶名，利用 MongoDB 反規範化優勢
  content: string;
  type?: 'TEXT' | 'IMAGE' | 'SYSTEM';  // 新的類型字段
  message_type?: 'text' | 'image' | 'system';  // 保持向後兼容
  created_at: string;
  updated_at: string;
  user?: {
    id: string;
    username: string;
    full_name?: string;
    avatar?: string;
    created_at?: string;
  };
}

export interface Notification {
  id: string;
  user_id: string;
  title: string;
  content: string;
  type: 'MESSAGE' | 'ROOM_INVITE' | 'ROOM_JOIN' | 'ROOM_LEAVE' | 'SYSTEM' | 'MENTION';
  status: 'UNREAD' | 'READ' | 'DISMISSED';
  is_read: boolean;
  created_at: string;
  read_at?: string;
  metadata?: Record<string, any>;
  sender_id?: string;
  room_id?: string;
}

// API 相關型別
export interface LoginData {
  username: string;
  password: string;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface RoomCreate {
  name: string;
  description?: string;
  is_public?: boolean;
  room_type?: RoomType;
  join_policy?: JoinPolicy;
  max_members?: number;
  password?: string;
  invite_code?: string;
}

// 加入房間請求
export interface RoomJoinRequest {
  password?: string;
  invite_code?: string;
}

// 邀請相關類型
export enum InvitationStatus {
  PENDING = 'pending',
  ACCEPTED = 'accepted',
  REJECTED = 'rejected',
  EXPIRED = 'expired'
}

export interface RoomInvitation {
  id: string;
  room_id: string;
  room_name: string;
  invite_code: string;
  inviter_name: string;
  max_uses?: number;
  uses_count: number;
  expires_at: string;
  status: InvitationStatus;
  created_at: string;
  invite_link?: string;
}

export interface InvitationCreate {
  room_id: string;
  max_uses?: number;
  expires_in_hours?: number;
}

// 加入申請相關類型
export enum JoinRequestStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  CANCELLED = 'cancelled'
}

export interface JoinRequest {
  id: string;
  room_id: string;
  room_name: string;
  requester_id: string;
  requester_name: string;
  message?: string;
  status: JoinRequestStatus;
  reviewed_by?: string;
  reviewed_at?: string;
  review_comment?: string;
  created_at: string;
}

export interface JoinRequestCreate {
  room_id: string;
  message?: string;
}

export interface JoinRequestReview {
  status: JoinRequestStatus.APPROVED | JoinRequestStatus.REJECTED;
  comment?: string;
}

export interface MessageCreate {
  content: string;
  message_type?: 'text' | 'image';
}

// WebSocket 相關型別
export interface WebSocketMessage {
  type: 'message' | 'user_joined' | 'user_left' | 'room_users' | 'welcome' | 'message_history' | 'pong' | 'notification' | 'error' | 'notification_status_changed' | 'read_status_response' | 'room_created' | 'room_deleted' | 'room_updated';
  payload?: any;
  user?: User;  // 用於 user_joined 事件
  user_id?: string;  // 用於 user_left 事件
  message?: string;
  messages?: Message[];
  users?: User[];
  room_id?: string;
  timestamp?: string;
  // 已讀狀態相關字段
  success?: boolean;
  error?: string;
  data?: any;
}

// 狀態管理型別
export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
}

export interface RoomState {
  currentRoom: Room | null;
  rooms: Room[];
  users: User[];
  loading: boolean;
  // 權限相關狀態
  currentUserRole: MemberRole | null;
  permissions: string[];
  invitations: RoomInvitation[];
  joinRequests: JoinRequest[];
  permissionsLoading: boolean;
  // 分頁相關狀態
  hasMoreRooms: boolean;
  roomsOffset: number;
  loadingMoreRooms: boolean;
}

export interface MessageState {
  messages: Message[];
  loading: boolean;
  hasMore: boolean;
}

// API 客戶端型別
export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  body?: any;
  headers?: Record<string, string>;
}

export interface ApiError {
  detail: string;
  status_code: number;
}