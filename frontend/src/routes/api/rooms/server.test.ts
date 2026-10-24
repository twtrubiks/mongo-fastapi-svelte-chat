// 房間與房間訊息相關 BFF 路由
import { describe, expect, it } from 'vitest';
import * as rooms from './+server';
import * as my from './my/+server';
import * as room from './[id]/+server';
import * as join from './[id]/join/+server';
import * as joinAdvanced from './[id]/join-advanced/+server';
import * as leave from './[id]/leave/+server';
import * as members from './[id]/members/+server';
import * as member from './[id]/members/[userId]/+server';
import * as inviteCode from './[id]/invite-code/+server';
import * as bans from './[id]/bans/+server';
import * as ban from './[id]/bans/[userId]/+server';
import * as messages from './[id]/messages/+server';
import {
  backendError,
  FakeCookies,
  jsonRequest,
  makeEvent,
  mockBackend,
  tokenExpiringIn,
} from '../../../tests/bff';

const ROOM = { id: 'r1', name: '大廳', is_member: true, member_count: 3 };

function event(init: { url?: string; params?: Record<string, string>; request?: Request } = {}) {
  return makeEvent({ cookies: new FakeCookies({ auth_token: tokenExpiringIn(3600) }), ...init });
}

function throws(code: number, message: string) {
  return () => {
    throw backendError(code, message);
  };
}

async function body(response: Response) {
  return { status: response.status, ...(await response.json()) };
}

describe('GET /api/rooms', () => {
  it('沒有參數時直接轉送', async () => {
    mockBackend({ 'GET /api/rooms': () => [ROOM] });

    expect((await body(await rooms.GET(event({ url: '/api/rooms' })))).data).toEqual([ROOM]);
  });

  it('offset 對應後端 skip，並轉送搜尋與探索條件', async () => {
    const backend = mockBackend({
      'GET /api/rooms?limit=20&skip=40&search=%E5%A4%A7&exclude_joined=true': () => [],
    });

    await rooms.GET(event({ url: '/api/rooms?limit=20&offset=40&search=大&exclude_joined=true' }));

    expect(backend).toHaveBeenCalledOnce();
  });
});

describe('POST /api/rooms', () => {
  it('建立房間回 201', async () => {
    const backend = mockBackend({ 'POST /api/rooms/': (options) => ({ ...ROOM, ...(options.data as object) }) });

    const result = await body(await rooms.POST(event({ request: jsonRequest('POST', { name: '新房間' }) })));

    expect(result).toMatchObject({ status: 201, success: true, data: { name: '新房間' } });
    expect(backend).toHaveBeenCalledOnce();
  });

  it('缺少名稱時回 400 且不呼叫後端', async () => {
    const backend = mockBackend({});

    const result = await body(await rooms.POST(event({ request: jsonRequest('POST', { description: 'x' }) })));

    expect(result).toMatchObject({ status: 400, error: { code: 'VALIDATION_ERROR' } });
    expect(backend).not.toHaveBeenCalled();
  });

  it('名稱重複時沿用後端 409', async () => {
    mockBackend({ 'POST /api/rooms/': throws(409, '房間名稱已存在: 大廳') });

    const result = await body(await rooms.POST(event({ request: jsonRequest('POST', { name: '大廳' }) })));

    expect(result).toMatchObject({ status: 409, error: { message: '房間名稱已存在: 大廳' } });
  });
});

describe('GET /api/rooms/my', () => {
  it('預設第一頁 50 筆', async () => {
    const backend = mockBackend({ 'GET /api/rooms/my?limit=50&skip=0': () => [ROOM] });

    await my.GET(event({ url: '/api/rooms/my' }));

    expect(backend).toHaveBeenCalledOnce();
  });
});

describe('/api/rooms/[id]', () => {
  const params = { id: 'r1' };

  it('取得房間', async () => {
    mockBackend({ 'GET /api/rooms/r1': () => ROOM });

    expect((await body(await room.GET(event({ params })))).data).toEqual(ROOM);
  });

  it('錯誤帶上 roomId', async () => {
    mockBackend({ 'GET /api/rooms/r1': throws(404, '房間不存在') });

    const result = await body(await room.GET(event({ params })));

    expect(result).toMatchObject({
      status: 404,
      error: { code: 'ROOM_ERROR', message: '房間不存在', details: { roomId: 'r1' } },
    });
  });

  it('更新房間', async () => {
    const backend = mockBackend({ 'PUT /api/rooms/r1': () => ROOM });

    await room.PUT(event({ params, request: jsonRequest('PUT', { description: '新描述' }) }));

    expect(backend).toHaveBeenCalledWith('/api/rooms/r1', expect.objectContaining({ data: { description: '新描述' } }));
  });

  it('名稱只有空白時回 400', async () => {
    const backend = mockBackend({});

    const result = await body(await room.PUT(event({ params, request: jsonRequest('PUT', { name: '   ' }) })));

    expect(result.status).toBe(400);
    expect(backend).not.toHaveBeenCalled();
  });

  it('刪除房間', async () => {
    mockBackend({ 'DELETE /api/rooms/r1': () => ({ message: 'ok' }) });

    const result = await body(await room.DELETE(event({ params })));

    expect(result.data).toEqual({ success: true, message: '房間已刪除', roomId: 'r1' });
  });

  it('非房主刪除時沿用後端 403', async () => {
    mockBackend({ 'DELETE /api/rooms/r1': throws(403, '只有房主可以刪除房間') });

    const result = await body(await room.DELETE(event({ params })));

    expect(result).toMatchObject({ status: 403, error: { code: 'ROOM_DELETE_ERROR' } });
  });
});

describe('加入與離開', () => {
  const params = { id: 'r1' };

  it.each([
    ['沒有 body', undefined, {}],
    ['body 不是 JSON', 'oops', {}],
    ['帶密碼', JSON.stringify({ password: 'pw' }), { password: 'pw' }],
  ])('POST /join（%s）', async (_, raw, data) => {
    const backend = mockBackend({ 'POST /api/rooms/r1/join': () => ({ message: '成功加入房間' }) });
    const request = new Request('http://localhost/', { method: 'POST', ...(raw !== undefined && { body: raw }) });

    const result = await body(await join.POST(event({ params, request })));

    expect(result.data).toEqual({ message: '成功加入房間' });
    expect(backend).toHaveBeenCalledWith('/api/rooms/r1/join', expect.objectContaining({ data }));
  });

  it('POST /leave', async () => {
    mockBackend({ 'POST /api/rooms/r1/leave': () => ({ message: '已離開房間' }) });

    expect((await body(await leave.POST(event({ params })))).data).toEqual({ message: '已離開房間' });
  });

  it('房主離開時沿用後端錯誤', async () => {
    mockBackend({ 'POST /api/rooms/r1/leave': throws(400, '房主不能離開房間') });

    const result = await body(await leave.POST(event({ params })));

    expect(result).toMatchObject({ status: 400, error: { code: 'LEAVE_ERROR', message: '房主不能離開房間' } });
  });
});

describe('POST /api/rooms/[id]/join-advanced', () => {
  const params = { id: 'r1' };
  const post = (data: unknown) => joinAdvanced.POST(event({ params, request: jsonRequest('POST', data) }));

  it('加入成功後回傳房間（私人房間加入後才能讀取）', async () => {
    const backend = mockBackend({
      'POST /api/rooms/r1/join': () => ({ message: '成功加入房間' }),
      'GET /api/rooms/r1': () => ROOM,
    });

    const result = await body(await post({ password: 'pw' }));

    expect(result.data).toEqual({ success: true, message: '成功加入聊天室', room: ROOM });
    expect(backend.mock.calls.map(([endpoint]) => endpoint)).toEqual(['/api/rooms/r1/join', '/api/rooms/r1']);
  });

  // 訊息字串與後端 RoomService.join_room 一致
  it.each([
    ['需要提供密碼', { type: 'password', message: '此聊天室需要密碼才能加入' }],
    ['密碼錯誤', { type: 'error', message: '密碼錯誤' }],
    ['需要提供邀請碼', { type: 'invite_code', message: '此聊天室需要邀請碼才能加入' }],
    ['邀請碼無效', { type: 'error', message: '邀請碼無效' }],
    ['邀請碼已過期', { type: 'error', message: '邀請碼已過期' }],
  ])('後端「%s」轉成需要使用者處理的回應', async (message, requiresAction) => {
    mockBackend({ 'POST /api/rooms/r1/join': throws(400, message) });

    const result = await body(await post({}));

    expect(result).toMatchObject({ status: 200, data: { success: false, message, requiresAction } });
  });

  it('房間已滿回 ROOM_FULL', async () => {
    mockBackend({ 'POST /api/rooms/r1/join': throws(400, '房間已滿') });

    expect(await body(await post({}))).toMatchObject({ status: 400, error: { code: 'ROOM_FULL' } });
  });

  it('其他錯誤沿用後端狀態碼', async () => {
    mockBackend({ 'POST /api/rooms/r1/join': throws(403, '該房間不允許直接加入') });

    expect(await body(await post({}))).toMatchObject({
      status: 403,
      error: { code: 'JOIN_ERROR', message: '該房間不允許直接加入' },
    });
  });
});

describe('GET /api/rooms/[id]/join-advanced', () => {
  const params = { id: 'r1' };

  it('已是成員', async () => {
    mockBackend({ 'GET /api/rooms/r1': () => ROOM });

    expect((await body(await joinAdvanced.GET(event({ params })))).data).toMatchObject({ isMember: true, room: ROOM });
  });

  it.each([
    [{ join_policy: 'direct', room_type: 'public' }, { canDirectJoin: true, needsPassword: false, needsInviteCode: false }],
    [{ join_policy: 'password', room_type: 'public' }, { canDirectJoin: false, needsPassword: true, needsInviteCode: false }],
    [{ join_policy: 'invite', room_type: 'private' }, { canDirectJoin: false, needsPassword: false, needsInviteCode: true }],
  ])('非成員依加入策略回傳需求 %o', async (policy, requirements) => {
    mockBackend({
      'GET /api/rooms/r1': () => ({ id: 'r1', name: '大廳', is_member: false, has_password: false, ...policy }),
    });

    const data = (await body(await joinAdvanced.GET(event({ params })))).data;

    expect(data).toEqual({
      isMember: false,
      room: {
        id: 'r1',
        name: '大廳',
        room_type: policy.room_type,
        join_policy: policy.join_policy,
        has_password: false,
        member_count: 0,
      },
      requirements,
    });
  });
});

describe('GET /api/rooms/[id]/members', () => {
  it('預設 100 筆，offset 對應 skip', async () => {
    const backend = mockBackend({ 'GET /api/rooms/r1/members?limit=100&skip=0': () => [] });

    await members.GET(event({ params: { id: 'r1' }, url: '/api/rooms/r1/members' }));

    expect(backend).toHaveBeenCalledOnce();
  });

  it('轉送分頁參數', async () => {
    const backend = mockBackend({ 'GET /api/rooms/r1/members?limit=20&skip=40': () => [] });

    await members.GET(event({ params: { id: 'r1' }, url: '/api/rooms/r1/members?limit=20&offset=40' }));

    expect(backend).toHaveBeenCalledOnce();
  });
});

describe('房主撤銷權限', () => {
  it('POST /invite-code 回傳新的邀請碼', async () => {
    mockBackend({ 'POST /api/rooms/r1/invite-code': () => ({ invite_code: 'new-code' }) });

    const result = await body(await inviteCode.POST(event({ params: { id: 'r1' } })));

    expect(result).toMatchObject({ status: 200, data: { invite_code: 'new-code' } });
  });

  it('非房主重新產生邀請碼時沿用後端 403', async () => {
    mockBackend({ 'POST /api/rooms/r1/invite-code': throws(403, '只有房間擁有者可以重新產生邀請碼') });

    const result = await body(await inviteCode.POST(event({ params: { id: 'r1' } })));

    expect(result).toMatchObject({
      status: 403,
      error: { code: 'INVITE_CODE_ERROR', message: '只有房間擁有者可以重新產生邀請碼' },
    });
  });

  it('DELETE /members/[userId] 移除成員', async () => {
    const backend = mockBackend({ 'DELETE /api/rooms/r1/members/u2': () => ({ message: '已將成員移出房間' }) });

    const result = await body(await member.DELETE(event({ params: { id: 'r1', userId: 'u2' } })));

    expect(result).toMatchObject({ status: 200, data: { message: '已將成員移出房間' } });
    expect(backend).toHaveBeenCalledOnce();
  });

  it('移除房主時沿用後端 403', async () => {
    mockBackend({ 'DELETE /api/rooms/r1/members/u1': throws(403, '不能移除房間擁有者') });

    const result = await body(await member.DELETE(event({ params: { id: 'r1', userId: 'u1' } })));

    expect(result).toMatchObject({
      status: 403,
      error: { code: 'REMOVE_MEMBER_ERROR', message: '不能移除房間擁有者' },
    });
  });

  it('DELETE /members/[userId]?ban=true 移出並封鎖', async () => {
    const backend = mockBackend({
      'DELETE /api/rooms/r1/members/u2?ban=true': () => ({ message: '已將成員移出並封鎖' }),
    });

    const result = await body(
      await member.DELETE(event({ params: { id: 'r1', userId: 'u2' }, url: '/api/rooms/r1/members/u2?ban=true' })),
    );

    expect(result).toMatchObject({ status: 200, data: { message: '已將成員移出並封鎖' } });
    expect(backend).toHaveBeenCalledOnce();
  });

  it('GET /bans 回傳封鎖名單', async () => {
    mockBackend({ 'GET /api/rooms/r1/bans': () => [{ id: 'u2', username: 'bob' }] });

    const result = await body(await bans.GET(event({ params: { id: 'r1' } })));

    expect(result).toMatchObject({ status: 200, data: [{ id: 'u2', username: 'bob' }] });
  });

  it('非房主查看封鎖名單時沿用後端 403', async () => {
    mockBackend({ 'GET /api/rooms/r1/bans': throws(403, '只有房間擁有者可以查看封鎖名單') });

    const result = await body(await bans.GET(event({ params: { id: 'r1' } })));

    expect(result).toMatchObject({
      status: 403,
      error: { code: 'BANS_ERROR', message: '只有房間擁有者可以查看封鎖名單' },
    });
  });

  it('DELETE /bans/[userId] 解除封鎖', async () => {
    const backend = mockBackend({ 'DELETE /api/rooms/r1/bans/u2': () => ({ message: '已解除封鎖' }) });

    const result = await body(await ban.DELETE(event({ params: { id: 'r1', userId: 'u2' } })));

    expect(result).toMatchObject({ status: 200, data: { message: '已解除封鎖' } });
    expect(backend).toHaveBeenCalledOnce();
  });

  it('解除不在封鎖名單中的使用者時沿用後端 404', async () => {
    mockBackend({ 'DELETE /api/rooms/r1/bans/u3': throws(404, '該使用者不在封鎖名單中') });

    const result = await body(await ban.DELETE(event({ params: { id: 'r1', userId: 'u3' } })));

    expect(result).toMatchObject({
      status: 404,
      error: { code: 'UNBAN_ERROR', message: '該使用者不在封鎖名單中' },
    });
  });
});

describe('/api/rooms/[id]/messages', () => {
  const params = { id: 'r1' };

  it('GET 預設第一頁 50 筆', async () => {
    const backend = mockBackend({ 'GET /api/rooms/r1/messages?limit=50&skip=0': () => [] });

    await messages.GET(event({ params, url: '/api/rooms/r1/messages' }));

    expect(backend).toHaveBeenCalledOnce();
  });

  it('GET 以 before_seq 游標分頁', async () => {
    const backend = mockBackend({ 'GET /api/rooms/r1/messages?limit=30&skip=0&before_seq=120': () => [] });

    await messages.GET(event({ params, url: '/api/rooms/r1/messages?limit=30&before_seq=120' }));

    expect(backend).toHaveBeenCalledOnce();
  });

  it('非成員讀取時沿用後端 403', async () => {
    mockBackend({ 'GET /api/rooms/r1/messages?limit=50&skip=0': throws(403, '您不是此房間的成員') });

    const result = await body(await messages.GET(event({ params, url: '/api/rooms/r1/messages' })));

    expect(result).toMatchObject({ status: 403, error: { code: 'MESSAGES_ERROR', details: { roomId: 'r1' } } });
  });

  it('POST 去除前後空白並補齊預設欄位', async () => {
    const backend = mockBackend({ 'POST /api/rooms/r1/messages': (options) => ({ id: 'm1', ...(options.data as object) }) });

    await messages.POST(event({ params, request: jsonRequest('POST', { content: '  嗨  ' }) }));

    expect(backend).toHaveBeenCalledWith('/api/rooms/r1/messages', expect.objectContaining({
      method: 'POST',
      data: { content: '嗨', message_type: 'text', room_id: 'r1', metadata: {}, client_id: null },
    }));
  });

  it('POST 轉送訊息類型、metadata 與 client_id（相容舊欄位 type）', async () => {
    const backend = mockBackend({ 'POST /api/rooms/r1/messages': () => ({ id: 'm1' }) });

    await messages.POST(event({
      params,
      request: jsonRequest('POST', { content: '圖', type: 'image', metadata: { url: '/f' }, client_id: 'c1' }),
    }));

    expect(backend.mock.calls[0]![1]!.data).toEqual({
      content: '圖',
      message_type: 'image',
      room_id: 'r1',
      metadata: { url: '/f' },
      client_id: 'c1',
    });
  });

  it.each([{}, { content: '   ' }])('POST 內容為空時回 400：%o', async (data) => {
    const backend = mockBackend({});

    const result = await body(await messages.POST(event({ params, request: jsonRequest('POST', data) })));

    expect(result.status).toBe(400);
    expect(backend).not.toHaveBeenCalled();
  });
});
