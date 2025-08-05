/**
 * 時區處理工具類
 * 提供更可靠的時間解析和格式化方法
 */

/**
 * 智能解析時間字符串，自動處理時區問題
 */
export function parseDateTime(dateStr: string | Date): Date {
  if (dateStr instanceof Date) {
    return dateStr;
  }
  
  if (!dateStr) {
    throw new Error('Invalid date string provided');
  }
  
  // 如果已經有時區標識，直接解析
  if (dateStr.includes('+') || dateStr.includes('-') || dateStr.endsWith('Z')) {
    return new Date(dateStr);
  }
  
  // 沒有時區標識，假設為 UTC 時間
  console.warn(`[timezone] 時間字符串缺少時區標識，假設為 UTC: ${dateStr}`);
  return new Date(dateStr + 'Z');
}

/**
 * 格式化為本地時間字符串
 */
export function formatLocalDateTime(dateStr: string | Date, options?: Intl.DateTimeFormatOptions): string {
  const date = parseDateTime(dateStr);
  
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    ...options
  };
  
  return new Intl.DateTimeFormat('zh-CN', defaultOptions).format(date);
}

/**
 * 計算時間差並返回人性化描述
 */
export function getRelativeTime(dateStr: string | Date): string {
  const date = parseDateTime(dateStr);
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
  return formatLocalDateTime(date, {
    year: date.getFullYear() === now.getFullYear() ? undefined : 'numeric',
    month: '2-digit',
    day: '2-digit'
  });
}

/**
 * 檢查是否為今天
 */
export function isToday(dateStr: string | Date): boolean {
  const date = parseDateTime(dateStr);
  const now = new Date();
  
  return date.getDate() === now.getDate() &&
         date.getMonth() === now.getMonth() &&
         date.getFullYear() === now.getFullYear();
}

/**
 * 檢查是否為昨天
 */
export function isYesterday(dateStr: string | Date): boolean {
  const date = parseDateTime(dateStr);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  
  return date.getDate() === yesterday.getDate() &&
         date.getMonth() === yesterday.getMonth() &&
         date.getFullYear() === yesterday.getFullYear();
}

/**
 * 獲取時區安全的當前時間（UTC）
 */
export function getNowUTC(): string {
  return new Date().toISOString();
}

/**
 * 轉換為 UTC 時間字符串
 */
export function toUTCString(dateStr: string | Date): string {
  return parseDateTime(dateStr).toISOString();
}