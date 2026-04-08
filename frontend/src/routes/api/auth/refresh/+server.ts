import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
} from '$lib/bff-utils';
import { setAuthCookies, clearAuthCookies } from '$lib/bff-cookie';

// Refresh Token API — 用 HttpOnly cookie 中的 refresh_token 換發新 token
export const POST: RequestHandler = async ({ cookies }) => {
  try {
    const refreshToken = cookies.get('refresh_token');

    if (!refreshToken) {
      return json(
        createBFFError('UNAUTHORIZED', 'Refresh token 不存在'),
        { status: 401 }
      );
    }

    // 轉發到後端 refresh endpoint
    const result = await bffBackendClient.request('/api/auth/refresh', {
      method: 'POST',
      data: { refresh_token: refreshToken },
      headers: {
        'Content-Type': 'application/json'
      }
    }) as { access_token: string; refresh_token: string; token_type: string; };

    setAuthCookies(cookies, result.access_token, result.refresh_token);

    // 不回傳 token 給前端（httpOnly cookie 已更新）
    return json(createBFFResponse({ refreshed: true }));

  } catch {
    clearAuthCookies(cookies);

    return json(
      createBFFError('UNAUTHORIZED', 'Token 刷新失敗，請重新登入'),
      { status: 401 }
    );
  }
};
