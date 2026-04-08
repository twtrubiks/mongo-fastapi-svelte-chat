import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  toBffErrorResponse,
  isTokenExpired,
} from '$lib/bff-utils';
import { tryRefreshIfNeeded } from '$lib/bff-auth';

// 檔案上傳代理 API
// multipart/form-data 無法走 bffAuthRequest，但仍需透明 refresh
export const POST: RequestHandler = async ({ cookies, request }) => {
  let token = cookies.get('auth_token');

  if (!token || isTokenExpired(token)) {
    token = (await tryRefreshIfNeeded(cookies)) ?? undefined;
    if (!token) {
      return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
    }
  }

  try {
    const contentType = request.headers.get('content-type');

    if (!contentType || !contentType.includes('multipart/form-data')) {
      return json(
        createBFFError('VALIDATION_ERROR', '無效的請求格式，需要 multipart/form-data'),
        { status: 400 }
      );
    }

    const formData = await request.formData();
    const file = formData.get('file') as File;
    const uploadType = formData.get('type') as string || 'general';

    const validation = validateFile(file, uploadType);
    if (!validation.valid) {
      return json(createBFFError('VALIDATION_ERROR', validation.error!), { status: 400 });
    }

    const uploadEndpoint = getUploadEndpoint(uploadType);

    const backendFormData = new FormData();
    backendFormData.append('file', file);

    if (formData.get('description')) {
      backendFormData.append('description', formData.get('description') as string);
    }

    const uploadResult = await bffBackendClient.request(uploadEndpoint, {
      method: 'POST',
      data: backendFormData,
      headers: {
        'Content-Type': undefined as any
      },
      token
    }) as { file: any; message?: string; };

    const enhancedResult = {
      ...uploadResult,
      file: {
        ...(uploadResult.file || {}),
        uploadedAt: new Date().toISOString(),
        uploadType,
        size: file.size,
        originalName: file.name,
      }
    };

    return json(createBFFResponse(enhancedResult), {
      headers: { 'Cache-Control': 'no-cache' },
    });
  } catch (error: any) {
    if (error.code === 413 || error.message?.includes('too large')) {
      return json(createBFFError('VALIDATION_ERROR', '檔案大小超過限制'), { status: 413 });
    }
    if (error.code === 415 || error.message?.includes('unsupported')) {
      return json(createBFFError('VALIDATION_ERROR', '不支援的檔案類型'), { status: 415 });
    }
    return toBffErrorResponse(error, '檔案上傳失敗');
  }
};

function validateFile(file: File | null, uploadType: string): { valid: boolean; error?: string; } {
  if (!file) return { valid: false, error: '沒有選擇檔案' };

  const sizeLimits: Record<string, number> = {
    image: 10 * 1024 * 1024,
    document: 50 * 1024 * 1024,
    audio: 20 * 1024 * 1024,
    video: 100 * 1024 * 1024,
    general: 5 * 1024 * 1024,
  };

  const maxSize = sizeLimits[uploadType] ?? sizeLimits['general'] ?? 5 * 1024 * 1024;
  if (file.size > maxSize) {
    return { valid: false, error: `檔案大小不能超過 ${Math.round(maxSize / 1024 / 1024)}MB` };
  }

  const allowedTypes: Record<string, string[]> = {
    image: ['image/jpeg', 'image/png', 'image/gif', 'image/webp'],
    document: ['application/pdf', 'text/plain', 'application/msword',
               'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    audio: ['audio/mpeg', 'audio/wav', 'audio/ogg'],
    video: ['video/mp4', 'video/avi', 'video/mov', 'video/webm'],
    general: [],
  };

  const allowed = allowedTypes[uploadType];
  if (allowed && allowed.length > 0 && !allowed.includes(file.type)) {
    return { valid: false, error: `不支援的檔案類型：${file.type}` };
  }

  if (file.name.length > 255) return { valid: false, error: '檔案名過長' };

  const dangerousPatterns = [/\.exe$/i, /\.bat$/i, /\.cmd$/i, /\.scr$/i];
  if (dangerousPatterns.some(pattern => pattern.test(file.name))) {
    return { valid: false, error: '不允許的檔案類型' };
  }

  return { valid: true };
}

function getUploadEndpoint(uploadType: string): string {
  const endpoints: Record<string, string> = {
    image: '/api/files/upload/image',
    document: '/api/files/upload',
    audio: '/api/files/upload',
    video: '/api/files/upload',
    general: '/api/files/upload',
  };
  return endpoints[uploadType] ?? endpoints['general'] ?? '/api/files/upload';
}
