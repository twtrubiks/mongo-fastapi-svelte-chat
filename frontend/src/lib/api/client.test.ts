import { createServer, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient } from './client';

// 以真實 HTTP server 扮演 BFF：回應由各測試設定，並記錄收到的請求
let server: Server;
let baseURL: string;
let reply: { status: number; body: unknown } = { status: 200, body: {} };
let received: { method?: string | undefined; url?: string | undefined; body: string; contentType?: string | undefined }[] = [];

beforeAll(async () => {
  server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => {
      received.push({ method: req.method, url: req.url, body, contentType: req.headers['content-type'] });
      res.writeHead(reply.status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(reply.body));
    });
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  baseURL = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

beforeEach(() => {
  reply = { status: 200, body: {} };
  received = [];
});

function bffOk(data: unknown) {
  return { success: true, data, meta: { timestamp: 't', requestId: 'req-1' } };
}

function bffError(code: string, message: string) {
  return { success: false, error: { code, message } };
}

describe('ApiClient 回應攔截器', () => {
  it('解開 BFF 信封，只回傳 data', async () => {
    reply = { status: 200, body: bffOk({ id: 'r1', name: '大廳' }) };

    expect(await new ApiClient(baseURL).rooms.get('r1')).toEqual({ id: 'r1', name: '大廳' });
  });

  it('非 BFF 格式（通知列表）原樣回傳', async () => {
    reply = { status: 200, body: { notifications: [], unread_count: 0 } };

    expect(await new ApiClient(baseURL).notifications.list()).toEqual({ notifications: [], unread_count: 0 });
  });

  it('BFF 錯誤轉成帶 code 的 BFFError', async () => {
    reply = { status: 403, body: bffError('ROOM_DELETE_ERROR', '只有房主可以刪除房間') };

    await expect(new ApiClient(baseURL).rooms.delete('r1')).rejects.toMatchObject({
      name: 'BFFError',
      code: 'ROOM_DELETE_ERROR',
      message: '只有房主可以刪除房間',
    });
  });

  it('HTTP 200 但 success 為 false 也視為錯誤', async () => {
    reply = { status: 200, body: bffError('X', '失敗') };

    await expect(new ApiClient(baseURL).rooms.get('r1')).rejects.toMatchObject({ code: 'X', message: '失敗' });
  });

  it.each([
    ['BFF 格式', bffError('UNAUTHORIZED', '認證已過期')],
    ['非 BFF 格式', { detail: 'Not authenticated' }],
  ])('401（%s）表示 BFF 換發也失敗，通知登出', async (_, body) => {
    reply = { status: 401, body };
    const client = new ApiClient(baseURL);
    const onAuthFailure = vi.fn();
    client.onAuthFailure = onAuthFailure;

    await expect(client.rooms.myRooms()).rejects.toBeTruthy();
    expect(onAuthFailure).toHaveBeenCalledOnce();
  });

  it('帳密錯誤的 401 不算登入失效', async () => {
    reply = { status: 401, body: bffError('AUTH_ERROR', '用戶名或密碼錯誤') };
    const client = new ApiClient(baseURL);
    const onAuthFailure = vi.fn();
    client.onAuthFailure = onAuthFailure;

    await expect(client.auth.login({ username: 'alice', password: 'x' })).rejects.toMatchObject({
      message: '用戶名或密碼錯誤',
    });
    expect(onAuthFailure).not.toHaveBeenCalled();
  });

  it('其他錯誤不通知登出', async () => {
    reply = { status: 403, body: bffError('FORBIDDEN', '沒有權限') };
    const client = new ApiClient(baseURL);
    const onAuthFailure = vi.fn();
    client.onAuthFailure = onAuthFailure;

    await expect(client.rooms.get('r1')).rejects.toBeTruthy();
    expect(onAuthFailure).not.toHaveBeenCalled();
  });
});

describe('ApiClient 請求', () => {
  it('登入以表單送出', async () => {
    reply = { status: 200, body: bffOk({ user: { id: 'u1' } }) };

    expect(await new ApiClient(baseURL).auth.login({ username: 'alice', password: 'p w' })).toEqual({
      user: { id: 'u1' },
    });
    expect(received[0]).toMatchObject({
      method: 'POST',
      url: '/api/auth/login',
      body: 'username=alice&password=p+w',
      contentType: 'application/x-www-form-urlencoded',
    });
  });

  it.each([
    ['列表', () => [{}], '/api/rooms'],
    ['搜尋', () => [{ search: '大 廳', limit: 10 }], '/api/rooms?limit=10&search=%E5%A4%A7+%E5%BB%B3'],
    ['探索', () => [{ exclude_joined: true, offset: 20 }], '/api/rooms?offset=20&exclude_joined=true'],
  ])('房間%s的查詢參數', async (_, args, url) => {
    reply = { status: 200, body: bffOk([]) };

    await new ApiClient(baseURL).rooms.list(...(args() as [object]));

    expect(received[0]!.url).toBe(url);
  });

  it.each([
    [undefined, '/api/rooms/r1/messages?limit=50&offset=0'],
    [120, '/api/rooms/r1/messages?limit=50&offset=0&before_seq=120'],
  ])('訊息列表（before_seq=%s）', async (beforeSeq, url) => {
    reply = { status: 200, body: bffOk([]) };

    await new ApiClient(baseURL).messages.list('r1', 50, 0, beforeSeq);

    expect(received[0]!.url).toBe(url);
  });

  it('加入房間：有密碼走 join-advanced，沒有走 join', async () => {
    reply = { status: 200, body: bffOk({}) };
    const client = new ApiClient(baseURL);

    await client.rooms.join('r1', { password: 'pw' });
    await client.rooms.join('r1');

    expect(received.map((r) => [r.url, r.body])).toEqual([
      ['/api/rooms/r1/join-advanced', JSON.stringify({ password: 'pw' })],
      ['/api/rooms/r1/join', ''],
    ]);
  });

  it('WS ticket 只回傳 ticket 字串', async () => {
    reply = { status: 200, body: bffOk({ ticket: 't-1' }) };

    expect(await new ApiClient(baseURL).wsTicket.create('r1')).toBe('t-1');
    expect(JSON.parse(received[0]!.body)).toEqual({ room_id: 'r1' });
  });
});
