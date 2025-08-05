import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ params, fetch, request, cookies }) => {
  try {
    const { id } = params;
    const token = cookies.get('auth_token');
    
    if (!token) {
      return json({ error: { message: 'Unauthorized' } }, { status: 401 });
    }

    // 調用後端 API 離開房間
    const response = await fetch(`http://localhost:8000/api/rooms/${id}/leave`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      const error = await response.json();
      return json({ error }, { status: response.status });
    }

    const data = await response.json();
    return json({ success: true, data });
    
  } catch (error: any) {
    console.error('Leave room error:', error);
    return json({ 
      error: { 
        message: error.message || 'Failed to leave room' 
      } 
    }, { status: 500 });
  }
};