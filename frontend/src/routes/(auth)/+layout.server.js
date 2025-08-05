import { redirect } from '@sveltejs/kit';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ cookies, fetch, url }) {
  // 檢查是否已經登入
  const token = cookies.get('auth_token');
  
  if (token) {
    // 驗證 token 是否有效
    try {
      const response = await fetch('/api/auth/me');
      
      if (response.ok) {
        // token 有效，重定向到應用
        throw redirect(302, '/app');
      } else {
        // token 無效，清除 cookie
        cookies.delete('auth_token', { path: '/' });
      }
    } catch (error) {
      // 檢查是否是 SvelteKit 的 redirect
      if (error && typeof error === 'object' && 'status' in error && 'location' in error) {
        throw error;
      }
      // 其他錯誤，清除 cookie
      cookies.delete('auth_token', { path: '/' });
    }
  }
  
  return {};
}