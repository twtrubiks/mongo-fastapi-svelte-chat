import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';

// 獲取房間列表
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, url, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 獲取查詢參數
    const queryParams = new URLSearchParams();
    const limit = url.searchParams.get('limit');
    const offset = url.searchParams.get('offset');
    const search = url.searchParams.get('search');
    
    if (limit) queryParams.append('limit', limit);
    if (offset) queryParams.append('offset', offset);
    if (search) queryParams.append('search', search);
    
    const queryString = queryParams.toString();
    const endpoint = queryString ? `/api/rooms?${queryString}` : '/api/rooms';
    
    // 轉發到後端
    
    const rooms = await bffBackendClient.request(endpoint, {
      method: 'GET'
    });
    
    
    return json(createBFFResponse(rooms));
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 403 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取房間列表失敗', error.details),
      { status: 500 }
    );
  }
}, 'rooms_list');

// 創建新房間
export const POST: RequestHandler = withPerformanceTracking(async ({ cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 獲取請求數據
    const roomData = await request.json();
    
    // 基本驗證
    if (!roomData.name) {
      return json(
        createBFFError('VALIDATION_ERROR', '房間名稱不能為空'),
        { status: 400 }
      );
    }
    
    // 轉發到後端
    const newRoom = await bffBackendClient.request('/api/rooms/', {
      method: 'POST',
      data: roomData
    });
    
    return json(createBFFResponse(newRoom), { status: 201 });
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 403 });
    }
    
    // 處理 400 錯誤（包括房間名稱已存在）
    if (error.code === 400 || error.code === 'BAD_REQUEST') {
      // 使用後端返回的具體錯誤訊息
      const errorMessage = error.message || '創建房間失敗';
      return json(createBFFError('BAD_REQUEST', errorMessage), { status: 400 });
    }
    
    if (error.code === 409 || error.code === 'CONFLICT') {
      return json(createBFFError('CONFLICT', '房間名稱已存在'), { status: 409 });
    }
    
    // 使用後端返回的錯誤訊息，如果沒有則使用通用訊息
    const errorMessage = error.message || '創建房間失敗';
    return json(
      createBFFError('INTERNAL_ERROR', errorMessage, error.details),
      { status: 500 }
    );
  }
}, 'rooms_create');