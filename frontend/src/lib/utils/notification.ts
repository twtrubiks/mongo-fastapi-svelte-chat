import { notificationStore } from '$lib/stores/notification.svelte';

/**
 * 獲取認證 headers
 */
function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('auth_token');
  
  // 檢查 token 是否為字符串 "undefined"
  if (token && token !== 'undefined' && token !== 'null') {
    return {
      'Authorization': `Bearer ${token}`
    };
  }
  
  return {};
}

/**
 * 初始化通知系統
 */
export async function initializeNotificationSystem() {
  try {
    const authHeaders = getAuthHeaders();
    
    // 載入通知統計
    const statsResponse = await fetch('/api/notifications/stats', {
      credentials: 'include',
      headers: authHeaders
    });

    if (statsResponse.ok) {
      const stats = await statsResponse.json();
      notificationStore.updateStats(stats);
    } else if (statsResponse.status === 429) {
      // 稍後重試
      setTimeout(() => {
        fetch('/api/notifications/stats', {
          credentials: 'include',
          headers: getAuthHeaders()
        }).then(res => res.json()).then(stats => {
          notificationStore.updateStats(stats);
        }).catch(() => {});
      }, 5000);
    }

    // 添加小延遲以避免速率限制
    await new Promise(resolve => setTimeout(resolve, 100));

    // 載入最近的未讀通知
    const unreadResponse = await fetch('/api/notifications/unread?limit=10', {
      credentials: 'include',
      headers: getAuthHeaders()
    });

    if (unreadResponse.ok) {
      const data = await unreadResponse.json();
      notificationStore.setNotifications(data.notifications || []);
    }

  } catch (error) {
  }
}

/**
 * 定期更新通知統計
 */
export function startNotificationPolling(intervalMs = 30000) {
  const interval = setInterval(async () => {
    try {
      const response = await fetch('/api/notifications/stats', {
        credentials: 'include',
        headers: getAuthHeaders()
      });

      if (response.ok) {
        const stats = await response.json();
        notificationStore.updateStats(stats);
      }
    } catch (error) {
    }
  }, intervalMs);

  return () => clearInterval(interval);
}