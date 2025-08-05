import { getContext, setContext } from 'svelte';
import { writable, type Writable } from 'svelte/store';
import type { Room, User, Message } from '../types';

export interface RoomContextState {
  currentRoom: Room | null;
  users: User[];
  isConnected: boolean;
  loading: boolean;
}

export interface RoomContext {
  // 狀態 stores
  state: Writable<RoomContextState>;
  
  // 操作方法
  setRoom: (room: Room | null) => void;
  setUsers: (users: User[]) => void;
  addUser: (user: User) => void;
  removeUser: (userId: string) => void;
  setConnected: (connected: boolean) => void;
  setLoading: (loading: boolean) => void;
  
  // 事件處理
  sendMessage: (content: string, type?: string) => Promise<void>;
  uploadImage: (file: File) => Promise<void>;
  leaveRoom: () => Promise<void>;
}

const ROOM_CONTEXT_KEY = 'room-context';

export function createRoomContext(): RoomContext {
  const initialState: RoomContextState = {
    currentRoom: null,
    users: [],
    isConnected: false,
    loading: false,
  };

  const state = writable(initialState);

  const context: RoomContext = {
    state,
    
    setRoom: (room: Room | null) => {
      state.update(s => ({ ...s, currentRoom: room }));
    },
    
    setUsers: (users: User[]) => {
      state.update(s => ({ ...s, users }));
    },
    
    addUser: (user: User) => {
      state.update(s => ({
        ...s,
        users: s.users.some(u => u.id === user.id) 
          ? s.users 
          : [...s.users, user]
      }));
    },
    
    removeUser: (userId: string) => {
      state.update(s => ({
        ...s,
        users: s.users.filter(u => u.id !== userId)
      }));
    },
    
    setConnected: (connected: boolean) => {
      state.update(s => ({ ...s, isConnected: connected }));
    },
    
    setLoading: (loading: boolean) => {
      state.update(s => ({ ...s, loading }));
    },
    
    // 這些方法將由使用組件實現
    sendMessage: async () => {
      throw new Error('sendMessage method not implemented');
    },
    
    uploadImage: async () => {
      throw new Error('uploadImage method not implemented');
    },
    
    leaveRoom: async () => {
      throw new Error('leaveRoom method not implemented');
    },
  };

  return context;
}

export function setRoomContext(context: RoomContext): void {
  setContext(ROOM_CONTEXT_KEY, context);
}

export function getRoomContext(): RoomContext {
  const context = getContext<RoomContext>(ROOM_CONTEXT_KEY);
  if (!context) {
    throw new Error('Room context not found. Make sure to call setRoomContext() in a parent component.');
  }
  return context;
}

// 便利函數：獲取狀態 store
export function getRoomState() {
  return getRoomContext().state;
}