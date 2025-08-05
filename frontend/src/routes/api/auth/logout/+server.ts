import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ cookies, fetch }) => {
  try {
    const token = cookies.get('auth_token');
    
    // 調用後端登出 API（如果有的話）
    if (token) {
      try {
        const backendResponse = await fetch('http://localhost:8000/api/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (!backendResponse.ok) {
          // 後端登出失敗，但繼續清除前端狀態
        }
      } catch (error) {
        // 繼續前端登出流程
      }
    }
    
    // 清除所有認證相關 cookies - 關鍵步驟
    
    // 清除 auth_token cookie
    cookies.delete('auth_token', { 
      path: '/',
      secure: false,    // 開發環境設為 false
      httpOnly: true,
      sameSite: 'strict'
    });
    
    // 嘗試不同的清除方式
    cookies.set('auth_token', '', {
      path: '/',
      expires: new Date(0),
      httpOnly: true,
      secure: false,
      sameSite: 'strict'
    });
    
    // 清除其他可能的認證 cookies
    cookies.delete('refresh_token', { path: '/' });
    cookies.delete('session_id', { path: '/' });
    
    
    return json({ 
      success: true, 
      message: '登出成功',
      redirectTo: '/login'
    });
    
  } catch (error) {
    
    // 即使出錯也要清除 cookies
    cookies.delete('auth_token', { path: '/' });
    cookies.delete('refresh_token', { path: '/' });
    
    return json({ 
      success: false, 
      error: '登出操作失敗',
      message: error instanceof Error ? error.message : '未知錯誤'
    }, { status: 500 });
  }
};