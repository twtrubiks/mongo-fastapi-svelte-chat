import { isRedirect, redirect } from '@sveltejs/kit';
import { isTokenExpiringSoon } from '$lib/bff-utils';
import { clearAuthCookies } from '$lib/bff-cookie';
import { loginUrl } from '$lib/utils/loginRedirect';

/** @type {import('./$types').LayoutServerLoad} */
export async function load({ cookies, fetch, url, untrack }) {
  // 登入後回到原頁面；untrack 避免讀 url 讓這個 load 在 /app 底下每次換頁都重跑
  const toLogin = untrack(() => loginUrl(url.pathname + url.search));
  const token = cookies.get('auth_token');

  if (!token) {
    throw redirect(302, toLogin);
  }

  // 如果 access token 即將過期，先嘗試 refresh（cookie 會自動更新）
  if (isTokenExpiringSoon(token)) {
    try {
      const refreshResponse = await fetch('/api/auth/refresh', { method: 'POST' });
      if (!refreshResponse.ok) {
        clearAuthCookies(cookies);
        throw redirect(302, toLogin);
      }
    } catch (error) {
      if (isRedirect(error)) throw error;
      clearAuthCookies(cookies);
      throw redirect(302, toLogin);
    }
  }

  // 驗證 token 是否有效
  try {
    const response = await fetch('/api/auth/me');

    if (!response.ok) {
      clearAuthCookies(cookies);
      throw redirect(302, toLogin);
    }

    const data = await response.json();

    // 不回傳 token — token 由 httpOnly cookie 管理
    return {
      user: data.data
    };
  } catch (error) {
    if (isRedirect(error)) {
      throw error;
    }
    clearAuthCookies(cookies);
    throw redirect(302, toLogin);
  }
}
