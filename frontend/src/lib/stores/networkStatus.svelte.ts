import { browser } from '$app/environment';

export interface NetworkState {
  isOnline: boolean;
  lastOnlineTime: number;
  lastOfflineTime: number;
}

// 創建響應式狀態
let networkState = $state<NetworkState>({
  isOnline: browser ? navigator.onLine : true,
  lastOnlineTime: Date.now(),
  lastOfflineTime: 0,
});

let checkInterval: number | null = null;

// 處理在線狀態變化
function handleOnline() {
  const now = Date.now();
  networkState = {
    ...networkState,
    isOnline: true,
    lastOnlineTime: now
  };
}

// 處理離線狀態變化
function handleOffline() {
  const now = Date.now();
  networkState = {
    ...networkState,
    isOnline: false,
    lastOfflineTime: now
  };
}

// 初始化
function init() {
  if (!browser) return;

  // 添加事件監聽器
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);

  // 定期檢查連接狀態（僅在狀態變化時更新，避免無效的響應式觸發）
  checkInterval = window.setInterval(() => {
    const currentOnline = navigator.onLine;
    if (currentOnline !== networkState.isOnline) {
      networkState = {
        ...networkState,
        isOnline: currentOnline
      };
    }
  }, 30000);
}

// 清理
function destroy() {
  if (!browser) return;

  window.removeEventListener('online', handleOnline);
  window.removeEventListener('offline', handleOffline);

  if (checkInterval) {
    clearInterval(checkInterval);
    checkInterval = null;
  }
}

export const networkStore = {
  // 暴露狀態的 getter
  get state() {
    return networkState;
  },

  get isOnline() {
    return networkState.isOnline;
  },

  init,
  destroy,
};

// 延遲初始化，避免 SSR 問題
// 初始化會在首次使用時或組件中手動調用
