import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';

// 獲取房間訊息列表
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, params, url, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 獲取查詢參數
    const queryParams = new URLSearchParams();
    const limit = url.searchParams.get('limit') || '50';
    const offset = url.searchParams.get('offset') || '0';
    const before = url.searchParams.get('before');
    const after = url.searchParams.get('after');
    
    queryParams.append('limit', limit);
    queryParams.append('offset', offset);
    if (before) queryParams.append('before', before);
    if (after) queryParams.append('after', after);
    
    // 轉發到後端房間訊息 API
    const messages = await bffBackendClient.request(`/api/rooms/${roomId}/messages?${queryParams.toString()}`, {
      method: 'GET'
    }) as Array<{
      id: string;
      room_id: string;
      user_id: string;
      type: 'TEXT' | 'IMAGE' | 'SYSTEM';
      content: string;
      metadata?: Record<string, any>;
      created_at: string;
      updated_at: string;
    }>;
    
    return json(createBFFResponse(messages));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}/messages] 錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '獲取訊息失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限訪問此房間的訊息';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    }
    
    return json(
      createBFFError('MESSAGES_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});

// 發送新訊息
export const POST: RequestHandler = withPerformanceTracking(async ({ cookies, params, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }
  
  try {
    const messageData = await request.json();
    
    // 基本驗證
    if (!messageData.content || messageData.content.trim().length === 0) {
      return json(
        createBFFError('VALIDATION_ERROR', '訊息內容不能為空'),
        { status: 400 }
      );
    }
    
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端發送訊息 API
    const newMessage = await bffBackendClient.request(`/api/rooms/${roomId}/messages`, {
      method: 'POST',
      data: {
        content: messageData.content.trim(),
        message_type: messageData.type || 'text',  // 使用 message_type 而不是 type
        room_id: roomId,                            // 添加 room_id 字段
        metadata: messageData.metadata || {}
      },
      headers: {
        'Content-Type': 'application/json'
      }
    }) as {
      id: string;
      room_id: string;
      user_id: string;
      type: string;
      content: string;
      metadata?: Record<string, any>;
      created_at: string;
      updated_at: string;
    };
    
    return json(createBFFResponse(newMessage));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}/messages] 發送錯誤:`, {
      message: error.message,
      response: error.response?.data,
      status: error.response?.status,
      config: error.config?.url,
      stack: error.stack
    });
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '發送訊息失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限在此房間發送訊息';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    } else if (error.response?.status === 422) {
      statusCode = 422;
      errorMessage = error.response.data?.detail || '訊息格式錯誤';
    } else if (error.response?.status === 429) {
      statusCode = 429;
      errorMessage = '發送太頻繁，請稍後再試';
    }
    
    return json(
      createBFFError('MESSAGE_SEND_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});