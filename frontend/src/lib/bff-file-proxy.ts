import { error, json, type Cookies } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { isTokenExpired, createBFFError } from '$lib/bff-utils';
import { tryRefreshIfNeeded } from '$lib/bff-auth';

/**
 * 以使用者 token 向後端取檔並串流回傳（需認證）
 *
 * 二進位回應不能走 bffAuthRequest（它解析 JSON 信封），但仍需透明 refresh。
 * backendPath 由呼叫端負責 encodeURIComponent 各個片段。
 */
export async function proxyBackendFile(
  cookies: Cookies,
  backendPath: string,
  cacheControl: string
): Promise<Response> {
  let token = cookies.get('auth_token');
  if (!token || isTokenExpired(token)) {
    token = (await tryRefreshIfNeeded(cookies)) ?? undefined;
    if (!token) {
      return json(createBFFError('UNAUTHORIZED', '請先登入'), { status: 401 });
    }
  }

  const backendURL = env['BACKEND_URL'] || 'http://localhost:8000';

  const response = await fetch(`${backendURL}${backendPath}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    response.body?.cancel();
    if (response.status === 401) {
      return json(createBFFError('UNAUTHORIZED', '認證已過期'), { status: 401 });
    }
    error(response.status, response.status === 404 ? '檔案不存在' : '檔案下載失敗');
  }

  const headers: Record<string, string> = {
    'Content-Type': response.headers.get('Content-Type') || 'application/octet-stream',
    'Cache-Control': cacheControl,
  };
  const contentLength = response.headers.get('Content-Length');
  if (contentLength) headers['Content-Length'] = contentLength;
  const disposition = response.headers.get('Content-Disposition');
  if (disposition) headers['Content-Disposition'] = disposition;

  return new Response(response.body, { headers });
}
