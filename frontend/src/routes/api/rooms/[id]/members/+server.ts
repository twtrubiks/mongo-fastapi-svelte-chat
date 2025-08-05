import { json, type RequestHandler } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';
import {
  createBFFResponse,
  createBFFError,
  getAuthToken,
  isTokenExpired,
  withPerformanceTracking
} from '$lib/bff-utils';

// 獲取房間成員列表
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
    const limit = url.searchParams.get('limit') || '100';
    const offset = url.searchParams.get('offset') || '0';
    const status = url.searchParams.get('status'); // online, offline, all
    
    queryParams.append('limit', limit);
    queryParams.append('offset', offset);
    if (status) queryParams.append('status', status);
    
    // 轉發到後端房間成員 API
    const members = await bffBackendClient.request(`/api/rooms/${roomId}/members?${queryParams.toString()}`, {
      method: 'GET'
    }) as Array<{
      user_id: string;
      username: string;
      full_name?: string;
      email?: string;
      avatar?: string;
      role: 'owner' | 'admin' | 'member';
      joined_at: string;
      last_seen?: string;
      is_online?: boolean;
      status?: 'active' | 'inactive' | 'banned';
    }>;
    
    return json(createBFFResponse(members));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}/members] 錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '獲取房間成員失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限查看此房間的成員';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    }
    
    return json(
      createBFFError('MEMBERS_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});

// 添加房間成員
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
    const memberData = await request.json();
    
    // 基本驗證
    if (!memberData.user_id && !memberData.username && !memberData.email) {
      return json(
        createBFFError('VALIDATION_ERROR', '必須提供用戶 ID、用戶名或郵箱'),
        { status: 400 }
      );
    }
    
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端添加成員 API
    const newMember = await bffBackendClient.request(`/api/rooms/${roomId}/members`, {
      method: 'POST',
      data: {
        user_id: memberData.user_id,
        username: memberData.username,
        email: memberData.email,
        role: memberData.role || 'member'
      },
      headers: {
        'Content-Type': 'application/json'
      }
    }) as {
      user_id: string;
      username: string;
      role: string;
      joined_at: string;
    };
    
    return json(createBFFResponse(newMember));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}/members] 添加錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '添加成員失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間或用戶不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限添加成員到此房間';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    } else if (error.response?.status === 409) {
      statusCode = 409;
      errorMessage = '用戶已經是房間成員';
    } else if (error.response?.status === 422) {
      statusCode = 422;
      errorMessage = error.response.data?.detail || '資料驗證失敗';
    }
    
    return json(
      createBFFError('MEMBER_ADD_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});

// 更新成員角色或狀態
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
    if (!updateData.user_id) {
      return json(
        createBFFError('VALIDATION_ERROR', '用戶 ID 不能為空'),
        { status: 400 }
      );
    }
    
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端更新成員 API
    const updatedMember = await bffBackendClient.request(`/api/rooms/${roomId}/members/${updateData.user_id}`, {
      method: 'PUT',
      data: {
        role: updateData.role,
        status: updateData.status
      },
      headers: {
        'Content-Type': 'application/json'
      }
    }) as {
      user_id: string;
      username: string;
      role: string;
      status: string;
      updated_at: string;
    };
    
    return json(createBFFResponse(updatedMember));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}/members] 更新錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '更新成員失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間或成員不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限修改此成員';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    } else if (error.response?.status === 422) {
      statusCode = 422;
      errorMessage = error.response.data?.detail || '資料驗證失敗';
    }
    
    return json(
      createBFFError('MEMBER_UPDATE_ERROR', errorMessage, {
        roomId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});

// 移除房間成員
export const DELETE: RequestHandler = withPerformanceTracking(async ({ cookies, params, url, request }) => {
  const token = getAuthToken(cookies, request.headers);
  
  // 檢查認證
  if (!token || isTokenExpired(token)) {
    return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
  }
  
  const roomId = params.id;
  if (!roomId) {
    return json(createBFFError('VALIDATION_ERROR', '房間 ID 不能為空'), { status: 400 });
  }
  
  const userId = url.searchParams.get('user_id');
  if (!userId) {
    return json(createBFFError('VALIDATION_ERROR', '用戶 ID 不能為空'), { status: 400 });
  }
  
  try {
    // 設置後端客戶端認證
    bffBackendClient.setAuth(token);
    
    // 轉發到後端移除成員 API
    await bffBackendClient.request(`/api/rooms/${roomId}/members/${userId}`, {
      method: 'DELETE'
    });
    
    return json(createBFFResponse({ 
      success: true, 
      message: '成員已移除',
      roomId,
      userId 
    }));
    
  } catch (error: any) {
    console.error(`[/api/rooms/${roomId}/members] 移除錯誤:`, error);
    
    // 根據錯誤類型返回適當的狀態碼
    let statusCode = 500;
    let errorMessage = '移除成員失敗';
    
    if (error.response?.status === 404) {
      statusCode = 404;
      errorMessage = '房間或成員不存在';
    } else if (error.response?.status === 403) {
      statusCode = 403;
      errorMessage = '無權限移除此成員';
    } else if (error.response?.status === 401) {
      statusCode = 401;
      errorMessage = '認證已失效，請重新登入';
    }
    
    return json(
      createBFFError('MEMBER_REMOVE_ERROR', errorMessage, {
        roomId,
        userId,
        serverMessage: error.message,
        bffError: true
      }),
      { status: statusCode }
    );
  }
});