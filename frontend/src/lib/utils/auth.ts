import { redirect } from '@sveltejs/kit';
import { authStore } from '../stores/auth.svelte';

// 檢查用戶是否已認證
export function requireAuth() {
  const authState = authStore.state;
  
  if (!authState.isAuthenticated) {
    throw redirect(302, '/login');
  }
  
  return authState;
}

// 檢查用戶是否未認證 (已登入則重定向)
export function requireGuest() {
  const authState = authStore.state;
  
  if (authState.isAuthenticated) {
    throw redirect(302, '/');
  }
  
  return authState;
}

// 初始化認證狀態 (from localStorage)
export async function initAuth() {
  try {
    await authStore.verify();
  } catch (error) {
    // 驗證失敗，清除無效的認證狀態
    authStore.logout();
  }
}

// 格式化錯誤訊息
export function formatAuthError(error: any): string {
  if (error?.detail) {
    return error.detail;
  }
  
  if (error?.message) {
    return error.message;
  }
  
  return '認證失敗，請稍後再試';
}

// 檢查密碼強度
export function validatePassword(password: string): {
  isValid: boolean;
  errors: string[];
} {
  const errors: string[] = [];
  
  if (password.length < 8) {
    errors.push('密碼至少需要 8 個字符');
  }
  
  if (!/[A-Z]/.test(password)) {
    errors.push('密碼需要包含至少一個大寫字母');
  }
  
  if (!/[a-z]/.test(password)) {
    errors.push('密碼需要包含至少一個小寫字母');
  }
  
  if (!/[0-9]/.test(password)) {
    errors.push('密碼需要包含至少一個數字');
  }
  
  return {
    isValid: errors.length === 0,
    errors,
  };
}

// 驗證電子郵件格式
export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

// 驗證用戶名格式
export function validateUsername(username: string): {
  isValid: boolean;
  errors: string[];
} {
  const errors: string[] = [];
  
  if (username.length < 3) {
    errors.push('用戶名至少需要 3 個字符');
  }
  
  if (username.length > 20) {
    errors.push('用戶名最多 20 個字符');
  }
  
  if (!/^[a-zA-Z0-9_]+$/.test(username)) {
    errors.push('用戶名只能包含字母、數字和下劃線');
  }
  
  return {
    isValid: errors.length === 0,
    errors,
  };
}