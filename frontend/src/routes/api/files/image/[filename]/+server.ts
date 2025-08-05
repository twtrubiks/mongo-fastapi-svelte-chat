import type { RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import { getAuthToken, isTokenExpired } from '$lib/bff-utils';

// 代理圖片文件請求
export const GET: RequestHandler = async ({ cookies, params, request }) => {
  const { filename } = params;
  
  // 獲取認證令牌
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證（可選，根據需要決定是否需要認證才能訪問圖片）
  if (!token || isTokenExpired(token)) {
    return new Response('Unauthorized', { status: 401 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 從後端獲取圖片
    const response = await bffBackendClient.requestRaw(`/api/files/image/${filename}`, {
      method: 'GET',
      responseType: 'arraybuffer' // 獲取二進制數據
    });
    
    // 複製響應頭
    const headers = new Headers();
    if (response.headers['content-type']) {
      headers.set('Content-Type', response.headers['content-type']);
    }
    if (response.headers['content-length']) {
      headers.set('Content-Length', response.headers['content-length']);
    }
    // 設置緩存控制
    headers.set('Cache-Control', 'public, max-age=3600'); // 緩存1小時
    
    // 返回圖片數據
    return new Response(response.data, {
      status: 200,
      headers
    });
    
  } catch (error: any) {
    console.error(`圖片代理錯誤 [${filename}]:`, error);
    
    if (error.code === 404) {
      return new Response('Not Found', { status: 404 });
    }
    
    if (error.code === 403) {
      return new Response('Forbidden', { status: 403 });
    }
    
    return new Response('Internal Server Error', { status: 500 });
  }
};