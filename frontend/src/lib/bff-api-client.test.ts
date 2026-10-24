// 前端 BFF API 客戶端：請求格式、錯誤回應與登入失效
import { beforeEach, describe, expect, it, vi, type Mock } from 'vitest';
import { apiClient } from '$lib/api/client';
import { BFFApiClient, isErrorResponse, isSuccessResponse } from './bff-api-client';

let fetchMock: Mock<typeof fetch>;
let onAuthFailure: Mock<() => void>;
const client = new BFFApiClient();

function respond(status: number, body: unknown, statusText = '') {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  fetchMock.mockImplementation(async () => new Response(text, { status, statusText }));
}

const lastCall = () => fetchMock.mock.calls.at(-1)!;
const lastInit = () => lastCall()[1]!;

beforeEach(() => {
  fetchMock = vi.fn<typeof fetch>();
  vi.stubGlobal('fetch', fetchMock);
  onAuthFailure = vi.fn();
  apiClient.onAuthFailure = onAuthFailure;
  return () => {
    apiClient.onAuthFailure = null;
  };
});

describe('JSON 請求', () => {
  it('GET 帶 JSON Content-Type，回傳 BFF 信封', async () => {
    respond(200, { success: true, data: { stats: { totalRooms: 1 } } });

    const response = await client.dashboard.get();

    expect(lastCall()[0]).toBe('/api/dashboard');
    expect(lastInit().headers).toEqual({ 'Content-Type': 'application/json' });
    expect(isSuccessResponse(response) && response.data).toEqual({ stats: { totalRooms: 1 } });
  });

  it('POST 以 JSON 送出內容', async () => {
    respond(200, { success: true, data: { success: true, message: '成功加入聊天室' } });

    await client.rooms.joinAdvanced('r1', { password: 'pw' });
    expect(lastCall()[0]).toBe('/api/rooms/r1/join-advanced');
    expect(lastInit()).toMatchObject({ method: 'POST', body: JSON.stringify({ password: 'pw' }) });

    await client.invitations.validate('abc');
    expect(lastCall()[0]).toBe('/api/invitations/validate');
    expect(lastInit()).toMatchObject({ method: 'POST', body: JSON.stringify({ inviteCode: 'abc' }) });

    await client.rooms.checkJoinRequirements('r1');
    expect(lastCall()[0]).toBe('/api/rooms/r1/join-advanced');
    expect(lastInit().method).toBeUndefined();
  });

  it('錯誤回應是 BFF 信封時原樣回傳', async () => {
    const error = { success: false, error: { code: 'FORBIDDEN', message: '只有房主可以操作' } };
    respond(403, error);

    const response = await client.dashboard.get();

    expect(response).toEqual(error);
    expect(isErrorResponse(response) && response.error.message).toBe('只有房主可以操作');
  });

  it('錯誤回應不是 JSON 時轉成 HTTP_ERROR', async () => {
    respond(502, '<html>Bad Gateway</html>', 'Bad Gateway');

    expect(await client.dashboard.get()).toEqual({
      success: false,
      error: { code: 'HTTP_ERROR', message: 'HTTP 502: Bad Gateway' },
    });
  });

  it('網路錯誤直接丟出，由呼叫端處理', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(client.dashboard.get()).rejects.toThrow('Failed to fetch');
  });
});

describe('檔案上傳', () => {
  const file = new File(['png'], 'photo.png', { type: 'image/png' });

  it('以 multipart 送出檔案、類型與說明，不帶 JSON Content-Type', async () => {
    respond(200, { success: true, data: { file: { url: '/uploads/photo.png' } } });

    await client.files.upload(file, 'image', '頭像');

    const [url, init] = lastCall();
    expect(url).toBe('/api/files');
    expect(init!.method).toBe('POST');
    expect(init!.headers).toBeUndefined();
    const form = init!.body as FormData;
    expect((form.get('file') as File).name).toBe('photo.png');
    expect(form.get('type')).toBe('image');
    expect(form.get('description')).toBe('頭像');
  });

  it('沒有說明時不送 description', async () => {
    respond(200, { success: true, data: {} });

    await client.files.upload(file);

    const form = lastInit().body as FormData;
    expect(form.get('type')).toBe('general');
    expect(form.has('description')).toBe(false);
  });

  it('錯誤回應不是 JSON 時轉成 HTTP_ERROR', async () => {
    respond(413, 'too large', 'Payload Too Large');

    expect(await client.files.upload(file)).toEqual({
      success: false,
      error: { code: 'HTTP_ERROR', message: 'HTTP 413: Payload Too Large' },
    });
  });
});

// 與 apiClient 相同：BFF 的透明 refresh 也失敗時回 401 UNAUTHORIZED，表示登入已失效
describe('登入失效', () => {
  const unauthorized = { success: false, error: { code: 'UNAUTHORIZED', message: '認證已過期' } };

  it('JSON 請求收到 401 UNAUTHORIZED 時通知 apiClient 導回登入頁', async () => {
    respond(401, unauthorized);

    expect(await client.dashboard.get()).toEqual(unauthorized);
    expect(onAuthFailure).toHaveBeenCalledOnce();
  });

  it('上傳收到 401 UNAUTHORIZED 時同樣導回登入頁', async () => {
    respond(401, unauthorized);

    await client.files.upload(new File(['x'], 'a.txt'));

    expect(onAuthFailure).toHaveBeenCalledOnce();
  });

  it('其他錯誤不視為登入失效', async () => {
    respond(403, { success: false, error: { code: 'FORBIDDEN', message: '沒有權限' } });
    await client.dashboard.get();

    respond(401, { success: false, error: { code: 'AUTH_ERROR', message: '帳號或密碼錯誤' } });
    await client.dashboard.get();

    expect(onAuthFailure).not.toHaveBeenCalled();
  });
});

describe('回應型別判斷', () => {
  it('成功須有 data，失敗須有 error', () => {
    expect(isSuccessResponse({ success: true, data: null })).toBe(true);
    expect(isSuccessResponse({ success: true })).toBe(false);
    expect(isErrorResponse({ success: false, error: { code: 'X', message: 'x' } })).toBe(true);
    expect(isErrorResponse({ success: false })).toBe(false);
  });
});
