/**
 * BFF 認證請求模組（server-only）
 *
 * 所有受保護的 BFF routes 應使用 bffAuthRequest 取代手動 getAuthToken + bffBackendClient。
 * 此函數自動處理：
 * 1. 從 httpOnly cookie 讀取 token
 * 2. Token 過期時透明 refresh
 * 3. 後端回 401 時自動 refresh + 重試
 */

import type { Cookies } from '@sveltejs/kit';
import { bffBackendClient } from './bff-client';
import { setAuthCookies, clearAuthCookies } from './bff-cookie';
import { isTokenExpired } from './bff-utils';

// 防止並行請求同時觸發多次 refresh（例如 dashboard Promise.all）
let refreshing: Promise<string | null> | null = null;

/**
 * 嘗試用 refresh_token 換發新的 access_token
 *
 * 內建 promise 去重：並行呼叫只會發出一次 refresh 請求。
 *
 * @returns 新的 access_token，失敗則回傳 null 並清除 cookies
 */
async function tryRefreshToken(cookies: Cookies): Promise<string | null> {
	if (refreshing) return refreshing;

	refreshing = doRefresh(cookies);
	try {
		return await refreshing;
	} finally {
		refreshing = null;
	}
}

async function doRefresh(cookies: Cookies): Promise<string | null> {
	const refreshToken = cookies.get('refresh_token');
	if (!refreshToken) return null;

	try {
		const result = await bffBackendClient.request<{
			access_token: string;
			refresh_token: string;
			token_type: string;
		}>('/api/auth/refresh', {
			method: 'POST',
			data: { refresh_token: refreshToken }
		});

		setAuthCookies(cookies, result.access_token, result.refresh_token);
		return result.access_token;
	} catch {
		clearAuthCookies(cookies);
		return null;
	}
}

/**
 * 供 multipart 等無法走 bffAuthRequest 的路由使用：
 * 當 token 不存在或已過期時嘗試 refresh，回傳新 token 或 null。
 */
export async function tryRefreshIfNeeded(cookies: Cookies): Promise<string | null> {
	return tryRefreshToken(cookies);
}

/**
 * 帶透明 token refresh 的 BFF 後端請求
 *
 * @throws {{ code: number; message: string }} 認證失敗或其他錯誤
 */
export async function bffAuthRequest<T>(
	cookies: Cookies,
	endpoint: string,
	options: {
		method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
		data?: any;
		headers?: Record<string, string>;
	} = {}
): Promise<T> {
	let token = cookies.get('auth_token');

	if (!token || isTokenExpired(token)) {
		token = (await tryRefreshToken(cookies)) ?? undefined;
		if (!token) {
			throw { code: 401, message: 'Not authenticated' };
		}
	}

	try {
		return await bffBackendClient.request<T>(endpoint, { ...options, token });
	} catch (error: any) {
		if (error.code === 401) {
			const newToken = await tryRefreshToken(cookies);
			if (!newToken) throw error;
			return await bffBackendClient.request<T>(endpoint, { ...options, token: newToken });
		}
		throw error;
	}
}
