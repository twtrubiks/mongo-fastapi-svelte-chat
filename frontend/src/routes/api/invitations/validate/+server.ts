import { json, type RequestHandler } from '@sveltejs/kit';
import { BFFBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError
} from '$lib/bff-utils';

// 處理 OPTIONS 請求 (CORS preflight)
export const OPTIONS: RequestHandler = async () => {
  return new Response(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
};

// 驗證邀請碼 - 不需要認證
export const POST: RequestHandler = async ({ request }) => {
  try {
    const body = await request.json();
    
    const { inviteCode } = body;
    
    if (!inviteCode) {
      return json(createBFFError('VALIDATION_ERROR', '邀請碼不能為空'), { status: 400 });
    }
    
// 真實邀請碼驗證流程
    
    let backendClient;
    try {
      backendClient = new BFFBackendClient();
    } catch (clientError) {
      return json(createBFFError('BACKEND_ERROR', '無法創建後端客戶端'), { status: 500 });
    }
    
    // 檢查後端連接 - 使用動態 URL
    const backendUrl = backendClient['client'].defaults.baseURL;
    try {
      const testResponse = await fetch(`${backendUrl}/docs`);
      
      if (!testResponse.ok) {
        return json(createBFFError('BACKEND_UNAVAILABLE', '後端服務不可用'), { status: 503 });
      }
    } catch (connectionError) {
      return json(createBFFError('BACKEND_UNAVAILABLE', '無法連接到後端服務'), { status: 503 });
    }
    
    const result = await backendClient.request('/api/invitations/validate', {
      method: 'POST',
      data: { invite_code: inviteCode }
    });
    
    // 後端回應格式：{ valid: true, room_id: "xxx", room_name: "xxx", inviter_name: "xxx" }
    // 前端期望格式：{ valid: true, room: { id: "xxx", name: "xxx", ... } }
    
    if (result && result.valid) {
      return json(createBFFResponse({
        valid: true,
        room: {
          id: result.room_id,
          name: result.room_name,
          inviter_name: result.inviter_name
        }
      }));
    } else {
      return json(createBFFError('INVALID_INVITE', '邀請碼無效或已過期'), { status: 400 });
    }
    
  } catch (error: any) {
    
    // 檢查是否是網路錯誤
    if (error.code === 'ECONNREFUSED' || error.message?.includes('ECONNREFUSED')) {
      return json(createBFFError('BACKEND_UNAVAILABLE', '後端服務不可用'), { status: 503 });
    }
    
    // 檢查 BFFBackendClient 包裝的錯誤
    if (error.code) {
      
      // 對於後端錯誤，都轉換為友好的邀請碼無效錯誤
      if (error.code === 400 || error.code === 404 || error.code === 500) {
        return json(createBFFError('INVALID_INVITE', error.message || '邀請碼無效或已過期'), { status: 400 });
      }
      
      return json(createBFFError('BACKEND_ERROR', error.message || '後端處理錯誤'), { status: 500 });
    }
    
    // 檢查是否是標準 axios 錯誤
    if (error.response) {
      const status = error.response.status;
      const data = error.response.data;
      
      if (status === 400 || status === 404 || status === 500) {
        return json(createBFFError('INVALID_INVITE', data.detail || '邀請碼無效或已過期'), { status: 400 });
      }
      
      return json(createBFFError('BACKEND_ERROR', data.detail || '後端處理錯誤'), { status: status });
    }
    
    if (error.message?.includes('邀請碼無效') || error.message?.includes('已過期')) {
      return json(createBFFError('INVALID_INVITE', error.message), { status: 400 });
    }
    
    return json(
      createBFFError('INTERNAL_ERROR', error.message || '驗證邀請碼失敗'),
      { status: 500 }
    );
  }
};