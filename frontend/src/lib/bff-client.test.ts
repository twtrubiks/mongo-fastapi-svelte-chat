import { createServer, type IncomingMessage, type Server } from 'node:http';
import type { AddressInfo } from 'node:net';
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { BFFBackendClient } from './bff-client';

interface Received {
  method: string | undefined;
  url: string | undefined;
  headers: IncomingMessage['headers'];
  body: string;
}

// 以真實 HTTP server 扮演後端：記錄收到的請求，回應由各測試設定
let server: Server;
let baseURL: string;
let received: Received[] = [];
let reply: { status: number; body: unknown } = { status: 200, body: {} };

beforeAll(async () => {
  server = createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => (body += chunk));
    req.on('end', () => {
      received.push({ method: req.method, url: req.url, headers: req.headers, body });
      res.writeHead(reply.status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(reply.body));
    });
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  baseURL = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

beforeEach(() => {
  received = [];
  reply = { status: 200, body: {} };
});

describe('BFFBackendClient.request', () => {
  it('GET 回傳後端 JSON，未帶 token 時不送 Authorization', async () => {
    reply = { status: 200, body: [{ id: 'r1' }] };

    const data = await new BFFBackendClient(baseURL).request('/api/rooms?limit=5');

    expect(data).toEqual([{ id: 'r1' }]);
    expect(received).toHaveLength(1);
    expect(received[0]).toMatchObject({ method: 'GET', url: '/api/rooms?limit=5' });
    expect(received[0]!.headers['authorization']).toBeUndefined();
    expect(received[0]!.headers['x-forwarded-for']).toBeUndefined();
  });

  it('帶上 token、真實 client IP 與自訂 header', async () => {
    await new BFFBackendClient(baseURL).request('/api/auth/login', {
      method: 'POST',
      data: 'username=a&password=b',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      token: 'tok',
      clientIp: '203.0.113.9',
    });

    expect(received[0]).toMatchObject({ method: 'POST', body: 'username=a&password=b' });
    expect(received[0]!.headers).toMatchObject({
      authorization: 'Bearer tok',
      'x-forwarded-for': '203.0.113.9',
      'content-type': 'application/x-www-form-urlencoded',
    });
  });

  it('物件資料以 JSON 送出', async () => {
    await new BFFBackendClient(baseURL).request('/api/rooms/', {
      method: 'POST',
      data: { name: '大廳' },
      token: 'tok',
    });

    expect(received[0]!.headers['content-type']).toContain('application/json');
    expect(JSON.parse(received[0]!.body)).toEqual({ name: '大廳' });
  });

  describe('錯誤轉換為 { code, message, details }', () => {
    it.each([
      ['業務錯誤 {detail}', 403, { detail: '只有房主可以刪除' }, '只有房主可以刪除'],
      [
        '全域錯誤處理器 {success, error}',
        500,
        { success: false, error: { code: 'DATABASE_ERROR', message: '資料庫錯誤' } },
        '資料庫錯誤',
      ],
      [
        '限流 {error, message}',
        429,
        { error: 'Rate limit exceeded', message: 'Too many requests. Please try again in 30 seconds.' },
        'Too many requests. Please try again in 30 seconds.',
      ],
      [
        // FastAPI 欄位驗證失敗時 detail 是陣列；訊息必須是字串，前端才認得 BFF 錯誤格式
        '欄位驗證 {detail: [...]}',
        422,
        {
          detail: [
            { loc: ['body', 'username'], msg: 'String should have at least 3 characters', type: 'string_too_short' },
            { loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error' },
          ],
        },
        'String should have at least 3 characters; value is not a valid email address',
      ],
    ])('%s', async (_, status, body, message) => {
      reply = { status, body };

      const error = await new BFFBackendClient(baseURL).request('/api/x').catch((e: unknown) => e);

      expect(error).toEqual({ code: status, message, details: body });
    });

    it('無法辨識的錯誤內容使用 axios 訊息', async () => {
      reply = { status: 502, body: 'bad gateway' };

      const error = await new BFFBackendClient(baseURL).request('/api/x').catch((e: unknown) => e);

      expect(error).toEqual({
        code: 502,
        message: 'Request failed with status code 502',
        details: 'bad gateway',
      });
    });

    it('後端連不上時為 NETWORK_ERROR', async () => {
      const closed = createServer();
      await new Promise<void>((resolve) => closed.listen(0, '127.0.0.1', resolve));
      const port = (closed.address() as AddressInfo).port;
      await new Promise<void>((resolve) => closed.close(() => resolve()));

      const error = await new BFFBackendClient(`http://127.0.0.1:${port}`)
        .request('/api/x')
        .catch((e: unknown) => e);

      expect(error).toMatchObject({ code: 'NETWORK_ERROR', message: expect.stringContaining('ECONNREFUSED') });
    });
  });
});
