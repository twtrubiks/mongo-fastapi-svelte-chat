import { env } from '$env/dynamic/private';
import type { Cookies } from '@sveltejs/kit';

// 設定認證相關 cookie（供 login/register/refresh 路由共用）
export function setAuthCookies(cookies: Cookies, accessToken: string, refreshToken?: string) {
  const cookieOptions = {
    path: '/',
    httpOnly: true,
    secure: env['NODE_ENV'] === 'production',
    sameSite: 'strict' as const,
    maxAge: 60 * 60 * 24 * 7, // 7 days
  };

  cookies.set('auth_token', accessToken, cookieOptions);
  if (refreshToken) {
    cookies.set('refresh_token', refreshToken, cookieOptions);
  }
}

// 清除所有認證 cookie
export function clearAuthCookies(cookies: Cookies) {
  cookies.delete('auth_token', { path: '/' });
  cookies.delete('refresh_token', { path: '/' });
}
