export interface ErrorInfo {
  id: string;
  title: string;
  message: string;
  type: 'error' | 'warning' | 'info';
  timestamp: number;
  action?: {
    label: string;
    handler: () => void;
  };
  autoHide?: boolean;
  duration?: number;
}

export interface ErrorState {
  errors: ErrorInfo[];
  currentError: ErrorInfo | null;
}

// 創建響應式狀態
let errorState = $state<ErrorState>({
  errors: [],
  currentError: null
});

export const errorStore = {
  // 暴露狀態的 getter
  get state() {
    return errorState;
  },

  get errors() {
    return errorState.errors;
  },

  get currentError() {
    return errorState.currentError;
  },

  // 添加錯誤
  addError(error: Omit<ErrorInfo, 'id' | 'timestamp'>) {
    const errorInfo: ErrorInfo = {
      ...error,
      id: `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
      autoHide: error.autoHide !== false, // 預設為 true
      duration: error.duration || 5000
    };

    errorState = {
      ...errorState,
      errors: [...errorState.errors, errorInfo],
      currentError: errorState.currentError || errorInfo
    };

    return errorInfo.id;
  },

  // 移除錯誤
  removeError(errorId: string) {
    const newErrors = errorState.errors.filter(e => e.id !== errorId);
    const newCurrentError = errorState.currentError?.id === errorId 
      ? newErrors[0] || null 
      : errorState.currentError;
    
    errorState = {
      errors: newErrors,
      currentError: newCurrentError
    };
  },

  // 清除當前錯誤
  clearCurrentError() {
    errorState = {
      ...errorState,
      currentError: null
    };
  },

  // 清除所有錯誤
  clearAllErrors() {
    errorState = {
      errors: [],
      currentError: null
    };
  },

  // 顯示下一個錯誤
  showNextError() {
    const currentIndex = errorState.currentError 
      ? errorState.errors.findIndex(e => e.id === errorState.currentError!.id)
      : -1;
    
    const nextIndex = currentIndex + 1;
    const nextError = nextIndex < errorState.errors.length 
      ? errorState.errors[nextIndex] 
      : null;
    
    errorState = {
      ...errorState,
      currentError: nextError
    };
  },

  // 特定類型的錯誤快捷方法
  showError(message: string, title = '錯誤', action?: ErrorInfo['action']) {
    return this.addError({
      title,
      message,
      type: 'error',
      action
    });
  },

  showWarning(message: string, title = '警告', action?: ErrorInfo['action']) {
    return this.addError({
      title,
      message,
      type: 'warning',
      action
    });
  },

  showInfo(message: string, title = '訊息', action?: ErrorInfo['action']) {
    return this.addError({
      title,
      message,
      type: 'info',
      action
    });
  },

  // WebSocket 相關錯誤
  showConnectionError(action?: ErrorInfo['action']) {
    return this.addError({
      title: '連接錯誤',
      message: '與服務器的連接已斷開，正在嘗試重新連接...',
      type: 'error',
      autoHide: false,
      action
    });
  },

  showReconnectFailed(attempts: number, action?: ErrorInfo['action']) {
    return this.addError({
      title: '重連失敗',
      message: `嘗試重連 ${attempts} 次後失敗，請檢查網路連接或手動重試。`,
      type: 'error',
      autoHide: false,
      action
    });
  },

  showMessageSendError(messageId: string, action?: ErrorInfo['action']) {
    return this.addError({
      title: '訊息發送失敗',
      message: '訊息發送失敗，請檢查網路連接並重試。',
      type: 'error',
      action
    });
  },

  // 驗證錯誤
  showValidationError(field: string, message: string) {
    return this.addError({
      title: '輸入錯誤',
      message: `${field}: ${message}`,
      type: 'warning'
    });
  },

  // 權限錯誤
  showPermissionError(action: string) {
    return this.addError({
      title: '權限不足',
      message: `您沒有權限執行此操作：${action}`,
      type: 'error'
    });
  },

  // 網路錯誤
  showNetworkError(action?: ErrorInfo['action']) {
    return this.addError({
      title: '網路錯誤',
      message: '網路連接不穩定，請檢查您的網路設定。',
      type: 'error',
      action
    });
  }
};

// 派生值 - 轉換為 getter 函數以支援 SSR
export const currentErrors = () => errorState.errors;
export const hasErrors = () => errorState.errors.length > 0;