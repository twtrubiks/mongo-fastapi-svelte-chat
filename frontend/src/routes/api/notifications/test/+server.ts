import type { RequestHandler } from './$types';
import { json } from '@sveltejs/kit';
import { bffBackendClient } from '$lib/bff-client';

export const POST: RequestHandler = async ({ cookies }) => {
	const authCookie = cookies.get('auth_token');
	
	if (!authCookie) {
		return json({ error: '未授權' }, { status: 401 });
	}

	try {
		// 設置認證
		bffBackendClient.setAuth(authCookie);
		
		// 發送測試通知請求到後端
		const response = await bffBackendClient.request('/api/notifications/test', {
			method: 'POST'
		});
		
		return json({
			success: true,
			data: response
		});
	} catch (error: any) {
		console.error('創建測試通知錯誤:', error);
		
		// 處理錯誤
		if (error.response?.data) {
			return json({ 
				error: error.response.data.detail || '創建測試通知失敗' 
			}, { 
				status: error.response.status || 500 
			});
		}
		
		return json({ 
			error: error.message || '創建測試通知失敗' 
		}, { 
			status: 500 
		});
	}
};