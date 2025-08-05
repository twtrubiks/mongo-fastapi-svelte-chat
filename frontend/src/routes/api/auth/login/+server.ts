import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  withPerformanceTracking
} from '$lib/bff-utils';

// 登入 API
export const POST: RequestHandler = withPerformanceTracking(async ({ request, cookies }) => {
  try {
    // 獲取登入資料 - 處理不同的內容類型
    let username: string;
    let password: string;
    
    const contentType = request.headers.get('content-type');
    
    if (contentType?.includes('application/x-www-form-urlencoded')) {
      // 處理 URLSearchParams
      const text = await request.text();
      const params = new URLSearchParams(text);
      username = params.get('username') || '';
      password = params.get('password') || '';
    } else if (contentType?.includes('multipart/form-data')) {
      // 處理 FormData
      const formData = await request.formData();
      username = formData.get('username') as string;
      password = formData.get('password') as string;
    } else {
      // 嘗試 JSON
      const data = await request.json();
      username = data.username;
      password = data.password;
    }
    

    // 驗證輸入
    if (!username || !password) {
      return json(
        createBFFError('VALIDATION_ERROR', '用戶名和密碼不能為空'),
        { status: 400 }
      );
    }

    // 準備發送到後端的 FormData
    const backendFormData = new URLSearchParams();
    backendFormData.append('username', username);
    backendFormData.append('password', password);

    // 轉發到後端登入 API
    // 注意：URLSearchParams 需要轉換為字符串
    const loginResult = await bffBackendClient.request('/api/auth/login', {
      method: 'POST',
      data: backendFormData.toString(),
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    }) as { access_token: string; user: any; token_type: string; };

    // 設置 HttpOnly cookie (可選的安全增強)
    if (loginResult.access_token) {
      cookies.set('auth_token', loginResult.access_token, {
        path: '/',
        httpOnly: true,
        secure: typeof process !== 'undefined' && process.env?.NODE_ENV === 'production',
        sameSite: 'strict',
        maxAge: 60 * 60 * 24 * 7 // 7 days
      });
    }

    return json(createBFFResponse(loginResult));

  } catch (error: any) {

    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '登入失敗';

    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      statusCode = 401;
      errorMessage = '用戶名或密碼錯誤';
    } else if (error.code === 422 || error.code === 'VALIDATION_ERROR') {
      statusCode = 422;
      errorMessage = error.message || '登入資料格式錯誤';
    }

    // 添加更詳細的錯誤信息
    const errorDetails = {
      ...error.details,
      serverMessage: error.message,
      bffError: true
    };

    return json(
      createBFFError('AUTH_ERROR', errorMessage, errorDetails),
      { status: statusCode }
    );
  }
}, 'auth_login');