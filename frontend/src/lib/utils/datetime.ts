// 日期時間工具函數

/**
 * 正規化時間字符串，確保包含時區標識
 * 這是一個防禦性修復，處理可能缺少時區標識的時間字符串
 */
function normalizeTimeString(dateStr: string): string {
  if (!dateStr) return dateStr;
  
  // 如果已經有時區標識，直接返回
  if (dateStr.includes('+') || dateStr.includes('-') || dateStr.endsWith('Z')) {
    return dateStr;
  }
  
  // 沒有時區標識，假設為 UTC 時間，添加 Z 後綴
  const normalizedStr = dateStr + 'Z';
  console.warn(`[datetime] 自動修復缺少時區標識的時間: ${dateStr} -> ${normalizedStr}`);
  return normalizedStr;
}

// 格式化日期時間 - 確保使用本地時間
export function formatDateTime(dateStr: string): string {
  const date = new Date(normalizeTimeString(dateStr));
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  
  // 小於 1 分鐘
  if (diff < 60 * 1000) {
    return '剛剛';
  }
  
  // 小於 1 小時
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000));
    return `${minutes} 分鐘前`;
  }
  
  // 小於 1 天
  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000));
    return `${hours} 小時前`;
  }
  
  // 小於 7 天
  if (diff < 7 * 24 * 60 * 60 * 1000) {
    const days = Math.floor(diff / (24 * 60 * 60 * 1000));
    return `${days} 天前`;
  }
  
  // 超過 7 天，顯示具體日期
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  
  // 如果是今年，不顯示年份
  if (year === now.getFullYear()) {
    return `${month}-${day}`;
  }
  
  return `${year}-${month}-${day}`;
}

// 格式化時間 (只顯示時間) - 確保轉換為本地時間
export function formatTime(dateStr: string): string {
  const normalizedStr = normalizeTimeString(dateStr);
  const date = new Date(normalizedStr);
  
  // 使用 toLocaleTimeString 確保正確的本地時間格式化
  const timeStr = date.toLocaleTimeString('zh-TW', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
  
  return timeStr;
}

// 按日期分組訊息
export function groupMessagesByDate<T extends { created_at: string }>(
  messages: T[]
): Array<{ date: string; messages: T[] }> {
  const groups: Record<string, T[]> = {};
  
  messages.forEach(message => {
    // 確保 created_at 存在
    if (!message.created_at) {
      console.warn('[groupMessagesByDate] 訊息缺少 created_at 欄位:', message);
      return; // 跳過這個訊息
    }
    
    const date = message.created_at.split('T')[0]!; // 取日期部分
    if (!groups[date]) {
      groups[date] = [];
    }
    groups[date]!.push(message);
  });
  
  return Object.keys(groups)
    .sort() // 按日期排序（最舊的日期在前）
    .map(date => ({
      date,
      messages: groups[date]!.sort((a, b) => {
        // 同一天內按時間排序（最舊的在前，最新的在後）
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }),
    }));
}