import type { RequestHandler } from '@sveltejs/kit';
import { proxyBackendFile } from '$lib/bff-file-proxy';

// 縮圖代理 — 圖片上傳回應的 thumbnails 指向此路徑（需認證）
// 靜態片段 thumbnail 比 [fileType]/[filename] 優先匹配；size 由後端驗證
export const GET: RequestHandler = async ({ params, cookies, url }) => {
  const size = url.searchParams.get('size') ?? 'medium';

  return proxyBackendFile(
    cookies,
    `/api/files/thumbnail/${encodeURIComponent(params.filename!)}?size=${encodeURIComponent(size)}`,
    'private, max-age=86400'
  );
};
