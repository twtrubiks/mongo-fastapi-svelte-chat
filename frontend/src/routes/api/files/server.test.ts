// 檔案上傳 / 下載 BFF 路由
import { describe, expect, it, vi } from 'vitest';
import * as upload from './+server';
import * as download from './[fileType]/[filename]/+server';
import { backendError, FakeCookies, makeEvent, mockBackend, tokenExpiringIn } from '../../../tests/bff';

const UPLOADED = { id: 'f1', filename: 'abc.png', url: '/api/files/image/abc.png' };

function file(name: string, type: string, size = 4) {
  return new File([new Uint8Array(size)], name, { type });
}

function uploadEvent(fields: Record<string, string | File>, cookies = new FakeCookies({ auth_token: tokenExpiringIn(3600) })) {
  const form = new FormData();
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  const request = new Request('http://localhost/api/files', { method: 'POST', body: form });
  return makeEvent({ cookies, request });
}

async function body(response: Response) {
  return { status: response.status, ...(await response.json()) };
}

describe('POST /api/files', () => {
  it('圖片上傳到 /upload/image，帶 token 並補上檔案資訊', async () => {
    const backend = mockBackend({ 'POST /api/files/upload/image': () => ({ file: UPLOADED, message: '上傳成功' }) });

    const result = await body(await upload.POST(uploadEvent({ file: file('cat.png', 'image/png'), type: 'image' })));

    expect(result.data).toEqual({
      message: '上傳成功',
      file: { ...UPLOADED, uploadedAt: expect.any(String), uploadType: 'image', size: 4, originalName: 'cat.png' },
    });
    const options = backend.mock.calls[0]![1]!;
    expect(options.token).toBeTruthy();
    expect(options.data).toBeInstanceOf(FormData);
    expect(((options.data as FormData).get('file') as File).name).toBe('cat.png');
  });

  it('非圖片上傳到 /upload 並轉送描述', async () => {
    const backend = mockBackend({ 'POST /api/files/upload': () => ({ file: UPLOADED }) });

    await upload.POST(uploadEvent({ file: file('a.pdf', 'application/pdf'), type: 'document', description: '報告' }));

    expect((backend.mock.calls[0]![1]!.data as FormData).get('description')).toBe('報告');
  });

  // 前端以 FILE_TYPE_CONFIGS 判斷類型（與後端白名單一致），BFF 不能另外擋掉
  it.each([
    ['image', 'scan.bmp', 'image/bmp', '/api/files/upload/image'],
    ['video', 'clip.mov', 'video/quicktime', '/api/files/upload'],
    ['video', 'movie.mkv', 'video/x-matroska', '/api/files/upload'],
    ['document', 'notes.md', '', '/api/files/upload'],
    ['audio', 'voice.m4a', 'audio/mp4', '/api/files/upload'],
    ['audio', 'song.flac', 'audio/flac', '/api/files/upload'],
  ])('前端與後端都接受的 %s（%s）可以上傳', async (type, name, mime, endpoint) => {
    const backend = mockBackend({ [`POST ${endpoint}`]: () => ({ file: UPLOADED }) });

    const result = await body(await upload.POST(uploadEvent({ file: file(name, mime), type })));

    expect(result.status).toBe(200);
    expect(backend).toHaveBeenCalledOnce();
  });

  it.each([
    ['副檔名與類型不符', { file: file('a.pdf', 'application/pdf'), type: 'image' }],
    ['超過該類型大小上限', { file: file('big.png', 'image/png', 10 * 1024 * 1024 + 1), type: 'image' }],
    ['未知類型超過 5MB', { file: file('x.bin', '', 5 * 1024 * 1024 + 1) }],
    ['可執行檔', { file: file('setup.exe', 'application/octet-stream') }],
    ['沒有檔案', { type: 'image' }],
  ])('%s時回 400 且不呼叫後端', async (_, fields) => {
    const backend = mockBackend({});

    const result = await body(await upload.POST(uploadEvent(fields)));

    expect(result).toMatchObject({ status: 400, error: { code: 'VALIDATION_ERROR' } });
    expect(backend).not.toHaveBeenCalled();
  });

  it('不是 multipart 時回 400', async () => {
    const request = new Request('http://localhost/api/files', { method: 'POST', body: '{}', headers: { 'Content-Type': 'application/json' } });

    const response = await upload.POST(makeEvent({ cookies: new FakeCookies({ auth_token: tokenExpiringIn(3600) }), request }));

    expect(response.status).toBe(400);
  });

  it('token 過期時先換發再上傳', async () => {
    const backend = mockBackend({
      'POST /api/auth/refresh': () => ({ access_token: 'new-access', refresh_token: 'r2', token_type: 'bearer' }),
      'POST /api/files/upload/image': () => ({ file: UPLOADED }),
    });
    const cookies = new FakeCookies({ auth_token: tokenExpiringIn(-1), refresh_token: 'r1' });

    await upload.POST(uploadEvent({ file: file('cat.png', 'image/png'), type: 'image' }, cookies));

    expect(backend.mock.calls[1]![1]!.token).toBe('new-access');
  });

  it('未登入時回 401', async () => {
    const response = await upload.POST(uploadEvent({ file: file('cat.png', 'image/png') }, new FakeCookies()));

    expect(response.status).toBe(401);
  });

  it.each([
    [413, '檔案大小超過限制'],
    [415, '不支援的檔案類型'],
    [400, '檔案內容與副檔名不符'],
  ])('後端 %i 時回傳「%s」', async (code, message) => {
    mockBackend({
      'POST /api/files/upload/image': () => {
        throw backendError(code, code === 400 ? message : 'x');
      },
    });

    const result = await body(await upload.POST(uploadEvent({ file: file('cat.png', 'image/png'), type: 'image' })));

    expect(result).toMatchObject({ status: code, error: { message } });
  });
});

describe('GET /api/files/[fileType]/[filename]', () => {
  function get(fileType: string, filename: string, cookies = new FakeCookies({ auth_token: tokenExpiringIn(3600) })) {
    return download.GET(makeEvent({ cookies, params: { fileType, filename } }));
  }

  function stubBackend(response: Response) {
    const fetchMock = vi.fn(async () => response);
    vi.stubGlobal('fetch', fetchMock);
    return fetchMock;
  }

  it('以 token 向後端取檔並串流回傳', async () => {
    const fetchMock = stubBackend(
      new Response('PNGDATA', {
        headers: { 'Content-Type': 'image/png', 'Content-Length': '7', 'Content-Disposition': 'inline; filename="a b.png"' },
      })
    );

    const response = await get('image', 'a b.png');

    expect(await response.text()).toBe('PNGDATA');
    expect(Object.fromEntries(response.headers)).toMatchObject({
      'content-type': 'image/png',
      'content-length': '7',
      'content-disposition': 'inline; filename="a b.png"',
      'cache-control': 'private, max-age=86400',
    });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('http://localhost:8000/api/files/image/a%20b.png');
    expect((init.headers as Record<string, string>)['Authorization']).toMatch(/^Bearer /);
  });

  it('非圖片不快取', async () => {
    stubBackend(new Response('PDF', { headers: { 'Content-Type': 'application/pdf' } }));

    expect((await get('document', 'a.pdf')).headers.get('cache-control')).toBe('no-cache');
  });

  it('不在白名單的類型回 400，不呼叫後端', async () => {
    const fetchMock = stubBackend(new Response(''));

    await expect(get('../etc', 'passwd')).rejects.toMatchObject({ status: 400 });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('後端 404 轉成 404', async () => {
    stubBackend(new Response('{}', { status: 404 }));

    await expect(get('image', 'missing.png')).rejects.toMatchObject({ status: 404, body: { message: '檔案不存在' } });
  });

  it('後端 401 回 BFF 錯誤', async () => {
    stubBackend(new Response('{}', { status: 401 }));

    expect((await get('image', 'a.png')).status).toBe(401);
  });

  it('未登入時回 401，不呼叫後端', async () => {
    const fetchMock = stubBackend(new Response(''));

    expect((await get('image', 'a.png', new FakeCookies())).status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
