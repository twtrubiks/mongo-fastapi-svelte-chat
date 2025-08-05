import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking,
  transformNotificationStats
} from '$lib/bff-utils';

// 獲取通知統計
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
    const stats = await bffBackendClient.request('/api/notifications/stats', {
      method: 'GET'
    });
    
    // 轉換通知統計資料格式
    const transformedStats = transformNotificationStats(stats);
    
    return json(createBFFResponse(transformedStats));
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 403 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取通知統計失敗', error.details),
      { status: 500 }
    );
  }
}, 'notifications_stats');