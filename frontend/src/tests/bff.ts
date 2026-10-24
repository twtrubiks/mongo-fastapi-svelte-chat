// BFF 測試共用工具：假 cookie、JWT 與 RequestEvent
import type { Cookies, RequestHandler } from '@sveltejs/kit';
import { vi } from 'vitest';
import { bffBackendClient } from '$lib/bff-client';

type CookieOptions = Parameters<Cookies['set']>[2];
type RequestOptions = Parameters<typeof bffBackendClient.request>[1];
export type RequestEvent = Parameters<RequestHandler>[0];

/** 以 Map 實作的 Cookies，記錄最後一次 set 的選項 */
export class FakeCookies implements Cookies {
  store = new Map<string, string>();
  options = new Map<string, CookieOptions>();

  constructor(initial: Record<string, string> = {}) {
    for (const [name, value] of Object.entries(initial)) this.store.set(name, value);
  }

  get(name: string) {
    return this.store.get(name);
  }

  getAll() {
    return [...this.store].map(([name, value]) => ({ name, value }));
  }

  set(name: string, value: string, opts: CookieOptions) {
    this.store.set(name, value);
    this.options.set(name, opts);
  }

  delete(name: string) {
    this.store.delete(name);
  }

  serialize(name: string, value: string) {
    return `${name}=${value}`;
  }
}

/** 產生未簽章的 JWT（BFF 只解 payload 判斷過期，不驗簽） */
export function makeJwt(payload: Record<string, unknown>): string {
  const encode = (value: unknown) => Buffer.from(JSON.stringify(value)).toString('base64url');
  return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.signature`;
}

/** 距今 seconds 秒後過期的 token */
export function tokenExpiringIn(seconds: number, extra: Record<string, unknown> = {}): string {
  return makeJwt({ sub: 'alice', exp: Math.floor(Date.now() / 1000) + seconds, ...extra });
}

/** 組出 handler 需要的 RequestEvent（只填 BFF 路由會用到的欄位） */
export function makeEvent(init: {
  cookies?: Cookies;
  url?: string;
  params?: Record<string, string>;
  request?: Request;
  clientAddress?: string;
}): RequestEvent {
  const url = new URL(init.url ?? '/', 'http://localhost');
  return {
    cookies: init.cookies ?? new FakeCookies(),
    url,
    params: init.params ?? {},
    request: init.request ?? new Request(url),
    getClientAddress: () => init.clientAddress ?? '127.0.0.1',
  } as unknown as RequestEvent;
}

/** JSON 請求 */
export function jsonRequest(method: string, body: unknown, path = '/'): Request {
  return new Request(new URL(path, 'http://localhost'), {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** 後端回應的錯誤格式（與 BFFBackendClient 丟出的相同） */
export function backendError(code: number | string, message: string, details?: unknown) {
  return { code, message, details };
}

type Handler = (options: NonNullable<RequestOptions>) => unknown;

/**
 * 以 spy 取代 bffBackendClient.request，依 "METHOD endpoint" 分派。
 * handler 丟出的值即為後端錯誤；未列出的端點一律 404，避免測試誤打到真實後端。
 */
export function mockBackend(routes: Record<string, Handler>) {
  return vi.spyOn(bffBackendClient, 'request').mockImplementation(async (endpoint, options = {}) => {
    const key = `${options.method ?? 'GET'} ${endpoint}`;
    const handler = routes[key];
    if (!handler) throw backendError(404, `未模擬的後端端點：${key}`);
    return handler(options);
  });
}
