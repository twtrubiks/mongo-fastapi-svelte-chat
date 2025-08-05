import { notificationSound } from '$lib/utils/notificationSound';

// 通知類型定義
export interface Notification {
  id: string;
  user_id: string;
  type: 'MESSAGE' | 'ROOM_INVITE' | 'ROOM_JOIN' | 'ROOM_LEAVE' | 'SYSTEM' | 'MENTION';
  status: 'UNREAD' | 'READ' | 'DISMISSED';
  title: string;
  message: string;
  content?: string; // 後端使用 content 欄位
  data?: Record<string, any>; // 前端期望的欄位
  metadata?: Record<string, any>; // 後端使用 metadata 欄位
  room_id?: string; // 相關房間 ID
  sender_id?: string; // 發送者 ID
  created_at: string;
  updated_at: string;
}

export interface NotificationStats {
  total: number;
  unread: number;
  by_type: Record<string, number>;
}

export interface NotificationSettings {
  email: boolean;
  push: boolean;
  sound: boolean;
  browserNotifications: boolean;
}

// 處理通知數據的規範化函數
function processNotification(n: any): Notification | null {
  if (!n || !n.id) return null;

  // 統一處理 message 和 content 欄位
  const message = n.message || n.content || '';
  
  // 統一處理 data 和 metadata 欄位
  const data = n.data || n.metadata || {};

  // 直接使用來自 BFF 層的標準化資料
  const status = n.status || 'UNREAD';
  const type = n.type || 'SYSTEM';

  return {
    id: n.id,
    user_id: n.user_id,
    type,
    status,
    title: n.title || '',
    message,
    content: n.content,
    data,
    metadata: n.metadata,
    room_id: n.room_id,
    sender_id: n.sender_id,
    created_at: n.created_at,
    updated_at: n.updated_at
  };
}

// 通知狀態管理 - 從 localStorage 讀取初始值
function getStoredStats(): NotificationStats {
  if (typeof window === 'undefined') {
    return { total: 0, unread: 0, by_type: {} };
  }
  
  try {
    const stored = localStorage.getItem('notificationStats');
    
    if (stored) {
      const parsed = JSON.parse(stored);
      
      const result = {
        total: parsed.total || parsed.total_count || 0,
        unread: parsed.unread || parsed.unread_count || 0,
        by_type: parsed.by_type || parsed.type_counts || {}
      };
      
      return result;
    }
  } catch (error) {
    console.warn('[notificationStore] 讀取本地統計資料失敗:', error);
  }
  
  return { total: 0, unread: 0, by_type: {} };
}

// 從 localStorage 讀取通知列表
function getStoredNotifications(): Notification[] {
  if (typeof window === 'undefined') {
    return [];
  }
  
  try {
    const stored = localStorage.getItem('notifications');
    
    if (stored) {
      const parsed = JSON.parse(stored);
      return parsed.map((n: any) => processNotification(n)).filter(Boolean);
    }
  } catch (error) {
    console.warn('[notificationStore] 讀取本地通知列表失敗:', error);
  }
  
  return [];
}

// 創建響應式狀態 - 延遲初始化避免 SSR 問題
let notificationList = $state<Notification[]>([]);
let notificationStatsState = $state<NotificationStats>({ total: 0, unread: 0, by_type: {} });

// 瀏覽器環境中初始化
if (typeof window !== 'undefined') {
  notificationList = getStoredNotifications();
  notificationStatsState = getStoredStats();
}
let notificationSettingsState = $state<NotificationSettings>({
  email: true,
  push: true,
  sound: true,
  browserNotifications: true
});
let browserNotificationPermissionState = $state<NotificationPermission>(
  typeof window !== 'undefined' && 'Notification' in window 
    ? Notification.permission 
    : 'default'
);
let soundEnabledState = $state(true);

// 儲存到 localStorage 的函數
function saveNotifications() {
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem('notifications', JSON.stringify(notificationList));
    } catch (error) {
      console.warn('[notificationStore] 儲存通知列表失敗:', error);
    }
  }
}

function saveStats() {
  if (typeof window !== 'undefined') {
    try {
      localStorage.setItem('notificationStats', JSON.stringify(notificationStatsState));
    } catch (error) {
      console.warn('[notificationStore] 儲存統計資料失敗:', error);
    }
  }
}

// 導出響應式狀態和派生值 - Svelte 5 函數格式
// 直接返回 notificationList 以確保響應式追蹤
export const notifications = () => notificationList;

export const notificationStats = {
  get value() {
    return notificationStatsState;
  }
};

export const notificationSettings = {
  get value() {
    return notificationSettingsState;
  }
};

// 派生值 - getter 函數形式支援 SSR
export const unreadCount = () => 
  notificationList.filter(n => n.status === 'UNREAD').length;

export const hasUnreadNotifications = () => unreadCount() > 0;

export const unreadNotifications = () =>
  notificationList.filter(n => n.status === 'UNREAD');

// 通知管理 Store
export const notificationStore = {
  // 獲取狀態
  get notifications() {
    return notificationList;
  },

  get stats() {
    return notificationStatsState;
  },

  get settings() {
    return notificationSettingsState;
  },

  // 添加通知
  addNotification: (notification: Notification) => {
    const processed = processNotification(notification);
    if (processed) {
      // 避免重複添加
      if (!notificationList.some(n => n.id === processed.id)) {
        notificationList = [processed, ...notificationList];
        saveNotifications();
        
        // 更新統計
        notificationStatsState = {
          ...notificationStatsState,
          total: notificationStatsState.total + 1,
          unread: processed.status === 'UNREAD' ? notificationStatsState.unread + 1 : notificationStatsState.unread
        };
        saveStats();
      }
    }
  },

  // 批量設置通知
  setNotifications: (notifications: Notification[]) => {
    const processed = notifications.map(n => processNotification(n)).filter((n): n is Notification => n !== null);
    notificationList = processed;
    saveNotifications();
  },

  // 標記為已讀
  markAsRead: async (notificationId: string) => {
    const index = notificationList.findIndex(n => n.id === notificationId);
    if (index !== -1 && notificationList[index] && notificationList[index].status === 'UNREAD') {
      // 在 Svelte 5 中，需要創建全新的數組來觸發響應式更新
      const updatedList = [...notificationList];
      updatedList[index] = {
        ...notificationList[index],
        status: 'READ' as const,
        updated_at: new Date().toISOString()
      };
      
      // 重新賦值整個數組
      notificationList = updatedList;
      saveNotifications();
      
      // 更新統計 - 創建全新的對象
      notificationStatsState = {
        total: notificationStatsState.total,
        unread: Math.max(0, notificationStatsState.unread - 1),
        by_type: { ...notificationStatsState.by_type }
      };
      saveStats();
      
      // console.log('[notificationStore] 已標記通知為已讀:', notificationId, '剩餘未讀:', notificationStatsState.unread);
    }
  },

  // 標記全部為已讀
  markAllAsRead: async () => {
    let changed = false;
    notificationList = notificationList.map(n => {
      if (n.status === 'UNREAD') {
        changed = true;
        return { ...n, status: 'READ' as const };
      }
      return n;
    });
    
    if (changed) {
      saveNotifications();
      notificationStatsState = {
        ...notificationStatsState,
        unread: 0
      };
      saveStats();
    }
  },

  // 刪除通知
  removeNotification: (notificationId: string) => {
    const notification = notificationList.find(n => n.id === notificationId);
    if (notification) {
      notificationList = notificationList.filter(n => n.id !== notificationId);
      saveNotifications();
      
      // 更新統計
      notificationStatsState = {
        ...notificationStatsState,
        total: Math.max(0, notificationStatsState.total - 1),
        unread: notification.status === 'UNREAD' 
          ? Math.max(0, notificationStatsState.unread - 1) 
          : notificationStatsState.unread
      };
      saveStats();
    }
  },

  // 更新統計
  updateStats: (stats: NotificationStats) => {
    notificationStatsState = { ...stats };
    saveStats();
  },

  // 更新設置
  updateSettings: (settings: Partial<NotificationSettings>) => {
    notificationSettingsState = { ...notificationSettingsState, ...settings };
  },

  // 清除所有通知
  clearAll: () => {
    notificationList = [];
    notificationStatsState = { total: 0, unread: 0, by_type: {} };
    saveNotifications();
    saveStats();
  }
};

// 瀏覽器通知權限管理
export const browserNotificationPermission = {
  get value() {
    return browserNotificationPermissionState;
  }
};

export const soundEnabled = {
  get value() {
    return soundEnabledState;
  },
  set value(enabled: boolean) {
    soundEnabledState = enabled;
  }
};

// 瀏覽器通知管理器
export const browserNotificationManager = {
  async requestPermission(): Promise<NotificationPermission> {
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      browserNotificationPermissionState = permission;
      return permission;
    }
    return 'denied';
  },

  showNotification(title: string, options?: NotificationOptions): boolean {
    if ('Notification' in window && Notification.permission === 'granted') {
      try {
        new Notification(title, options);
        return true;
      } catch (error) {
        console.warn('Failed to show notification:', error);
      }
    }
    return false;
  }
};

// 音效通知管理器
export const soundNotificationManager = {
  playNotificationSound() {
    if (soundEnabledState) {
      notificationSound.playNotificationSound();
    }
  },
  
  setEnabled(enabled: boolean) {
    soundEnabledState = enabled;
  }
};

// WebSocket 連接由 wsManager 統一管理，不需要額外的初始化函數

// 為了向後兼容，提供一些別名
export { unreadCount as unreadCountDerived };
export { hasUnreadNotifications as hasUnread };
export { unreadNotifications as unreadList };