import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 獲取用戶詳細資料
export const GET: RequestHandler = async ({ cookies }) => {
  try {
    const profile = await bffAuthRequest(cookies, '/api/auth/profile');
    return json(createBFFResponse(profile));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取用戶詳細資料失敗');
  }
};

// 更新用戶資料
export const PUT: RequestHandler = async ({ cookies, request }) => {
  try {
    const updateData = await request.json();
    const updatedProfile = await bffAuthRequest(cookies, '/api/auth/profile', {
      method: 'PUT',
      data: updateData,
    });
    return json(createBFFResponse(updatedProfile));
  } catch (error: any) {
    return toBffErrorResponse(error, '更新用戶資料失敗');
  }
};
