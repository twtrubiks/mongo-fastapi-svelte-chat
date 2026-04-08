import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { bffBackendClient } from '$lib/bff-client';
import { clearAuthCookies } from '$lib/bff-cookie';

export const POST: RequestHandler = async ({ cookies }) => {
  try {
    const token = cookies.get('auth_token');

    // 調用後端登出 API（失敗也不影響前端清除流程）
    if (token) {
      try {
        await bffBackendClient.request('/api/auth/logout', {
          method: 'POST',
          token
        });
      } catch {
        // 後端登出失敗，繼續清除前端狀態
      }
    }

    // 清除認證 cookie
    clearAuthCookies(cookies);

    return json({
      success: true,
      message: '登出成功',
      redirectTo: '/login'
    });

  } catch (error) {

    // 即使出錯也要清除 cookie
    clearAuthCookies(cookies);

    return json({
      success: false,
      error: '登出操作失敗',
      message: error instanceof Error ? error.message : '未知錯誤'
    }, { status: 500 });
  }
};
