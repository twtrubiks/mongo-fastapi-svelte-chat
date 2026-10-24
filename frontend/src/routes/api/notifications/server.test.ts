// 通知相關 BFF 路由：列表 / 未讀 / 統計 / 標記已讀 / 刪除
import { describe, expect, it } from 'vitest';
import * as list from './+server';
import * as unread from './unread/+server';
import * as stats from './stats/+server';
import * as single from './[id]/+server';
import * as read from './[id]/read/+server';
import * as readAll from './read-all/+server';
import { backendError, FakeCookies, makeEvent, mockBackend, tokenExpiringIn } from '../../../tests/bff';

const RAW = {
  id: 'n1',
  user_id: 'u1',
  type: 'message',
  status: 'unread',
  title: '新訊息',
  content: 'bob: 嗨',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};
const LIST = { notifications: [RAW, { id: 'broken' }], unread_count: 7 };

function event(url = '/', params: Record<string, string> = {}) {
  return makeEvent({ cookies: new FakeCookies({ auth_token: tokenExpiringIn(3600) }), url, params });
}

describe('GET /api/notifications', () => {
  it('預設第一頁 20 筆，轉成前端格式且不包 BFF 信封', async () => {
    const backend = mockBackend({ 'GET /api/notifications/?skip=0&limit=20': () => LIST });

    const response = await list.GET(event('/api/notifications'));
    const body = await response.json();

    expect(backend).toHaveBeenCalledOnce();
    expect(body).toEqual({
      notifications: [expect.objectContaining({ id: 'n1', type: 'MESSAGE', status: 'UNREAD', message: 'bob: 嗨' })],
      unread_count: 7,
    });
  });

  it('offset 對應後端 skip，並轉送篩選條件（前端大寫格式轉回後端小寫）', async () => {
    const backend = mockBackend({
      'GET /api/notifications/?skip=40&limit=10&status=unread&type=system': () => LIST,
    });

    const response = await list.GET(event('/api/notifications?offset=40&limit=10&status=UNREAD&type=SYSTEM'));

    expect(response.status).toBe(200);
    expect(backend).toHaveBeenCalledOnce();
  });

  it('後端錯誤轉成 BFF 錯誤', async () => {
    mockBackend({
      'GET /api/notifications/?skip=0&limit=20': () => {
        throw backendError(503, '資料庫錯誤');
      },
    });

    const response = await list.GET(event('/api/notifications'));

    expect(response.status).toBe(503);
    expect((await response.json()).error).toMatchObject({ code: 'INTERNAL_ERROR', message: '資料庫錯誤' });
  });
});

describe('DELETE /api/notifications', () => {
  it('清空全部通知', async () => {
    mockBackend({ 'DELETE /api/notifications/': () => ({ message: '已清空 3 個通知', count: 3 }) });

    const body = await (await list.DELETE(event())).json();

    expect(body).toMatchObject({ success: true, data: { message: '已清空 3 個通知', count: 3 } });
  });
});

describe('GET /api/notifications/unread', () => {
  it('預設取 10 筆，回傳轉換後的通知與總數', async () => {
    mockBackend({ 'GET /api/notifications/unread?limit=10': () => LIST });

    const body = await (await unread.GET(event('/api/notifications/unread'))).json();

    expect(body.success).toBe(true);
    expect(body.data).toEqual({
      notifications: [expect.objectContaining({ id: 'n1', type: 'MESSAGE' })],
      unread_count: 7,
    });
  });

  it('轉送 limit', async () => {
    const backend = mockBackend({ 'GET /api/notifications/unread?limit=3': () => LIST });

    await unread.GET(event('/api/notifications/unread?limit=3'));

    expect(backend).toHaveBeenCalledOnce();
  });

  it('未登入回 401', async () => {
    const response = await unread.GET(makeEvent({ url: '/api/notifications/unread' }));

    expect(response.status).toBe(401);
  });
});

describe('GET /api/notifications/stats', () => {
  it('統計欄位轉成前端格式', async () => {
    mockBackend({
      'GET /api/notifications/stats': () => ({
        total_count: 4,
        unread_count: 3,
        read_count: 1,
        type_counts: { message: 3, system: 1 },
        recent_activity: [],
      }),
    });

    const body = await (await stats.GET(event())).json();

    expect(body.data).toEqual({ total: 4, unread: 3, by_type: { MESSAGE: 3, SYSTEM: 1 } });
  });
});

describe('單筆通知操作', () => {
  it('標記已讀', async () => {
    mockBackend({ 'POST /api/notifications/n1/read': () => ({ message: '通知已標記為已讀' }) });

    const body = await (await read.POST(event('/', { id: 'n1' }))).json();

    expect(body).toMatchObject({ success: true, data: { message: '通知已標記為已讀' } });
  });

  it('標記他人通知已讀時沿用後端 403', async () => {
    mockBackend({
      'POST /api/notifications/n1/read': () => {
        throw backendError(403, '無權限操作此通知');
      },
    });

    const response = await read.POST(event('/', { id: 'n1' }));

    expect(response.status).toBe(403);
    expect((await response.json()).error.message).toBe('無權限操作此通知');
  });

  it('全部標記已讀', async () => {
    mockBackend({ 'POST /api/notifications/read-all': () => ({ message: '已標記 2 個通知為已讀', count: 2 }) });

    const body = await (await readAll.POST(event())).json();

    expect(body.data).toEqual({ message: '已標記 2 個通知為已讀', count: 2 });
  });

  it('刪除通知', async () => {
    mockBackend({ 'DELETE /api/notifications/n1': () => ({ message: '通知已刪除' }) });

    const body = await (await single.DELETE(event('/', { id: 'n1' }))).json();

    expect(body.data).toEqual({ message: '通知已刪除' });
  });

  it('刪除不存在的通知回 404', async () => {
    mockBackend({
      'DELETE /api/notifications/n1': () => {
        throw backendError(404, '通知不存在');
      },
    });

    const response = await single.DELETE(event('/', { id: 'n1' }));

    expect(response.status).toBe(404);
    expect((await response.json()).error.message).toBe('通知不存在');
  });
});
