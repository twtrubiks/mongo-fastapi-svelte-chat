// 認證相關 BFF 路由：token 只存在 httpOnly cookie，絕不出現在回應內容
import { describe, expect, it } from 'vitest';
import * as login from './login/+server';
import * as register from './register/+server';
import * as refresh from './refresh/+server';
import * as logout from './logout/+server';
import * as me from './me/+server';
import * as profile from './profile/+server';
import * as changePassword from './change-password/+server';
import {
  backendError,
  FakeCookies,
  jsonRequest,
  makeEvent,
  mockBackend,
  tokenExpiringIn,
  type RequestEvent,
} from '../../../tests/bff';

const USER = { id: 'u1', username: 'alice', email: 'alice@example.com' };
const TOKENS = { access_token: 'access-1', refresh_token: 'refresh-1', token_type: 'bearer' };

function loginRequest(contentType: string, body: BodyInit) {
  return new Request('http://localhost/api/auth/login', {
    method: 'POST',
    headers: contentType ? { 'Content-Type': contentType } : {},
    body,
  });
}

function loginEvent(request: Request, cookies = new FakeCookies()) {
  return makeEvent({ request, cookies, clientAddress: '203.0.113.9' });
}

function throws(code: number, message = 'boom') {
  return () => {
    throw backendError(code, message);
  };
}

describe('POST /api/auth/login', () => {
  it.each([
    ['表單', 'application/x-www-form-urlencoded', 'username=alice&password=secret1'],
    ['JSON', 'application/json', JSON.stringify({ username: 'alice', password: 'secret1' })],
    [
      'multipart',
      '',
      (() => {
        const form = new FormData();
        form.append('username', 'alice');
        form.append('password', 'secret1');
        return form;
      })(),
    ],
  ])('%s登入：以表單轉送後端並把 token 寫入 httpOnly cookie', async (_, contentType, body) => {
    const backend = mockBackend({ 'POST /api/auth/login': () => ({ ...TOKENS, user: USER }) });
    const cookies = new FakeCookies();

    const response = await login.POST(loginEvent(loginRequest(contentType, body), cookies));
    const json = await response.json();

    expect(response.status).toBe(200);
    expect(json.data).toEqual({ user: USER });
    expect(JSON.stringify(json)).not.toContain('access-1');
    expect(backend).toHaveBeenCalledWith('/api/auth/login', {
      method: 'POST',
      data: 'username=alice&password=secret1',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      clientIp: '203.0.113.9',
    });
    expect(cookies.get('auth_token')).toBe('access-1');
    expect(cookies.get('refresh_token')).toBe('refresh-1');
    expect(cookies.options.get('auth_token')).toMatchObject({ httpOnly: true, sameSite: 'strict', path: '/' });
  });

  it('缺少帳號或密碼時不呼叫後端', async () => {
    const backend = mockBackend({});

    const response = await login.POST(
      loginEvent(loginRequest('application/x-www-form-urlencoded', 'username=alice'))
    );

    expect(response.status).toBe(400);
    expect((await response.json()).error).toMatchObject({ code: 'VALIDATION_ERROR' });
    expect(backend).not.toHaveBeenCalled();
  });

  it.each([
    [401, 401, '用戶名或密碼錯誤'],
    [422, 422, 'String should have at least 3 characters'],
    [429, 429, '嘗試次數過多，請稍後再試'],
    [500, 500, '登入失敗'],
  ])('後端 %i → %i「%s」，且不寫入 cookie', async (backendStatus, status, message) => {
    mockBackend({ 'POST /api/auth/login': throws(backendStatus, 'String should have at least 3 characters') });
    const cookies = new FakeCookies();

    const response = await login.POST(
      loginEvent(loginRequest('application/x-www-form-urlencoded', 'username=al&password=x'), cookies)
    );

    expect(response.status).toBe(status);
    expect((await response.json()).error).toMatchObject({ code: 'AUTH_ERROR', message });
    expect(cookies.getAll()).toEqual([]);
  });
});

describe('POST /api/auth/register', () => {
  const DATA = { username: 'alice', email: 'alice@example.com', password: 'secret1' };

  function registerEvent(body: unknown, cookies = new FakeCookies()) {
    return makeEvent({ request: jsonRequest('POST', body), cookies, clientAddress: '203.0.113.9' });
  }

  it('註冊成功即登入，token 只寫入 cookie', async () => {
    const backend = mockBackend({ 'POST /api/auth/register': () => ({ ...TOKENS, user: USER }) });
    const cookies = new FakeCookies();

    const json = await (await register.POST(registerEvent(DATA, cookies))).json();

    expect(json.data).toEqual({ user: USER });
    expect(JSON.stringify(json)).not.toContain('refresh-1');
    expect(backend).toHaveBeenCalledWith('/api/auth/register', expect.objectContaining({
      data: DATA,
      clientIp: '203.0.113.9',
    }));
    expect(cookies.get('auth_token')).toBe('access-1');
  });

  it.each(['username', 'email', 'password'])('缺少 %s 時回 400', async (field) => {
    mockBackend({});

    const response = await register.POST(registerEvent({ ...DATA, [field]: '' }));

    expect(response.status).toBe(400);
  });

  it.each([
    [409, 409, '用戶名或郵箱已存在'],
    [422, 422, 'value is not a valid email address'],
    [429, 429, '嘗試次數過多，請稍後再試'],
    [500, 500, '註冊失敗'],
  ])('後端 %i → %i「%s」', async (backendStatus, status, message) => {
    mockBackend({ 'POST /api/auth/register': throws(backendStatus, 'value is not a valid email address') });

    const response = await register.POST(registerEvent(DATA));

    expect(response.status).toBe(status);
    expect((await response.json()).error).toMatchObject({ code: 'REGISTER_ERROR', message });
  });
});

describe('POST /api/auth/refresh', () => {
  it('換發成功更新兩個 cookie，回應不含 token', async () => {
    const backend = mockBackend({ 'POST /api/auth/refresh': () => ({ ...TOKENS, access_token: 'access-2', refresh_token: 'refresh-2' }) });
    const cookies = new FakeCookies({ refresh_token: 'refresh-1' });

    const json = await (await refresh.POST(makeEvent({ cookies, clientAddress: '203.0.113.9' }))).json();

    expect(json.data).toEqual({ refreshed: true });
    expect(backend).toHaveBeenCalledWith('/api/auth/refresh', expect.objectContaining({
      data: { refresh_token: 'refresh-1' },
      clientIp: '203.0.113.9',
    }));
    expect(cookies.get('auth_token')).toBe('access-2');
    expect(cookies.get('refresh_token')).toBe('refresh-2');
  });

  it('沒有 refresh token 時回 401', async () => {
    const backend = mockBackend({});

    const response = await refresh.POST(makeEvent({}));

    expect(response.status).toBe(401);
    expect(backend).not.toHaveBeenCalled();
  });

  it('換發失敗時清除 cookie 並回 401', async () => {
    mockBackend({ 'POST /api/auth/refresh': throws(401) });
    const cookies = new FakeCookies({ auth_token: 'old', refresh_token: 'refresh-1' });

    const response = await refresh.POST(makeEvent({ cookies }));

    expect(response.status).toBe(401);
    expect(cookies.getAll()).toEqual([]);
  });
});

describe('POST /api/auth/logout', () => {
  // logout 使用 ./$types 的 RequestHandler，事件型別帶 route id
  const post = (event: RequestEvent) => logout.POST(event as Parameters<typeof logout.POST>[0]);

  it('通知後端撤銷 token 並清除 cookie', async () => {
    const backend = mockBackend({ 'POST /api/auth/logout': () => ({ message: 'ok' }) });
    const cookies = new FakeCookies({ auth_token: 'access-1', refresh_token: 'refresh-1' });

    const json = await (await post(makeEvent({ cookies }))).json();

    expect(json).toEqual({ success: true, message: '登出成功', redirectTo: '/login' });
    expect(backend).toHaveBeenCalledWith('/api/auth/logout', { method: 'POST', token: 'access-1' });
    expect(cookies.getAll()).toEqual([]);
  });

  it('後端登出失敗仍清除 cookie', async () => {
    mockBackend({ 'POST /api/auth/logout': throws(500) });
    const cookies = new FakeCookies({ auth_token: 'access-1', refresh_token: 'refresh-1' });

    const response = await post(makeEvent({ cookies }));

    expect(response.status).toBe(200);
    expect(cookies.getAll()).toEqual([]);
  });

  it('沒有 token 時不呼叫後端', async () => {
    const backend = mockBackend({});

    await post(makeEvent({ cookies: new FakeCookies({ refresh_token: 'refresh-1' }) }));

    expect(backend).not.toHaveBeenCalled();
  });
});

describe('受保護的使用者路由', () => {
  const authed = () => new FakeCookies({ auth_token: tokenExpiringIn(3600) });

  it('GET /api/auth/me', async () => {
    mockBackend({ 'GET /api/auth/me': () => USER });

    expect((await (await me.GET(makeEvent({ cookies: authed() }))).json()).data).toEqual(USER);
  });

  it('未登入時回 401', async () => {
    const response = await me.GET(makeEvent({}));

    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe('UNAUTHORIZED');
  });

  it('GET / PUT /api/auth/profile', async () => {
    const backend = mockBackend({
      'GET /api/auth/profile': () => USER,
      'PUT /api/auth/profile': (options) => ({ ...USER, ...(options.data as object) }),
    });

    const got = await (await profile.GET(makeEvent({ cookies: authed() }))).json();
    const updated = await (
      await profile.PUT(makeEvent({ cookies: authed(), request: jsonRequest('PUT', { full_name: 'Alice' }) }))
    ).json();

    expect(got.data).toEqual(USER);
    expect(updated.data).toEqual({ ...USER, full_name: 'Alice' });
    expect(backend).toHaveBeenLastCalledWith('/api/auth/profile', expect.objectContaining({
      method: 'PUT',
      data: { full_name: 'Alice' },
    }));
  });

  it('修改密碼：舊密碼錯誤時沿用後端訊息', async () => {
    mockBackend({ 'PUT /api/auth/change-password': throws(400, '目前密碼錯誤') });
    const request = jsonRequest('PUT', { current_password: 'x', new_password: 'secret2' });

    const response = await changePassword.PUT(makeEvent({ cookies: authed(), request }));

    expect(response.status).toBe(400);
    expect((await response.json()).error.message).toBe('目前密碼錯誤');
  });
});
