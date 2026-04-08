import { redirect } from '@sveltejs/kit';
import { isTokenExpiringSoon } from '$lib/bff-utils';
import { clearAuthCookies } from '$lib/bff-cookie';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ cookies, fetch }) {
  const token = cookies.get('auth_token');

  if (!token) {
    throw redirect(302, '/login');
  }

  // 如果 access token 即將過期，先嘗試 refresh（cookie 會自動更新）
  if (isTokenExpiringSoon(token)) {
    try {
      const refreshResponse = await fetch('/api/auth/refresh', { method: 'POST' });
      if (!refreshResponse.ok) {
        clearAuthCookies(cookies);
        throw redirect(302, '/login');
      }
    } catch (error) {
      if (error instanceof redirect) throw error;
      clearAuthCookies(cookies);
      throw redirect(302, '/login');
    }
  }

  // 驗證 token 是否有效
  try {
    const response = await fetch('/api/auth/me');

    if (!response.ok) {
      clearAuthCookies(cookies);
      throw redirect(302, '/login');
    }

    const data = await response.json();

    // 不回傳 token — token 由 httpOnly cookie 管理
    return {
      user: data.data
    };
  } catch (error) {
    if (error instanceof redirect) {
      throw error;
    }
    clearAuthCookies(cookies);
    throw redirect(302, '/login');
  }
}
