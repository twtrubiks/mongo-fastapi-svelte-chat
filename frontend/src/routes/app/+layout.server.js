import { redirect } from '@sveltejs/kit';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ cookies, url, fetch }) {
  // 檢查是否有認證 token
  const token = cookies.get('auth_token');
  
  if (!token) {
    // 未登入，重定向到登入頁面
    throw redirect(302, '/login');
  }
  
  // 驗證 token 是否有效
  try {
    const response = await fetch('/api/auth/me');
    
    if (!response.ok) {
      cookies.delete('auth_token', { path: '/' });
      throw redirect(302, '/login');
    }
    
    const data = await response.json();
    
    return {
      token,
      user: data.data
    };
  } catch (error) {
    if (error instanceof redirect) {
      throw error;
    }
    cookies.delete('auth_token', { path: '/' });
    throw redirect(302, '/login');
  }
}