import { browser } from '$app/environment';

export interface NetworkState {
  isOnline: boolean;
  isSlowConnection: boolean;
  lastOnlineTime: number;
  lastOfflineTime: number;
  connectionType: string;
  effectiveType: string;
  rtt: number; // Round-trip time
  downlink: number; // Effective bandwidth estimate
}

// 創建響應式狀態
let networkState = $state<NetworkState>({
  isOnline: browser ? navigator.onLine : true,
  isSlowConnection: false,
  lastOnlineTime: Date.now(),
  lastOfflineTime: 0,
  connectionType: 'unknown',
  effectiveType: 'unknown',
  rtt: 0,
  downlink: 0
});

let checkInterval: number | null = null;

// 檢查網路連接類型和速度
function updateConnectionInfo() {
  if (!browser) return;

  // 檢查 Network Information API
  if ('connection' in navigator) {
    const connection = (navigator as any).connection;
    if (connection) {
      networkState = {
        ...networkState,
        connectionType: connection.type || 'unknown',
        effectiveType: connection.effectiveType || 'unknown',
        rtt: connection.rtt || 0,
        downlink: connection.downlink || 0,
        // 判斷是否為慢速連接
        isSlowConnection: 
          connection.effectiveType === 'slow-2g' || 
          connection.effectiveType === '2g' ||
          (connection.rtt && connection.rtt > 1000) ||
          (connection.downlink && connection.downlink < 0.5)
      };
    }
  }
}

// 處理在線狀態變化
function handleOnline() {
  const now = Date.now();
  networkState = {
    ...networkState,
    isOnline: true,
    lastOnlineTime: now
  };
  updateConnectionInfo();
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

// 處理連接信息變化
function handleConnectionChange() {
  updateConnectionInfo();
}

// 初始化
function init() {
  if (!browser) return;

  // 更新初始連接信息
  updateConnectionInfo();

  // 添加事件監聽器
  window.addEventListener('online', handleOnline);
  window.addEventListener('offline', handleOffline);

  // 監聽網路連接變化
  if ('connection' in navigator) {
    const connection = (navigator as any).connection;
    if (connection) {
      connection.addEventListener('change', handleConnectionChange);
    }
  }

  // 定期檢查連接狀態
  checkInterval = window.setInterval(() => {
    networkState = {
      ...networkState,
      isOnline: navigator.onLine
    };
    updateConnectionInfo();
  }, 30000); // 每30秒檢查一次
}

// 清理
function destroy() {
  if (!browser) return;

  window.removeEventListener('online', handleOnline);
  window.removeEventListener('offline', handleOffline);

  if ('connection' in navigator) {
    const connection = (navigator as any).connection;
    if (connection) {
      connection.removeEventListener('change', handleConnectionChange);
    }
  }

  if (checkInterval) {
    clearInterval(checkInterval);
    checkInterval = null;
  }
}

// 測試網路延遲
async function pingTest(url = '/api/ping'): Promise<number> {
  if (!browser) return 0;

  try {
    const start = performance.now();
    const response = await fetch(url, {
      method: 'HEAD',
      cache: 'no-cache'
    });
    const end = performance.now();
    
    if (response.ok) {
      return Math.round(end - start);
    }
    return 0;
  } catch (error) {
    console.error('Ping test failed:', error);
    return 0;
  }
}

// 測試下載速度
async function speedTest(url = '/api/speedtest', sizeKB = 100): Promise<number> {
  if (!browser) return 0;

  try {
    const start = performance.now();
    const response = await fetch(`${url}?size=${sizeKB}`);
    const data = await response.arrayBuffer();
    const end = performance.now();
    
    const durationSeconds = (end - start) / 1000;
    const sizeBytes = data.byteLength;
    const speedMbps = (sizeBytes * 8) / (1024 * 1024 * durationSeconds);
    
    return Math.round(speedMbps * 100) / 100;
  } catch (error) {
    console.error('Speed test failed:', error);
    return 0;
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

  get isSlowConnection() {
    return networkState.isSlowConnection;
  },

  get connectionType() {
    return networkState.connectionType;
  },

  get effectiveType() {
    return networkState.effectiveType;
  },

  init,
  destroy,
  pingTest,
  speedTest,
  updateConnectionInfo,
  
  // 獲取連接質量描述
  getConnectionQuality: () => {
    if (!networkState.isOnline) {
      return 'offline';
    } else if (networkState.isSlowConnection) {
      return 'poor';
    } else if (networkState.effectiveType === '4g' || networkState.downlink > 5) {
      return 'excellent';
    } else if (networkState.effectiveType === '3g' || networkState.downlink > 1) {
      return 'good';
    } else {
      return 'fair';
    }
  },

  // 檢查是否適合進行大量數據操作
  isGoodForHeavyOperations: () => {
    return networkState.isOnline && 
           !networkState.isSlowConnection && 
           (networkState.downlink > 1 || networkState.effectiveType === '3g' || networkState.effectiveType === '4g');
  }
};

// 派生值 - 轉換為 getter 函數以支援 SSR
export const isOnline = () => networkState.isOnline;
export const isSlowConnection = () => networkState.isSlowConnection;
export const connectionQuality = () => networkStore.getConnectionQuality();

// 延遲初始化，避免 SSR 問題
// 初始化會在首次使用時或組件中手動調用