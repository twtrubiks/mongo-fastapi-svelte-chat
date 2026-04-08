import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
} from '$lib/bff-utils';
import { setAuthCookies } from '$lib/bff-cookie';

// 註冊 API
export const POST: RequestHandler = async ({ request, cookies }) => {
  try {
    // 獲取註冊資料
    const registerData = await request.json();

    // 基本驗證
    if (!registerData.username || !registerData.password || !registerData.email) {
      return json(
        createBFFError('VALIDATION_ERROR', '用戶名、密碼和郵箱不能為空'),
        { status: 400 }
      );
    }

    // 轉發到後端註冊 API
    const registerResult = await bffBackendClient.request('/api/auth/register', {
      method: 'POST',
      data: registerData,
      headers: {
        'Content-Type': 'application/json'
      }
    }) as { access_token: string; refresh_token?: string; user: any; token_type: string; };

    if (registerResult.access_token) {
      setAuthCookies(cookies, registerResult.access_token, registerResult.refresh_token);
    }

    // 只回傳 user，不回傳 token（token 存在 httpOnly cookie 中）
    return json(createBFFResponse({ user: registerResult.user }));

  } catch (error: any) {

    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '註冊失敗';

    if (error.code === 409 || error.code === 'CONFLICT') {
      statusCode = 409;
      errorMessage = '用戶名或郵箱已存在';
    } else if (error.code === 422 || error.code === 'VALIDATION_ERROR') {
      statusCode = 422;
      errorMessage = error.message || '註冊資料格式錯誤';
    }

    return json(
      createBFFError('REGISTER_ERROR', errorMessage, error.details),
      { status: statusCode }
    );
  }
};
