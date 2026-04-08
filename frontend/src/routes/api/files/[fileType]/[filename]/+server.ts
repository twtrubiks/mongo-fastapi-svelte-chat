import { error, json, type RequestHandler } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { isTokenExpired, createBFFError } from '$lib/bff-utils';
import { tryRefreshIfNeeded } from '$lib/bff-auth';

import { FILE_TYPE_CONFIGS } from '$lib/utils';

const ALLOWED_FILE_TYPES = new Set(Object.keys(FILE_TYPE_CONFIGS));

// 檔案下載代理 — 將請求轉發到後端 FastAPI（需認證）
export const GET: RequestHandler = async ({ params, cookies }) => {
  const { fileType, filename } = params;

  if (!ALLOWED_FILE_TYPES.has(fileType!)) {
    error(400, '無效的檔案類型');
  }

  // 認證：與 upload route 同模式
  let token = cookies.get('auth_token');
  if (!token || isTokenExpired(token)) {
    token = (await tryRefreshIfNeeded(cookies)) ?? undefined;
    if (!token) {
      return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
    }
  }

  const backendURL = env['BACKEND_URL'] || 'http://localhost:8000';

  const response = await fetch(
    `${backendURL}/api/files/${encodeURIComponent(fileType!)}/${encodeURIComponent(filename!)}`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    response.body?.cancel();
    if (response.status === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    error(response.status, response.status === 404 ? '檔案不存在' : '檔案下載失敗');
  }

  const headers: Record<string, string> = {
    'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
    'Cache-Control': fileType === 'image' ? 'private, max-age=86400' : 'no-cache',
  };
  const contentLength = response.headers.get('Content-Length');
  if (contentLength) headers['Content-Length'] = contentLength;
  const disposition = response.headers.get('Content-Disposition');
  if (disposition) headers['Content-Disposition'] = disposition;

  return new Response(response.body, { headers });
};
