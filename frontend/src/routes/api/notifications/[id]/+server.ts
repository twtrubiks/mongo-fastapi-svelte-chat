import type { RequestHandler } from './$types';
import { json } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';

export const DELETE: RequestHandler = async ({ params, cookies }) => {
  const { id } = params;
  const authCookie = cookies.get('auth_token');
  
  if (!authCookie) {
    return json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // 設置認證
    bffBackendClient.setAuth(authCookie);
    
    // 轉發到後端
    const result = await bffBackendClient.request(`/api/notifications/${id}`, {
      method: 'DELETE'
    });
    
    return json(result);
  } catch (error: any) {
    
    // 檢查是否是 401 認證錯誤
    if (error.code === 401 || (error.message && error.message.includes('401'))) {
      return json({ error: 'Unauthorized' }, { status: 401 });
    }
    
    // 如果有具體的錯誤狀態碼，使用它
    const statusCode = error.code && typeof error.code === 'number' ? error.code : 500;
    
    return json({ 
      error: 'Failed to delete notification',
      details: error.message || 'Unknown error',
      backend_error: error.details
    }, { status: statusCode });
  }
};