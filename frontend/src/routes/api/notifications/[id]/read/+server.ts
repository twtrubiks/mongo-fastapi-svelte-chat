import type { RequestHandler } from './$types';
import { json } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';

export const POST: RequestHandler = async ({ params, cookies }) => {
  const { id } = params;
  const authCookie = cookies.get('auth_token');
  
  if (!authCookie) {
    return json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // 設置認證
    bffBackendClient.setAuth(authCookie);
    
    
    // 轉發到後端
    const result = await bffBackendClient.request(`/api/notifications/${id}/read`, {
      method: 'POST'
    });
    
    return json(result);
  } catch (error: any) {
    
    // 根據錯誤碼返回相應的狀態
    if (error.code === 401) {
      return json({ error: 'Unauthorized' }, { status: 401 });
    }
    
    if (error.code === 404) {
      return json({ 
        code: 404,
        message: error.message || '通知不存在或無權限',
        details: error.details
      }, { status: 404 });
    }
    
    return json({ 
      code: error.code || 500,
      message: error.message || 'Failed to mark notification as read',
      details: error.details || (error instanceof Error ? error.message : 'Unknown error')
    }, { status: error.code || 500 });
  }
};