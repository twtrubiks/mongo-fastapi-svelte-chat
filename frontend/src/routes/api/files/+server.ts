import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';

// 檔案上傳代理 API
export const POST: RequestHandler = withPerformanceTracking(async ({ cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  try {
    // 檢查 Content-Type
    const contentType = request.headers.get('content-type');
    
    if (!contentType || !contentType.includes('multipart/form-data')) {
      return json(
        createBFFError('VALIDATION_ERROR', '無效的請求格式，需要 multipart/form-data'),
        { status: 400 }
      );
    }

    // 獲取上傳的檔案
    const formData = await request.formData();
    const file = formData.get('file') as File;
    const uploadType = formData.get('type') as string || 'general';
    
    // 驗證檔案
    const validation = validateFile(file, uploadType);
    if (!validation.valid) {
      return json(
        createBFFError('VALIDATION_ERROR', validation.error!),
        { status: 400 }
      );
    }
    
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 根據檔案類型選擇適當的上傳端點
    const uploadEndpoint = getUploadEndpoint(uploadType);
    
    // 創建新的 FormData 用於轉發到後端
    const backendFormData = new FormData();
    backendFormData.append('file', file);
    
    // 添加額外的元數據
    if (formData.get('description')) {
      backendFormData.append('description', formData.get('description') as string);
    }
    
    // 轉發到後端
    const uploadResult = await bffBackendClient.request(uploadEndpoint, {
      method: 'POST',
      data: backendFormData,
      headers: {
        // 刪除 Content-Type 讓 axios 自動設置 multipart/form-data
        'Content-Type': undefined as any
      }
    }) as { file: any; message?: string; };
    
    // 增強響應資料
    const enhancedResult = {
      ...uploadResult,
      file: {
        ...(uploadResult.file || {}),
        // 添加前端需要的額外資訊
        uploadedAt: new Date().toISOString(),
        uploadType,
        size: file.size,
        originalName: file.name,
      }
    };
    
    
    return json(createBFFResponse(enhancedResult), {
      headers: {
        'Cache-Control': 'no-cache',
      },
    });
    
  } catch (error: any) {
    
    if (error.code === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    
    if (error.code === 413 || error.message?.includes('too large')) {
      return json(
        createBFFError('VALIDATION_ERROR', '檔案大小超過限制'),
        { status: 413 }
      );
    }
    
    if (error.code === 415 || error.message?.includes('unsupported')) {
      return json(
        createBFFError('VALIDATION_ERROR', '不支援的檔案類型'),
        { status: 415 }
      );
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '檔案上傳失敗', error),
      { status: 500 }
    );
  }
}, 'file_upload_proxy');

// 檔案下載代理 API
export const GET: RequestHandler = async ({ cookies, url }) => {
  const token = getAuthToken(cookies);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  const fileType = url.searchParams.get('type');
  const filename = url.searchParams.get('filename');
  
  if (!fileType || !filename) {
    return json(
      createBFFError('VALIDATION_ERROR', '缺少檔案類型或檔案名'),
      { status: 400 }
    );
  }
  
  try {
    // 檢查用戶是否有權限訪問此檔案
    if (!hasFileAccess(null, token)) {
      return json(createBFFError('FORBIDDEN', '沒有權限訪問此檔案'), { status: 403 });
    }
    
    // 返回檔案訪問資訊（直接代理到後端）
    return json(createBFFResponse({
      url: `http://localhost:8000/api/files/${fileType}/${filename}`,
      proxyUrl: `/api/files/${fileType}/${filename}`,
      filename,
      type: fileType,
      accessible: true,
      message: '檔案可訪問',
    }));
    
  } catch (error: any) {
    
    if (error.code === 404) {
      return json(createBFFError('NOT_FOUND', '檔案不存在'), { status: 404 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '檔案訪問失敗', error),
      { status: 500 }
    );
  }
};

// 驗證檔案
function validateFile(file: File | null, uploadType: string): { 
  valid: boolean; 
  error?: string; 
} {
  if (!file) {
    return { valid: false, error: '沒有選擇檔案' };
  }
  
  // 檔案大小限制（根據類型）- 與前端工具函數保持一致
  const sizeLimits: Record<string, number> = {
    image: 10 * 1024 * 1024,      // 10MB
    document: 50 * 1024 * 1024,   // 50MB
    audio: 20 * 1024 * 1024,      // 20MB
    video: 100 * 1024 * 1024,     // 100MB
    general: 5 * 1024 * 1024,     // 5MB
  };
  
  const maxSize = sizeLimits[uploadType] || sizeLimits.general;
  if (file.size > maxSize) {
    return { 
      valid: false, 
      error: `檔案大小不能超過 ${Math.round(maxSize / 1024 / 1024)}MB` 
    };
  }
  
  // 檔案類型驗證
  const allowedTypes: Record<string, string[]> = {
    image: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    document: ['application/pdf', 'text/plain', 'application/msword', 
               'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    audio: ['audio/mpeg', 'audio/wav', 'audio/ogg'],
    video: ['video/mp4', 'video/avi', 'video/mov', 'video/webm'],
    general: [], // 允許所有類型
  };
  
  const allowed = allowedTypes[uploadType];
  if (allowed && allowed.length > 0 && !allowed.includes(file.type)) {
    return { 
      valid: false, 
      error: `不支援的檔案類型：${file.type}` 
    };
  }
  
  // 檔案名驗證
  if (file.name.length > 255) {
    return { valid: false, error: '檔案名過長' };
  }
  
  // 檢查惡意檔案名
  const dangerousPatterns = [/\.exe$/i, /\.bat$/i, /\.cmd$/i, /\.scr$/i];
  if (dangerousPatterns.some(pattern => pattern.test(file.name))) {
    return { valid: false, error: '不允許的檔案類型' };
  }
  
  return { valid: true };
}

// 根據檔案類型選擇上傳端點
function getUploadEndpoint(uploadType: string): string {
  const endpoints: Record<string, string> = {
    image: '/api/files/upload/image',
    // 其他類型都使用通用端點，因為後端只實現了 image 和 general
    document: '/api/files/upload',
    audio: '/api/files/upload',
    video: '/api/files/upload',
    general: '/api/files/upload',
  };
  
  return endpoints[uploadType] || endpoints.general;
}

// 檢查檔案訪問權限（簡化版本）
function hasFileAccess(fileInfo: any, token: string): boolean {
  // 這裡應該實現實際的權限檢查邏輯
  // 例如檢查檔案是否屬於用戶，或者是否在用戶有權限的聊天室中分享
  
  // 目前簡化為：只要有有效 token 就可以訪問
  return !!token;
}

// 刪除檔案 API
export const DELETE: RequestHandler = async ({ cookies, url }) => {
  const token = getAuthToken(cookies);
  
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  const fileType = url.searchParams.get('type');
  const filename = url.searchParams.get('filename');
  
  if (!fileType || !filename) {
    return json(
      createBFFError('VALIDATION_ERROR', '缺少檔案類型或檔案名'),
      { status: 400 }
    );
  }
  
  try {
    bffBackendClient.setAuth(token);
    
    // 刪除檔案
    await bffBackendClient.request(`/api/files/${fileType}/${filename}`, {
      method: 'DELETE'
    });
    
    return json(createBFFResponse({ message: '檔案已刪除' }));
    
  } catch (error: any) {
    
    if (error.code === 404) {
      return json(createBFFError('NOT_FOUND', '檔案不存在'), { status: 404 });
    }
    
    if (error.code === 403) {
      return json(createBFFError('FORBIDDEN', '沒有權限刪除此檔案'), { status: 403 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '檔案刪除失敗', error),
      { status: 500 }
    );
  }
};