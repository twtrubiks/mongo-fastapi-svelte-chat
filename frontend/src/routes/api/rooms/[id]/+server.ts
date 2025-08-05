import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';

// 獲取單個房間詳細資訊
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, params, request }) => {
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
    
    // 轉發到後端房間詳細 API
    const roomData = await bffBackendClient.request(`/api/rooms/${roomId}`, {
      method: 'GET'
    }) as { 
      id: string; 
      name: string; 
      description?: string; 
      owner_id: string;
      created_at: string;
      updated_at: string;
      member_count?: number;
    };
    
    return json(createBFFResponse(roomData));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}] 錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '獲取房間信息失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限訪問此房間';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    }
    
    return json(
      createBFFError('ROOM_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});

// 更新房間資訊
export const PUT: RequestHandler = withPerformanceTracking(async ({ cookies, params, request }) => {
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
    const updateData = await request.json();
    
    // 基本驗證
    if (updateData.name && updateData.name.trim().length === 0) {
      return json(
        createBFFError('VALIDATION_ERROR', '房間名稱不能為空'),
        { status: 400 }
      );
    }
    
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端房間更新 API
    const updatedRoom = await bffBackendClient.request(`/api/rooms/${roomId}`, {
      method: 'PUT',
      data: updateData,
      headers: {
        'Content-Type': 'application/json'
      }
    }) as {
      id: string;
      name: string;
      description?: string;
      owner_id: string;
      updated_at: string;
    };
    
    return json(createBFFResponse(updatedRoom));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}] 更新錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '更新房間失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限修改此房間';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    } else if (error.response?.status === 422) {
      statusCode = 422;
      errorMessage = error.response.data?.detail || '資料驗證失敗';
    }
    
    return json(
      createBFFError('ROOM_UPDATE_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});

// 刪除房間
export const DELETE: RequestHandler = withPerformanceTracking(async ({ cookies, params, request }) => {
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
    
    // 轉發到後端房間刪除 API
    await bffBackendClient.request(`/api/rooms/${roomId}`, {
      method: 'DELETE'
    });
    
    return json(createBFFResponse({ 
      success: true, 
      message: '房間已刪除',
      roomId 
    }));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}] 刪除錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '刪除房間失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限刪除此房間';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    }
    
    return json(
      createBFFError('ROOM_DELETE_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});