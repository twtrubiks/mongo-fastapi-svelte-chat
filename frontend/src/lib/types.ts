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
  PRIVATE = 'private',      // 私人房間 - 僅邀請加入
}

export enum JoinPolicy {
  DIRECT = 'direct',       // 直接加入
  INVITE = 'invite',       // 邀請鏈接
  PASSWORD = 'password'    // 密碼加入
}

export enum MemberRole {
  OWNER = 'owner',     // 房主 - 完全控制權
  ADMIN = 'admin',     // 管理員 - 成員管理權
  MEMBER = 'member'    // 成員 - 基本使用權
}

// 列表 / 非成員用的精簡房間資訊
export interface RoomSummary {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  owner_name?: string;
  member_count: number;
  is_member: boolean;
  is_public: boolean;
  room_type?: RoomType;
  join_policy?: JoinPolicy;
  has_password?: boolean;
  max_members?: number;
  created_at: string;
  updated_at?: string;
}

// 成員詳情用的完整房間資訊
export interface Room extends RoomSummary {
  members: string[];
  member_roles?: Record<string, MemberRole>;
  invite_code?: string;
}

export interface Message {
  id: string;
  room_id: string;
  user_id: string;
  username?: string;  // 直接包含用戶名，利用 MongoDB 反規範化優勢
  avatar?: string;
  content: string;
  type?: 'TEXT' | 'IMAGE' | 'SYSTEM';  // 新的類型字段
  message_type?: 'text' | 'image' | 'system' | 'file';  // 保持向後兼容
  created_at: string;
  updated_at: string;
  user?: {
    id: string;
    username: string;
    full_name?: string;
    avatar?: string;
    created_at?: string;
  };
  metadata?: Record<string, any>;
}

export interface Notification {
  id: string;
  user_id: string;
  type: 'MESSAGE' | 'SYSTEM';
  status: 'UNREAD' | 'READ';
  title: string;
  message: string;
  content?: string;
  data?: Record<string, any>;
  metadata?: Record<string, any>;
  room_id?: string;
  sender_id?: string;
  created_at: string;
  updated_at: string;
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

export interface MessageCreate {
  content: string;
  message_type?: 'text' | 'image' | 'file';
}

// WebSocket 相關型別
export interface WebSocketMessage {
  type: 'message' | 'user_joined' | 'user_left' | 'room_users' | 'user_status_changed' | 'welcome' | 'message_history' | 'pong' | 'notification' | 'error' | 'notification_status_changed' | 'read_status_response' | 'room_created' | 'room_deleted' | 'room_updated' | 'typing';
  payload?: any;
  user?: User;  // 用於 user_joined 事件
  user_id?: string;  // 用於 user_left 事件
  message?: string;
  messages?: Message[];
  users?: User[];
  room_id?: string;
  timestamp?: string;
  is_typing?: boolean;
  // 已讀狀態相關字段
  success?: boolean;
  error?: string;
  data?: any;
}

// 狀態管理型別
export interface AuthState {
  user: User | null;
  loading: boolean;
}

export interface RoomState {
  currentRoom: Room | null;
  rooms: RoomSummary[];
  myRooms: RoomSummary[];
  activeTab: 'joined' | 'explore';
  searchQuery: string;
  users: User[];
  loading: boolean;
  // 探索聊天室分頁狀態
  hasMoreRooms: boolean;
  roomsOffset: number;
  loadingMoreRooms: boolean;
  // 已加入聊天室分頁狀態
  hasMoreMyRooms: boolean;
  myRoomsOffset: number;
  loadingMoreMyRooms: boolean;
  // 成員分頁狀態
  hasMoreMembers: boolean;
  membersOffset: number;
  loadingMoreMembers: boolean;
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

