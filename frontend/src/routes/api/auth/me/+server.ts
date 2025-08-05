import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';

// 獲取當前用戶資訊
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端
    const user = await bffBackendClient.request('/api/auth/me', {
      method: 'GET'
    });
    
    return json(createBFFResponse(user));
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取用戶資訊失敗', error.details),
      { status: 500 }
    );
  }
}, 'auth_me');