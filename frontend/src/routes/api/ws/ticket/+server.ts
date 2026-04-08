import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, createBFFError } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

// 產生一次性 WebSocket 連線 ticket
export const POST: RequestHandler = async ({ request, cookies }) => {
	try {
		const { room_id } = await request.json();

		if (!room_id) {
			return json(createBFFError('VALIDATION_ERROR', 'room_id 不能為空'), { status: 400 });
		}

		const result = await bffAuthRequest<{ ticket: string }>(cookies, '/api/ws/ticket', {
			method: 'POST',
			data: { room_id }
		});

		return json(createBFFResponse(result));
	} catch (error: any) {
		if (error.code === 401) {
			return json(createBFFError('UNAUTHORIZED', 'Not authenticated'), { status: 401 });
		}
		return json(createBFFError('INTERNAL_ERROR', '取得 WebSocket ticket 失敗'), {
			status: 500
		});
	}
};
