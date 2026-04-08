// 工具函數統一導出
export * from './auth';
export * from './clipboard';
export * from './datetime';
export * from './error';
// 通用工具函數
export function debounce<T extends (...args: any[]) => void>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout>;
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func(...args), delay);
  };
}

// 文件大小格式化
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

// 檔案類型定義
export interface FileTypeConfig {
  extensions: string[];
  mimeTypes: string[];
  maxSizeMB: number;
  icon: string;
  label: string;
}

// 支援的檔案類型配置
export const FILE_TYPE_CONFIGS: Record<string, FileTypeConfig> = {
  image: {
    extensions: ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
    mimeTypes: ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'],
    maxSizeMB: 10,
    icon: '🖼️',
    label: '圖片'
  },
  document: {
    extensions: ['.pdf', '.doc', '.docx', '.txt', '.md'],
    mimeTypes: ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/markdown'],
    maxSizeMB: 50,
    icon: '📄',
    label: '文檔'
  },
  video: {
    extensions: ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
    mimeTypes: ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska', 'video/webm'],
    maxSizeMB: 100,
    icon: '🎥',
    label: '影片'
  },
  audio: {
    extensions: ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
    mimeTypes: ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4', 'audio/flac'],
    maxSizeMB: 20,
    icon: '🎵',
    label: '音檔'
  }
};

// 檢查檔案類型
export function getFileType(file: File): string {
  const fileName = file.name.toLowerCase();
  const mimeType = file.type.toLowerCase();
  
  for (const [type, config] of Object.entries(FILE_TYPE_CONFIGS)) {
    // 檢查副檔名
    const hasValidExtension = config.extensions.some(ext => 
      fileName.endsWith(ext.toLowerCase())
    );
    
    // 檢查 MIME 類型
    const hasValidMimeType = config.mimeTypes.some(mime => 
      mimeType === mime.toLowerCase() || mimeType.startsWith(mime.toLowerCase())
    );
    
    if (hasValidExtension || hasValidMimeType) {
      return type;
    }
  }
  
  return 'general';
}

// 檢查是否為支援的檔案類型
export function isSupportedFileType(file: File, allowedTypes?: string[]): boolean {
  const fileType = getFileType(file);
  
  if (!allowedTypes) {
    return fileType !== 'general';
  }
  
  return allowedTypes.includes(fileType) || allowedTypes.includes('general');
}

// 檢查檔案是否為圖片（向後相容）
export function isImageFile(file: File): boolean {
  return getFileType(file) === 'image';
}

// 檢查檔案大小是否有效
export function isFileSizeValid(file: File, maxSizeMB?: number): boolean {
  const fileType = getFileType(file);
  const config = FILE_TYPE_CONFIGS[fileType];
  const limit = maxSizeMB || config?.maxSizeMB || 5;
  const maxSizeBytes = limit * 1024 * 1024;
  return file.size <= maxSizeBytes;
}

// 獲取檔案圖示
export function getFileIcon(file: File): string {
  const fileType = getFileType(file);
  const config = FILE_TYPE_CONFIGS[fileType];
  return config?.icon || '📎';
}

// 獲取檔案類型標籤
export function getFileTypeLabel(file: File): string {
  const fileType = getFileType(file);
  const config = FILE_TYPE_CONFIGS[fileType];
  return config?.label || '檔案';
}

// 獲取檔案最大大小限制
export function getMaxFileSize(file: File): number {
  const fileType = getFileType(file);
  const config = FILE_TYPE_CONFIGS[fileType];
  return config?.maxSizeMB || 5;
}

// 生成檔案接受的 MIME 類型字串
export function getAcceptString(allowedTypes?: string[]): string {
  if (!allowedTypes || allowedTypes.includes('general')) {
    // 返回所有支援的類型
    const allMimeTypes = Object.values(FILE_TYPE_CONFIGS)
      .flatMap(config => config.mimeTypes);
    return allMimeTypes.join(',');
  }
  
  const mimeTypes = allowedTypes
    .filter(type => FILE_TYPE_CONFIGS[type])
    .flatMap(type => FILE_TYPE_CONFIGS[type]?.mimeTypes || []);
  
  return mimeTypes.join(',');
}

// 生成頭像顏色
export function generateAvatarColor(name: string): string {
  const colors = [
    '#f87171', '#fb923c', '#fbbf24', '#facc15',
    '#a3e635', '#4ade80', '#34d399', '#2dd4bf',
    '#22d3ee', '#38bdf8', '#60a5fa', '#818cf8',
    '#a78bfa', '#c084fc', '#e879f9', '#f472b6',
    '#fb7185', '#fca5a5',
  ];
  
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  const index = Math.abs(hash) % colors.length;
  return colors[index]!;
}

// 生成頭像文字
export function generateAvatarText(name: string): string {
  if (!name) return 'U';
  
  const words = name.trim().split(/\s+/);
  if (words.length === 1) {
    return words[0]!.charAt(0).toUpperCase();
  }
  
  return (words[0]!.charAt(0) + words[1]!.charAt(0)).toUpperCase();
}

// 將完整後端 URL 轉為相對路徑（處理舊訊息中的完整 URL）
export function normalizeFileUrl(url: string): string {
  const idx = url.indexOf('/api/files/');
  return idx !== -1 ? url.slice(idx) : url;
}

// 從 URL 提取檔案名
export function extractFileNameFromUrl(url: string): string {
  if (!url) return 'unknown_file';
  
  try {
    // 移除查詢參數和片段
    const cleanUrl = url.split('?')[0]?.split('#')[0] || url;
    
    // 提取檔案名
    const urlParts = cleanUrl.split('/');
    let fileName = urlParts[urlParts.length - 1] || 'unknown_file';
    
    // 解碼 URL 編碼的檔案名
    fileName = decodeURIComponent(fileName);
    
    // 如果沒有副檔名，嘗試從 URL 中推斷
    if (!fileName.includes('.') && url.includes('.')) {
      const match = url.match(/\.([a-zA-Z0-9]+)(?:[?#]|$)/);
      if (match) {
        fileName += '.' + match[1];
      }
    }
    
    return fileName;
  } catch (error) {
    console.warn('Failed to extract filename from URL:', error);
    return 'unknown_file';
  }
}

// 從檔案 URL 推斷 MIME 類型
export function inferMimeTypeFromUrl(url: string): string {
  const fileName = extractFileNameFromUrl(url);
  const extension = fileName.split('.').pop()?.toLowerCase();
  
  const mimeMap: Record<string, string> = {
    // 圖片
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg', 
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'bmp': 'image/bmp',
    
    // 文檔
    'pdf': 'application/pdf',
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'txt': 'text/plain',
    'md': 'text/markdown',
    
    // 影片
    'mp4': 'video/mp4',
    'avi': 'video/avi',
    'mov': 'video/quicktime',
    'webm': 'video/webm',
    
    // 音檔
    'mp3': 'audio/mpeg',
    'wav': 'audio/wav',
    'ogg': 'audio/ogg',
  };
  
  return mimeMap[extension || ''] || 'application/octet-stream';
}

