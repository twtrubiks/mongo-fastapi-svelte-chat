import { describe, expect, it, vi } from 'vitest';
import {
  createBFFError,
  createBFFResponse,
  isTokenExpired,
  isTokenExpiringSoon,
  toBffErrorResponse,
  transformNotification,
  transformNotificationListResponse,
  transformNotifications,
  transformNotificationStats,
  type RawNotification,
} from './bff-utils';
import { makeJwt, tokenExpiringIn } from '../tests/bff';

const RAW: RawNotification = {
  id: 'n1',
  user_id: 'u1',
  type: 'message',
  status: 'unread',
  title: '新訊息',
  content: 'bob: 嗨',
  metadata: { room_id: 'r1' },
  room_id: 'r1',
  sender_id: 'u2',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:01Z',
};

describe('createBFFResponse / createBFFError', () => {
  it('成功回應帶資料與 meta', () => {
    const response = createBFFResponse({ a: 1 });

    expect(response).toEqual({
      success: true,
      data: { a: 1 },
      error: undefined,
      meta: { timestamp: expect.any(String), requestId: expect.any(String) },
    });
    expect(new Date(response.meta!.timestamp).toISOString()).toBe(response.meta!.timestamp);
  });

  it('每次回應的 requestId 不同', () => {
    expect(createBFFResponse(1).meta!.requestId).not.toBe(createBFFResponse(1).meta!.requestId);
  });

  it('錯誤回應 success 為 false 且帶錯誤內容', () => {
    const response = createBFFError('NOT_FOUND', '找不到', { id: 'x' });

    expect(response.success).toBe(false);
    expect(response.data).toBeUndefined();
    expect(response.error).toEqual({ code: 'NOT_FOUND', message: '找不到', details: { id: 'x' } });
  });
});

describe('toBffErrorResponse', () => {
  it('401 一律轉成 UNAUTHORIZED，不洩漏後端訊息', async () => {
    const response = toBffErrorResponse({ code: 401, message: 'token revoked' }, '失敗');

    expect(response.status).toBe(401);
    expect((await response.json()).error).toEqual({ code: 'UNAUTHORIZED', message: '認證已過期' });
  });

  it('沿用後端的狀態碼與訊息', async () => {
    const response = toBffErrorResponse(
      { code: 403, message: '只有房主可以刪除', details: { detail: '只有房主可以刪除' } },
      '刪除失敗',
      'ROOM_DELETE_ERROR'
    );

    expect(response.status).toBe(403);
    expect((await response.json()).error).toEqual({
      code: 'ROOM_DELETE_ERROR',
      message: '只有房主可以刪除',
      details: { detail: '只有房主可以刪除' },
    });
  });

  it('呼叫端提供的 details 優先於後端的', async () => {
    const response = toBffErrorResponse(
      { code: 404, message: '不存在', details: { detail: '不存在' } },
      '失敗',
      'ROOM_ERROR',
      { roomId: 'r1' }
    );

    expect((await response.json()).error.details).toEqual({ roomId: 'r1' });
  });

  it.each([
    ['網路錯誤（字串 code）', { code: 'NETWORK_ERROR', message: 'connect ECONNREFUSED' }, 'connect ECONNREFUSED'],
    ['非物件錯誤', new Error(''), '載入失敗'],
    ['沒有訊息', { code: 500 }, '載入失敗'],
  ])('%s → 500 與 fallback', async (_, error, message) => {
    const response = toBffErrorResponse(error, '載入失敗');

    expect(response.status).toBe(500);
    expect((await response.json()).error).toMatchObject({ code: 'INTERNAL_ERROR', message });
  });
});

describe('isTokenExpiringSoon / isTokenExpired', () => {
  it.each([
    ['沒有 token', null],
    ['不是三段', 'a.b'],
    ['payload 不是 JSON', 'a.bm90LWpzb24.c'],
  ])('%s 視為過期', (_, token) => {
    expect(isTokenExpired(token)).toBe(true);
    expect(isTokenExpiringSoon(token)).toBe(true);
  });

  it('依門檻判斷即將過期', () => {
    const token = tokenExpiringIn(120);

    expect(isTokenExpired(token)).toBe(false);
    expect(isTokenExpiringSoon(token)).toBe(true);
    expect(isTokenExpiringSoon(token, 60)).toBe(false);
  });

  it('已過期', () => {
    expect(isTokenExpired(tokenExpiringIn(-1))).toBe(true);
  });

  // JWT 是 base64url（- 與 _），不是標準 base64；使用者名稱 "abc?" 的 payload 會出現 _
  it('payload 含 base64url 專用字元時仍能解析', () => {
    const token = makeJwt({ sub: 'abc?', user_id: 'u1', exp: Math.floor(Date.now() / 1000) + 3600 });
    expect(token.split('.')[1]).toMatch(/[-_]/);

    expect(isTokenExpired(token)).toBe(false);
    expect(isTokenExpiringSoon(token)).toBe(false);
  });
});

describe('transformNotification', () => {
  it('轉成前端格式（type / status 大寫、content 對應 message）', () => {
    expect(transformNotification(RAW)).toEqual({
      id: 'n1',
      user_id: 'u1',
      type: 'MESSAGE',
      status: 'UNREAD',
      title: '新訊息',
      message: 'bob: 嗨',
      content: 'bob: 嗨',
      metadata: { room_id: 'r1' },
      data: { room_id: 'r1' },
      room_id: 'r1',
      sender_id: 'u2',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:01Z',
    });
  });

  it('缺少選填欄位時補預設值，且不產生 undefined 欄位', () => {
    const transformed = transformNotification({
      id: 'n1',
      user_id: 'u1',
      created_at: 't0',
      updated_at: 't1',
    });

    expect(transformed).toEqual({
      id: 'n1',
      user_id: 'u1',
      type: 'SYSTEM',
      status: 'UNREAD',
      title: '通知',
      message: '',
      metadata: {},
      data: {},
      created_at: 't0',
      updated_at: 't1',
    });
    expect(Object.keys(transformed!)).not.toContain('content');
  });

  it('message 優先於 content，data 與 metadata 互為備援', () => {
    const transformed = transformNotification({
      id: 'n1',
      user_id: 'u1',
      message: 'WS 推送的訊息',
      content: '後端內容',
      data: { from: 'ws' },
      created_at: 't0',
      updated_at: 't1',
    });

    expect(transformed).toMatchObject({
      message: 'WS 推送的訊息',
      metadata: { from: 'ws' },
      data: { from: 'ws' },
    });
  });

  it.each([
    ['null', null],
    ['字串', 'oops'],
    ['缺 id', { ...RAW, id: undefined }],
    ['缺 user_id', { ...RAW, user_id: 1 }],
    ['缺 created_at', { ...RAW, created_at: undefined }],
    ['缺 updated_at', { ...RAW, updated_at: null }],
  ])('結構不完整（%s）回傳 null', (_, input) => {
    vi.spyOn(console, 'error').mockImplementation(() => {});

    expect(transformNotification(input)).toBeNull();
  });

  it('只對非空資料記錄錯誤', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {});

    transformNotification(undefined);
    expect(log).not.toHaveBeenCalled();
    transformNotification({ id: 'x' });
    expect(log).toHaveBeenCalledOnce();
  });
});

describe('transformNotifications / transformNotificationListResponse', () => {
  it('略過無效項目', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const list = [RAW, { id: 'bad' }, { ...RAW, id: 'n2' }] as RawNotification[];

    expect(transformNotifications(list).map((n) => n.id)).toEqual(['n1', 'n2']);
  });

  it('非陣列回傳空陣列', () => {
    expect(transformNotifications(null as unknown as RawNotification[])).toEqual([]);
  });

  it('保留列表回應的其他欄位', () => {
    const result = transformNotificationListResponse({ notifications: [RAW], unread_count: 3 });

    expect(result['unread_count']).toBe(3);
    expect(result.notifications).toHaveLength(1);
    expect(result.notifications[0]!.type).toBe('MESSAGE');
  });

  it('缺 notifications 時視為空列表', () => {
    const result = transformNotificationListResponse({} as { notifications: RawNotification[] });

    expect(result.notifications).toEqual([]);
  });
});

describe('transformNotificationStats', () => {
  it('對應後端欄位並將類型大寫', () => {
    expect(
      transformNotificationStats({
        total_count: 4,
        unread_count: 3,
        type_counts: { message: 3, system: 1 },
      })
    ).toEqual({ total: 4, unread: 3, by_type: { MESSAGE: 3, SYSTEM: 1 } });
  });

  it('缺欄位時為 0 與空物件', () => {
    expect(transformNotificationStats({})).toEqual({ total: 0, unread: 0, by_type: {} });
  });
});
