import { browser } from '$app/environment';
import { apiClient } from '../api/client';
import { wsManager } from '../websocket/manager';
import { messageRetryManager } from '../utils/messageRetry';
import type { AuthState, User, LoginData, RegisterData } from '../types';

const initialState: AuthState = {
  user: null,
  loading: false,
};

// 創建響應式狀態
let authState = $state<AuthState>(initialState);

// 從 localStorage 恢復使用者資訊（不含 token）
function restoreFromStorage(): boolean {
  if (browser) {
    const userStr = localStorage.getItem('auth_user');

    if (userStr) {
      try {
        const user = JSON.parse(userStr);
        authState = { user, loading: false };
        return true;
      } catch {
        clearStorage();
      }
    }
  }
  return false;
}

// 清除本地存儲
function clearStorage() {
  if (browser) {
    localStorage.removeItem('auth_user');
  }
}

// 儲存使用者資訊到 localStorage（不含 token）
function saveToStorage(user: User) {
  if (browser) {
    localStorage.setItem('auth_user', JSON.stringify(user));
  }
}

// 導出的 authStore 對象
export const authStore = {
  get state() {
    return authState;
  },

  get user() {
    return authState.user;
  },

  get isAuthenticated() {
    return authState.user !== null;
  },

  get loading() {
    return authState.loading;
  },

  // 初始化 store
  init: () => {
    const restored = restoreFromStorage();

    // 認證失敗時的回調（BFF 透明 refresh 也失敗）
    apiClient.onAuthFailure = () => {
      authStore.logout();
    };

    return restored;
  },

  // 登入（BFF 回傳 { user }，token 在 httpOnly cookie 中）
  login: async (credentials: LoginData) => {
    authState = { ...authState, loading: true };

    try {
      const response = await apiClient.auth.login(credentials);

      authState = { user: response.user, loading: false };

      saveToStorage(response.user);
      return response;
    } catch (error) {
      authState = { ...authState, loading: false };
      throw error;
    }
  },

  // 註冊
  register: async (userData: RegisterData) => {
    authState = { ...authState, loading: true };

    try {
      const response = await apiClient.auth.register(userData);

      authState = { user: response.user, loading: false };

      saveToStorage(response.user);
      return response;
    } catch (error) {
      authState = { ...authState, loading: false };
      throw error;
    }
  },

  // 驗證當前登入狀態
  verify: async () => {
    if (!browser) return;

    authState = { ...authState, loading: true };

    try {
      const user = await apiClient.auth.verify();

      authState = { user, loading: false };

      saveToStorage(user);
      return user;
    } catch (error) {
      clearStorage();
      authState = initialState;
      throw error;
    }
  },

  // 登出
  logout: async () => {
    try {
      await apiClient.auth.logout();
    } catch {
      // 即使失敗也繼續登出流程
    }

    wsManager.destroy();
    messageRetryManager.clearAll();
    clearStorage();
    authState = initialState;
  },

  // 更新用戶資料
  updateUser: (user: User) => {
    if (authState.user) {
      authState = { ...authState, user };
      saveToStorage(user);
    }
  },

  // 直接設置認證狀態（用於服務端數據同步）
  setAuthState: (newAuthState: Partial<AuthState> & { user: User }) => {
    if (newAuthState.user) {
      saveToStorage(newAuthState.user);
    }
    authState = {
      user: newAuthState.user,
      loading: newAuthState.loading ?? false,
    };
  },
};

// 派生值
export const isAuthenticated = () => authState.user !== null;
export const currentUser = () => authState.user;
