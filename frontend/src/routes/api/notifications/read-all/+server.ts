import type { RequestHandler } from './$types';
import { json } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';

export const POST: RequestHandler = async ({ cookies }) => {
  const authCookie = cookies.get('auth_token');
  
  if (!authCookie) {
    return json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    // 設置認證
    bffBackendClient.setAuth(authCookie);
    
    // 轉發到後端
    const result = await bffBackendClient.request('/api/notifications/read-all', {
      method: 'POST'
    });
    
    return json(result);
  } catch (error) {
    
    if (error instanceof Error && error.message.includes('401')) {
      return json({ error: 'Unauthorized' }, { status: 401 });
    }
    
    return json({ 
      error: 'Failed to mark all notifications as read',
      details: error instanceof Error ? error.message : 'Unknown error'
    }, { status: 500 });
  }
};