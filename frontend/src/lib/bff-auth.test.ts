import { describe, expect, it } from 'vitest';
import { bffAuthRequest, tryRefreshIfNeeded } from './bff-auth';
import { backendError, FakeCookies, mockBackend, tokenExpiringIn } from '../tests/bff';

const VALID = tokenExpiringIn(3600);
const EXPIRED = tokenExpiringIn(-10);
const NEW_ACCESS = tokenExpiringIn(3600, { sub: 'alice', v: 2 });

function refreshOk(options: { data?: unknown }) {
  expect(options.data).toEqual({ refresh_token: 'refresh-1' });
  return { access_token: NEW_ACCESS, refresh_token: 'refresh-2', token_type: 'bearer' };
}

function refreshFails(): never {
  throw backendError(401, 'Invalid refresh token');
}

function authorizedAs(token: string, result: unknown = { ok: true }) {
  return (options: { token?: string }) => {
    if (options.token !== token) throw backendError(401, 'Could not validate credentials');
    return result;
  };
}

describe('bffAuthRequest', () => {
  it('token 有效時直接帶 token 請求，不換發', async () => {
    const backend = mockBackend({ 'GET /api/auth/me': authorizedAs(VALID, { username: 'alice' }) });

    const user = await bffAuthRequest(new FakeCookies({ auth_token: VALID }), '/api/auth/me');

    expect(user).toEqual({ username: 'alice' });
    expect(backend).toHaveBeenCalledOnce();
  });

  it('轉送 method、data 與 headers', async () => {
    const backend = mockBackend({ 'PUT /api/rooms/r1': () => ({ id: 'r1' }) });

    await bffAuthRequest(new FakeCookies({ auth_token: VALID }), '/api/rooms/r1', {
      method: 'PUT',
      data: { name: '新名稱' },
      headers: { 'X-Test': '1' },
    });

    expect(backend).toHaveBeenCalledWith('/api/rooms/r1', {
      method: 'PUT',
      data: { name: '新名稱' },
      headers: { 'X-Test': '1' },
      token: VALID,
    });
  });

  it.each([
    ['access token 已過期', { auth_token: EXPIRED, refresh_token: 'refresh-1' }],
    ['沒有 access token', { refresh_token: 'refresh-1' }],
  ])('%s 時先換發，再用新 token 請求並更新 cookie', async (_, initial) => {
    const backend = mockBackend({
      'POST /api/auth/refresh': refreshOk,
      'GET /api/auth/me': authorizedAs(NEW_ACCESS),
    });
    const cookies = new FakeCookies(initial);

    await bffAuthRequest(cookies, '/api/auth/me');

    expect(backend.mock.calls.map(([endpoint]) => endpoint)).toEqual(['/api/auth/refresh', '/api/auth/me']);
    expect(cookies.get('auth_token')).toBe(NEW_ACCESS);
    expect(cookies.get('refresh_token')).toBe('refresh-2');
    expect(cookies.options.get('auth_token')).toEqual({
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'strict',
      maxAge: 60 * 60 * 24 * 7,
    });
  });

  it('沒有任何 token 時丟 401，不呼叫後端', async () => {
    const backend = mockBackend({});

    await expect(bffAuthRequest(new FakeCookies(), '/api/auth/me')).rejects.toEqual({
      code: 401,
      message: 'Not authenticated',
    });
    expect(backend).not.toHaveBeenCalled();
  });

  it('換發失敗時清除 cookie 並丟 401', async () => {
    const backend = mockBackend({ 'POST /api/auth/refresh': refreshFails });
    const cookies = new FakeCookies({ auth_token: EXPIRED, refresh_token: 'refresh-1' });

    await expect(bffAuthRequest(cookies, '/api/auth/me')).rejects.toMatchObject({ code: 401 });
    expect(backend).toHaveBeenCalledOnce();
    expect(cookies.getAll()).toEqual([]);
  });

  it('後端回 401（例如 token 已撤銷）時換發並重試一次', async () => {
    const backend = mockBackend({
      'POST /api/auth/refresh': refreshOk,
      'GET /api/rooms/my': authorizedAs(NEW_ACCESS, [{ id: 'r1' }]),
    });
    const cookies = new FakeCookies({ auth_token: VALID, refresh_token: 'refresh-1' });

    const rooms = await bffAuthRequest(cookies, '/api/rooms/my');

    expect(rooms).toEqual([{ id: 'r1' }]);
    expect(backend.mock.calls.map(([endpoint, options]) => [endpoint, options?.token])).toEqual([
      ['/api/rooms/my', VALID],
      ['/api/auth/refresh', undefined],
      ['/api/rooms/my', NEW_ACCESS],
    ]);
  });

  it('後端回 401 且換發失敗時丟出原本的錯誤並清除 cookie', async () => {
    mockBackend({ 'POST /api/auth/refresh': refreshFails, 'GET /api/auth/me': authorizedAs('other') });
    const cookies = new FakeCookies({ auth_token: VALID, refresh_token: 'refresh-1' });

    await expect(bffAuthRequest(cookies, '/api/auth/me')).rejects.toEqual(
      backendError(401, 'Could not validate credentials')
    );
    expect(cookies.getAll()).toEqual([]);
  });

  it('重試仍 401 時不再換發（不會無限重試）', async () => {
    const backend = mockBackend({
      'POST /api/auth/refresh': refreshOk,
      'GET /api/auth/me': authorizedAs('never'),
    });

    await expect(
      bffAuthRequest(new FakeCookies({ auth_token: VALID, refresh_token: 'refresh-1' }), '/api/auth/me')
    ).rejects.toMatchObject({ code: 401 });
    expect(backend).toHaveBeenCalledTimes(3);
  });

  it('非 401 錯誤直接往上丟，不換發', async () => {
    const backend = mockBackend({
      'DELETE /api/rooms/r1': () => {
        throw backendError(403, '只有房主可以刪除');
      },
    });

    await expect(
      bffAuthRequest(new FakeCookies({ auth_token: VALID, refresh_token: 'refresh-1' }), '/api/rooms/r1', {
        method: 'DELETE',
      })
    ).rejects.toEqual(backendError(403, '只有房主可以刪除'));
    expect(backend).toHaveBeenCalledOnce();
  });

  it('同一 refresh token 的並行請求只換發一次', async () => {
    let finishRefresh!: () => void;
    const refreshGate = new Promise<void>((resolve) => (finishRefresh = resolve));
    const backend = mockBackend({
      'POST /api/auth/refresh': async (options) => {
        await refreshGate;
        return refreshOk(options);
      },
      'GET /api/auth/me': authorizedAs(NEW_ACCESS, 'me'),
      'GET /api/rooms/my': authorizedAs(NEW_ACCESS, 'rooms'),
    });
    const tabA = new FakeCookies({ auth_token: EXPIRED, refresh_token: 'refresh-1' });
    const tabB = new FakeCookies({ auth_token: EXPIRED, refresh_token: 'refresh-1' });

    const pending = Promise.all([bffAuthRequest(tabA, '/api/auth/me'), bffAuthRequest(tabB, '/api/rooms/my')]);
    finishRefresh();

    expect(await pending).toEqual(['me', 'rooms']);
    expect(backend.mock.calls.filter(([endpoint]) => endpoint === '/api/auth/refresh')).toHaveLength(1);
  });

  it('不同使用者的換發不共用結果', async () => {
    const backend = mockBackend({
      'POST /api/auth/refresh': (options) => {
        const { refresh_token } = options.data as { refresh_token: string };
        return { access_token: tokenExpiringIn(3600, { sub: refresh_token }), refresh_token, token_type: 'bearer' };
      },
      'GET /api/auth/me': (options) => options.token,
    });

    const [alice, bob] = await Promise.all([
      bffAuthRequest<string>(new FakeCookies({ refresh_token: 'alice-refresh' }), '/api/auth/me'),
      bffAuthRequest<string>(new FakeCookies({ refresh_token: 'bob-refresh' }), '/api/auth/me'),
    ]);

    expect(alice).not.toBe(bob);
    expect(backend.mock.calls.filter(([endpoint]) => endpoint === '/api/auth/refresh')).toHaveLength(2);
  });
});

describe('tryRefreshIfNeeded', () => {
  it('換發成功回傳新 token', async () => {
    mockBackend({ 'POST /api/auth/refresh': refreshOk });

    expect(await tryRefreshIfNeeded(new FakeCookies({ refresh_token: 'refresh-1' }))).toBe(NEW_ACCESS);
  });

  it('沒有 refresh token 時回傳 null', async () => {
    const backend = mockBackend({});

    expect(await tryRefreshIfNeeded(new FakeCookies())).toBeNull();
    expect(backend).not.toHaveBeenCalled();
  });
});
