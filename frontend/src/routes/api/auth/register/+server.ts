import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  withPerformanceTracking
} from '$lib/bff-utils';

// 註冊 API
export const POST: RequestHandler = withPerformanceTracking(async ({ request, cookies }) => {
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
    }) as { access_token: string; user: any; token_type: string; };

    // 設置 HttpOnly cookie (如果註冊成功後自動登入)
    if (registerResult.access_token) {
      cookies.set('auth_token', registerResult.access_token, {
        path: '/',
        httpOnly: true,
        secure: typeof process !== 'undefined' && process.env?.NODE_ENV === 'production',
        sameSite: 'strict',
        maxAge: 60 * 60 * 24 * 7 // 7 days
      });
    }

    return json(createBFFResponse(registerResult));

  } catch (error: any) {
    console.error('註冊錯誤:', error);

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
}, 'auth_register');