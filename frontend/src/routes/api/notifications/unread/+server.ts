import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking,
  transformNotifications
} from '$lib/bff-utils';

// 獲取未讀通知
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, url, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 獲取查詢參數
    const limit = url.searchParams.get('limit') || '10';
    
    // 轉發到後端
    const notifications = await bffBackendClient.request(`/api/notifications/unread?limit=${limit}`, {
      method: 'GET'
    });
    
    // 轉換通知資料格式
    const transformedNotifications = transformNotifications(notifications);
    
    return json(createBFFResponse(transformedNotifications));
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 403 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取未讀通知失敗', error.details),
      { status: 500 }
    );
  }
}, 'notifications_unread');