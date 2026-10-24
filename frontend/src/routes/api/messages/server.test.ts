// 訊息編輯 / 刪除 / 搜尋 BFF 路由
import { describe, expect, it } from 'vitest';
import * as message from './[messageId]/+server';
import * as search from './room/[id]/search/+server';
import {
  backendError,
  FakeCookies,
  jsonRequest,
  makeEvent,
  mockBackend,
  tokenExpiringIn,
} from '../../../tests/bff';

function event(params: Record<string, string>, request?: Request) {
  return makeEvent({
    cookies: new FakeCookies({ auth_token: tokenExpiringIn(3600) }),
    params,
    ...(request && { request }),
  });
}

async function body(response: Response) {
  return { status: response.status, ...(await response.json()) };
}

describe('PUT /api/messages/[messageId]', () => {
  it('只轉送去除空白後的 content（不能順帶改 status 等欄位）', async () => {
    const backend = mockBackend({ 'PUT /api/messages/m1': () => ({ id: 'm1', content: '改過', edited: true }) });

    const result = await body(
      await message.PUT(event({ messageId: 'm1' }, jsonRequest('PUT', { content: '  改過 ', status: 'deleted' })))
    );

    expect(result.data).toEqual({ id: 'm1', content: '改過', edited: true });
    expect(backend).toHaveBeenCalledWith('/api/messages/m1', expect.objectContaining({
      method: 'PUT',
      data: { content: '改過' },
    }));
  });

  it.each([{}, { content: '  ' }, { content: 123 }])('內容無效時回 400：%o', async (data) => {
    const backend = mockBackend({});

    const result = await body(await message.PUT(event({ messageId: 'm1' }, jsonRequest('PUT', data))));

    expect(result).toMatchObject({ status: 400, error: { code: 'VALIDATION_ERROR' } });
    expect(backend).not.toHaveBeenCalled();
  });

  it('編輯他人訊息時沿用後端 403 並帶 messageId', async () => {
    mockBackend({
      'PUT /api/messages/m1': () => {
        throw backendError(403, '只能編輯自己的訊息');
      },
    });

    const result = await body(await message.PUT(event({ messageId: 'm1' }, jsonRequest('PUT', { content: 'x' }))));

    expect(result).toMatchObject({
      status: 403,
      error: { code: 'MESSAGE_UPDATE_ERROR', message: '只能編輯自己的訊息', details: { messageId: 'm1' } },
    });
  });
});

describe('DELETE /api/messages/[messageId]', () => {
  it('刪除訊息', async () => {
    mockBackend({ 'DELETE /api/messages/m1': () => ({ message: '訊息已刪除' }) });

    const result = await body(await message.DELETE(event({ messageId: 'm1' })));

    expect(result.data).toEqual({ success: true, message: '訊息已刪除', messageId: 'm1' });
  });

  it('訊息不存在時回 404', async () => {
    mockBackend({
      'DELETE /api/messages/m1': () => {
        throw backendError(404, '訊息不存在');
      },
    });

    const result = await body(await message.DELETE(event({ messageId: 'm1' })));

    expect(result).toMatchObject({ status: 404, error: { code: 'MESSAGE_DELETE_ERROR' } });
  });
});

describe('POST /api/messages/room/[id]/search', () => {
  it('轉送搜尋條件並回傳結果', async () => {
    const backend = mockBackend({ 'POST /api/messages/room/r1/search': () => [{ id: 'm1' }] });
    const query = { keyword: '會議', page: 1, page_size: 20 };

    const result = await body(await search.POST(event({ id: 'r1' }, jsonRequest('POST', query))));

    expect(result.data).toEqual([{ id: 'm1' }]);
    expect(backend).toHaveBeenCalledWith('/api/messages/room/r1/search', expect.objectContaining({ data: query }));
  });

  it('關鍵字格式錯誤時回傳後端訊息', async () => {
    mockBackend({
      'POST /api/messages/room/r1/search': () => {
        throw backendError(422, 'String should have at most 100 characters');
      },
    });

    const result = await body(await search.POST(event({ id: 'r1' }, jsonRequest('POST', { keyword: 'x'.repeat(101) }))));

    expect(result).toMatchObject({
      status: 422,
      error: { code: 'SEARCH_ERROR', message: 'String should have at most 100 characters' },
    });
  });
});
