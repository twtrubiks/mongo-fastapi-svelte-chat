import { browser } from '$app/environment';
import { apiClient } from '../api/client';
import type { AuthState, User, LoginData, RegisterData } from '../types';

// 初始狀態
const initialState: AuthState = {
  user: null,
  token: null,
  isAuthenticated: false,
  loading: false,
};

// 創建響應式狀態
let authState = $state<AuthState>(initialState);

// 從 localStorage 恢復狀態
function restoreFromStorage(): boolean {
  if (browser) {
    const token = localStorage.getItem('auth_token');
    const userStr = localStorage.getItem('auth_user');
    
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr);
        apiClient.setToken(token);
        authState = {
          user,
          token,
          isAuthenticated: true,
          loading: false,
        };
        return true; // 成功恢復
      } catch (error) {
        clearStorage();
      }
    }
  }
  return false; // 未恢復或失敗
}

// 清除本地存儲和 cookie
function clearStorage() {
  if (browser) {
    // 清除 localStorage
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('refresh_token');
    
    // 清除 sessionStorage
    sessionStorage.clear();
    
    // 清除 cookie - 使用多種方式確保清除
    document.cookie = 'auth_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT; samesite=strict';
    document.cookie = 'auth_token=; path=/; expires=Thu, 01 Jan 1970 00:00:01 GMT';
    document.cookie = 'auth_token=; path=/; max-age=0';
    
    // 清除其他可能的 cookies
    document.cookie = 'refresh_token=; path=/; max-age=0';
    document.cookie = 'session_id=; path=/; max-age=0';
  }
}

// 儲存到本地存儲和 cookie
function saveToStorage(token: string, user: User) {
  if (browser) {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', JSON.stringify(user));
    
    // 同時設置 cookie 用於伺服器端檢查
    document.cookie = `auth_token=${token}; path=/; max-age=${7 * 24 * 60 * 60}; samesite=lax; secure=${window.location.protocol === 'https:'}`;
  }
}

// 導出的 authStore 對象
export const authStore = {
  // 暴露狀態的 getter
  get state() {
    return authState;
  },
  
  // 暴露特定屬性的 getter（為了向後兼容）
  get user() {
    return authState.user;
  },
  
  get token() {
    return authState.token;
  },
  
  get isAuthenticated() {
    return authState.isAuthenticated;
  },
  
  get loading() {
    return authState.loading;
  },
  
  // 初始化 store
  init: () => {
    return restoreFromStorage();
  },

  // 登入
  login: async (credentials: LoginData) => {
    authState = { ...authState, loading: true };
    
    try {
      const response = await apiClient.auth.login(credentials);
      
      authState = {
        user: response.user,
        token: response.access_token,
        isAuthenticated: true,
        loading: false,
      };
      
      saveToStorage(response.access_token, response.user);
      
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
      
      authState = {
        user: response.user,
        token: response.access_token,
        isAuthenticated: true,
        loading: false,
      };
      
      saveToStorage(response.access_token, response.user);
      
      return response;
    } catch (error) {
      authState = { ...authState, loading: false };
      throw error;
    }
  },

  // 驗證 token
  verify: async () => {
    if (!browser) return;
    
    const token = localStorage.getItem('auth_token');
    if (!token) return;

    authState = { ...authState, loading: true };
    
    try {
      const user = await apiClient.auth.verify(token);
      
      authState = {
        user,
        token,
        isAuthenticated: true,
        loading: false,
      };
      
      saveToStorage(token, user);
      
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
      // 1. 調用後端登出 API
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      
      if (!response.ok) {
        // 後端登出失敗，但仍繼續前端登出
      }
    } catch (error) {
      // 即使失敗也繼續登出流程
    }
    
    // 2. 清除本地存儲
    clearStorage();
    
    // 3. 清除 API 客戶端 token
    apiClient.setToken(null);
    
    // 4. 重置 Store 狀態
    authState = initialState;
  },

  // 更新用戶資料
  updateUser: (user: User) => {
    if (authState.isAuthenticated) {
      authState = { ...authState, user };
      saveToStorage(authState.token!, user);
    }
  },

  // 直接設置認證狀態（用於服務端數據同步）
  setAuthState: (newAuthState: AuthState) => {
    if (newAuthState.token && newAuthState.user) {
      saveToStorage(newAuthState.token, newAuthState.user);
      apiClient.setToken(newAuthState.token);
    }
    authState = newAuthState;
  },

  // 清除錯誤狀態
  clearError: () => {
    authState = { ...authState, loading: false };
  },
};

// 派生值 - 使用 getter 函數以實現響應性
export const isAuthenticated = () => authState.isAuthenticated;
export const currentUser = () => authState.user;
export const authLoading = () => authState.loading;