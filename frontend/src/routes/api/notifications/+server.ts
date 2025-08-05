import type { RequestHandler } from './$types';
import { json } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import { transformNotificationListResponse } from '$lib/bff-utils';

export const GET: RequestHandler = async ({ url, cookies }) => {
  const authCookie = cookies.get('auth_token');
  
  if (!authCookie) {
    return json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // 設置認證
    bffBackendClient.setAuth(authCookie);
    
    // 獲取查詢參數
    const page = url.searchParams.get('page') || '1';
    const limit = url.searchParams.get('limit') || '20';
    const status = url.searchParams.get('status');
    const type = url.searchParams.get('type');
    
    // 構建查詢字符串
    const params = new URLSearchParams({
      page,
      limit
    });
    
    if (status) params.append('status', status);
    if (type) params.append('type', type);
    
    // 轉發到後端
    const response = await bffBackendClient.request(`/api/notifications/?${params.toString()}`, {
      method: 'GET'
    });
    
    // 轉換通知資料格式
    const transformedResponse = transformNotificationListResponse(response);
    
    return json(transformedResponse);
  } catch (error) {
    
    if (error instanceof Error && error.message.includes('401')) {
      return json({ error: 'Unauthorized' }, { status: 401 });
    }
    
    return json({ 
      error: 'Failed to fetch notifications',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
};