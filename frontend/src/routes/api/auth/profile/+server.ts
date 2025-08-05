import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';

// 獲取用戶詳細資料
export const GET: RequestHandler = withPerformanceTracking(async ({ cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端
    const profile = await bffBackendClient.request('/api/auth/profile', {
      method: 'GET'
    });
    
    return json(createBFFResponse(profile));
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
    }
    
    if (error.code === 404 || error.code === 'NOT_FOUND') {
      return json(createBFFError('NOT_FOUND', '用戶不存在'), { status: 404 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '獲取用戶詳細資料失敗', error.details),
      { status: 500 }
    );
  }
}, 'auth_profile_get');

// 更新用戶資料
export const PUT: RequestHandler = withPerformanceTracking(async ({ cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
  }
  
  try {
    // 獲取請求資料
    const updateData = await request.json();
    
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端
    const updatedProfile = await bffBackendClient.request('/api/auth/profile', {
      method: 'PUT',
      data: updateData
    });
    
    return json(createBFFResponse(updatedProfile));
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
    }
    
    if (error.code === 404 || error.code === 'NOT_FOUND') {
      return json(createBFFError('NOT_FOUND', '用戶不存在'), { status: 404 });
    }
    
    if (error.code === 400 || error.code === 'BAD_REQUEST') {
      return json(createBFFError('BAD_REQUEST', '請求資料無效', error.details), { status: 400 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '更新用戶資料失敗', error.details),
      { status: 500 }
    );
  }
}, 'auth_profile_put');

// 刪除用戶帳號
export const DELETE: RequestHandler = withPerformanceTracking(async ({ cookies, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端
    const result = await bffBackendClient.request('/api/auth/profile', {
      method: 'DELETE'
    });
    
    return json(createBFFResponse(result));
    
  } catch (error: any) {
    
    if (error.code === 401 || error.code === 'UNAUTHORIZED') {
      return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
    }
    
    if (error.code === 404 || error.code === 'NOT_FOUND') {
      return json(createBFFError('NOT_FOUND', '用戶不存在'), { status: 404 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', '刪除用戶帳號失敗', error.details),
      { status: 500 }
    );
  }
}, 'auth_profile_delete');