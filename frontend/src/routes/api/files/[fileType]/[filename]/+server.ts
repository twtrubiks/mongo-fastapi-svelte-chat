import { error, type RequestHandler } from '@sveltejs/kit';
import { proxyBackendFile } from '$lib/bff-file-proxy';

import { FILE_TYPE_CONFIGS } from '$lib/utils';

const ALLOWED_FILE_TYPES = new Set(Object.keys(FILE_TYPE_CONFIGS));

// 檔案下載代理 — 將請求轉發到後端 FastAPI（需認證）
export const GET: RequestHandler = async ({ params, cookies }) => {
  const { fileType, filename } = params;

  if (!ALLOWED_FILE_TYPES.has(fileType!)) {
    error(400, '無效的檔案類型');
  }

  return proxyBackendFile(
    cookies,
    `/api/files/${encodeURIComponent(fileType!)}/${encodeURIComponent(filename!)}`,
    fileType === 'image' ? 'private, max-age=86400' : 'no-cache'
  );
};
