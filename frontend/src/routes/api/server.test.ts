// 其餘 BFF 路由：WebSocket ticket、邀請碼驗證、AI 狀態
import { describe, expect, it } from 'vitest';
import * as wsTicket from './ws/ticket/+server';
import * as invitation from './invitations/validate/+server';
import * as aiStatus from './ai/status/+server';
import {
  backendError,
  FakeCookies,
  jsonRequest,
  makeEvent,
  mockBackend,
  tokenExpiringIn,
} from '../../tests/bff';

const authed = () => new FakeCookies({ auth_token: tokenExpiringIn(3600) });

async function body(response: Response) {
  return { status: response.status, ...(await response.json()) };
}

describe('POST /api/ws/ticket', () => {
  it('取得一次性 ticket', async () => {
    const backend = mockBackend({ 'POST /api/ws/ticket': () => ({ ticket: 't-123' }) });

    const result = await body(await wsTicket.POST(makeEvent({ cookies: authed(), request: jsonRequest('POST', { room_id: 'r1' }) })));

    expect(result.data).toEqual({ ticket: 't-123' });
    expect(backend).toHaveBeenCalledWith('/api/ws/ticket', expect.objectContaining({ data: { room_id: 'r1' } }));
  });

  it('缺少 room_id 時回 400', async () => {
    const backend = mockBackend({});

    const result = await body(await wsTicket.POST(makeEvent({ cookies: authed(), request: jsonRequest('POST', {}) })));

    expect(result.status).toBe(400);
    expect(backend).not.toHaveBeenCalled();
  });

  it('未登入時回 401', async () => {
    const result = await body(await wsTicket.POST(makeEvent({ request: jsonRequest('POST', { room_id: 'r1' }) })));

    expect(result).toMatchObject({ status: 401, error: { code: 'UNAUTHORIZED' } });
  });

  it('其他錯誤回 500，不洩漏後端細節', async () => {
    mockBackend({
      'POST /api/ws/ticket': () => {
        throw backendError(503, 'Redis connection refused');
      },
    });

    const result = await body(await wsTicket.POST(makeEvent({ cookies: authed(), request: jsonRequest('POST', { room_id: 'r1' }) })));

    expect(result).toMatchObject({ status: 500, error: { message: '取得 WebSocket ticket 失敗' } });
  });
});

describe('POST /api/invitations/validate', () => {
  const post = (data: unknown) => invitation.POST(makeEvent({ request: jsonRequest('POST', data) }));

  it('不需登入，將後端欄位轉成前端格式', async () => {
    const backend = mockBackend({
      'POST /api/invitations/validate': () => ({ valid: true, room_id: 'r1', room_name: '私人房', inviter_name: 'alice' }),
    });

    const result = await body(await post({ inviteCode: 'ABC123' }));

    expect(result.data).toEqual({ valid: true, room: { id: 'r1', name: '私人房', inviter_name: 'alice' } });
    expect(backend).toHaveBeenCalledWith('/api/invitations/validate', {
      method: 'POST',
      data: { invite_code: 'ABC123' },
    });
  });

  it('缺少邀請碼時回 400', async () => {
    mockBackend({});

    expect((await post({})).status).toBe(400);
  });

  it.each([
    [404, '邀請碼無效或已過期'],
    [400, '邀請碼已過期'],
  ])('後端 %i「%s」', async (code, message) => {
    mockBackend({
      'POST /api/invitations/validate': () => {
        throw backendError(code, message);
      },
    });

    expect(await body(await post({ inviteCode: 'X' }))).toMatchObject({
      status: code,
      error: { code: 'INVALID_INVITE', message },
    });
  });
});

describe('GET /api/ai/status', () => {
  it('代理後端狀態', async () => {
    mockBackend({ 'GET /api/ai/status': () => ({ enabled: true, bot_user_id: 'b1', bot_username: 'AI 助理' }) });

    const result = await body(await aiStatus.GET(makeEvent({ cookies: authed() })));

    expect(result.data).toEqual({ enabled: true, bot_user_id: 'b1', bot_username: 'AI 助理' });
  });

  it('未登入時回 401', async () => {
    expect((await aiStatus.GET(makeEvent({}))).status).toBe(401);
  });
});
