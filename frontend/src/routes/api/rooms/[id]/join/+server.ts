import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { bffBackendClient } from '$lib/bff-client';

export const POST: RequestHandler = async ({ params, request, cookies }) => {
    try {
        const roomId = params.id;
        
        // 讀取請求 body（如果有的話）
        let joinRequest = {};
        try {
            const body = await request.text();
            if (body) {
                joinRequest = JSON.parse(body);
            }
        } catch (e) {
            // 忽略 JSON 解析錯誤，使用空對象
        }

        const result = await bffBackendClient.request(
            `/api/rooms/${roomId}/join`,
            {
                method: 'POST',
                requireAuth: true,
                cookies,
                data: joinRequest
            }
        );

        return json(result.data, { status: result.status });
    } catch (error) {
        return bffBackendClient.handleError(error);
    }
};