import { describe, expect, it } from 'vitest';
import { GET } from './+server';
import { backendError, FakeCookies, makeEvent, mockBackend, tokenExpiringIn } from '../../../tests/bff';

const USER = { id: 'u1', username: 'alice' };
const MY_ROOMS = [{ id: 'r1', name: '大廳', member_count: 2 }];
const UNREAD = {
  notifications: [
    {
      id: 'n1',
      user_id: 'u1',
      type: 'message',
      status: 'unread',
      title: '新訊息',
      content: 'bob: 嗨',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    },
  ],
  // 後端只回傳 limit 筆，總數以 unread_count 為準
  unread_count: 12,
};

function dashboard() {
  return GET(makeEvent({ cookies: new FakeCookies({ auth_token: tokenExpiringIn(3600) }) }));
}

function fail(code: number) {
  return () => {
    throw backendError(code, 'boom');
  };
}

describe('GET /api/dashboard', () => {
  it('聚合使用者、已加入的房間與未讀通知', async () => {
    mockBackend({
      'GET /api/auth/me': () => USER,
      'GET /api/rooms/my?limit=100': () => MY_ROOMS,
      'GET /api/notifications/unread': () => UNREAD,
    });

    const response = await dashboard();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.data).toEqual({
      user: USER,
      rooms: MY_ROOMS,
      unreadCount: 12,
      notifications: [
        expect.objectContaining({ id: 'n1', type: 'MESSAGE', status: 'UNREAD', content: 'bob: 嗨' }),
      ],
    });
  });

  it('房間或通知載入失敗時以空資料呈現', async () => {
    mockBackend({
      'GET /api/auth/me': () => USER,
      'GET /api/rooms/my?limit=100': fail(500),
      'GET /api/notifications/unread': fail(503),
    });

    const response = await dashboard();

    expect(response.status).toBe(200);
    expect((await response.json()).data).toEqual({ user: USER, rooms: [], unreadCount: 0, notifications: [] });
  });

  it.each([
    ['使用者', 'GET /api/auth/me'],
    ['房間', 'GET /api/rooms/my?limit=100'],
    ['通知', 'GET /api/notifications/unread'],
  ])('%s回 401 時整體回 401', async (_, failing) => {
    mockBackend({
      'GET /api/auth/me': () => USER,
      'GET /api/rooms/my?limit=100': () => MY_ROOMS,
      'GET /api/notifications/unread': () => UNREAD,
      [failing]: fail(401),
    });

    const response = await dashboard();

    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe('UNAUTHORIZED');
  });

  it('取不到使用者時回錯誤', async () => {
    mockBackend({
      'GET /api/auth/me': fail(500),
      'GET /api/rooms/my?limit=100': () => MY_ROOMS,
      'GET /api/notifications/unread': () => UNREAD,
    });

    const response = await dashboard();

    expect(response.status).toBe(500);
    expect((await response.json()).error.message).toBe('boom');
  });
});
