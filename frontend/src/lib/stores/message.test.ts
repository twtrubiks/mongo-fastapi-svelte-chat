import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../api/client';
import type { Message } from '../types';
import { messageStore } from './message.svelte';
import { deferred } from '../../tests/deferred';

function msg(id: string, minute: number, extra: Partial<Message> = {}): Message {
  const at = new Date(Date.UTC(2026, 0, 1, 0, minute)).toISOString();
  return {
    id,
    room_id: 'r1',
    user_id: 'u1',
    content: `內容 ${id}`,
    message_type: 'text',
    created_at: at,
    updated_at: at,
    ...extra,
  };
}

const ids = () => messageStore.messages.map((m) => m.id);

beforeEach(() => {
  messageStore.clearMessages();
});

describe('addMessage', () => {
  it('依建立時間由舊到新排序', () => {
    messageStore.addMessage(msg('b', 2));
    messageStore.addMessage(msg('a', 1));
    messageStore.addMessage(msg('c', 3));

    expect(ids()).toEqual(['a', 'b', 'c']);
  });

  it('相同 id 不重複加入', () => {
    messageStore.addMessage(msg('a', 1));
    messageStore.addMessage(msg('a', 1, { content: '另一份' }));

    expect(messageStore.messages).toHaveLength(1);
    expect(messageStore.messages[0]!.content).toBe('內容 a');
  });

  it('以伺服器版本原地取代同 client_id 的樂觀訊息', () => {
    messageStore.addMessage(msg('a', 1));
    messageStore.addPendingMessage(msg('tmp-1', 5, { client_id: 'c1' }));
    messageStore.addMessage(msg('b', 3));

    messageStore.addMessage(msg('server-1', 4, { client_id: 'c1', seq: 9 }));

    expect(ids()).toEqual(['a', 'b', 'server-1']);
    expect(messageStore.messages[2]).toMatchObject({ seq: 9, pending: false });
  });
});

describe('樂觀訊息', () => {
  it('加入時標記 pending，重試不重複插入', () => {
    messageStore.addPendingMessage(msg('tmp-1', 1, { client_id: 'c1' }));
    messageStore.addPendingMessage(msg('tmp-1', 1, { client_id: 'c1' }));

    expect(messageStore.messages).toEqual([expect.objectContaining({ id: 'tmp-1', pending: true })]);
  });

  it('收到 ack 後換成伺服器 id 與 seq', () => {
    messageStore.addPendingMessage(msg('tmp-1', 1, { client_id: 'c1' }));

    messageStore.confirmMessage('c1', 'server-1', 42);

    expect(messageStore.messages[0]).toMatchObject({ id: 'server-1', seq: 42, pending: false, client_id: 'c1' });
  });

  it('ack 沒有 seq 時不覆寫成 undefined', () => {
    messageStore.addPendingMessage(msg('tmp-1', 1, { client_id: 'c1', seq: 7 }));

    messageStore.confirmMessage('c1', 'server-1');

    expect(messageStore.messages[0]!.seq).toBe(7);
  });

  it('未知 client_id 的 ack 不影響列表', () => {
    messageStore.addMessage(msg('a', 1));
    const before = messageStore.messages;

    messageStore.confirmMessage('nope', 'x');

    expect(messageStore.messages).toBe(before);
  });
});

describe('編輯與刪除事件', () => {
  it('依 id 合併編輯內容', () => {
    messageStore.addMessage(msg('a', 1));

    messageStore.applyEdit({ id: 'a', content: '改過', edited: true });

    expect(messageStore.messages[0]).toMatchObject({ id: 'a', content: '改過', edited: true, user_id: 'u1' });
  });

  it('找不到訊息時略過（冪等）', () => {
    messageStore.applyEdit({ id: 'missing', content: 'x' });
    messageStore.removeMessage('missing');

    expect(messageStore.messages).toEqual([]);
  });

  it('移除訊息', () => {
    messageStore.addMessage(msg('a', 1));
    messageStore.addMessage(msg('b', 2));

    messageStore.removeMessage('a');

    expect(ids()).toEqual(['b']);
  });

  it('editMessage 呼叫 API 後先在本地套用', async () => {
    messageStore.addMessage(msg('a', 1));
    vi.spyOn(apiClient.messages, 'update').mockResolvedValue(msg('a', 1, { content: '改過' }));

    await messageStore.editMessage('a', '改過');

    expect(apiClient.messages.update).toHaveBeenCalledWith('a', '改過');
    expect(messageStore.messages[0]).toMatchObject({ content: '改過', edited: true });
  });

  it('deleteMessage 失敗時保留訊息', async () => {
    messageStore.addMessage(msg('a', 1));
    vi.spyOn(apiClient.messages, 'delete').mockRejectedValue(new Error('403'));

    await expect(messageStore.deleteMessage('a')).rejects.toThrow('403');
    expect(ids()).toEqual(['a']);
  });
});

describe('bot streaming 預覽', () => {
  const bot = { id: 'bot', username: 'AI 助理' };

  it('累積增量成單一預覽', () => {
    messageStore.appendBotStream('r1', bot, '你');
    messageStore.appendBotStream('r1', bot, '好');

    expect(messageStore.messages).toEqual([
      expect.objectContaining({ id: 'bot-stream-r1', content: '你好', streaming: true, user_id: 'bot' }),
    ]);
  });

  it('正式訊息抵達後收掉同一 bot 的預覽', () => {
    messageStore.appendBotStream('r1', bot, '你好');
    const landed = msg('m1', 1, { user_id: 'bot', content: '你好', seq: 3 });

    messageStore.addMessage(landed);
    messageStore.resolveBotStreamOnLanding(landed);

    expect(ids()).toEqual(['m1']);
  });

  it('其他人的訊息不會收掉預覽', () => {
    messageStore.appendBotStream('r1', bot, '你好');
    const other = msg('m1', 1);

    messageStore.addMessage(other);
    messageStore.resolveBotStreamOnLanding(other);

    expect(ids()).toContain('bot-stream-r1');
  });

  it('bot 錯誤時收掉預覽', () => {
    messageStore.appendBotStream('r1', bot, '你');

    messageStore.clearBotStream('r1');

    expect(messageStore.messages).toEqual([]);
  });
});

describe('斷線重連補發', () => {
  it('增量補發合併並去重', () => {
    messageStore.addMessage(msg('a', 1, { seq: 1 }));

    messageStore.applySync([msg('a', 1, { seq: 1 }), msg('b', 2, { seq: 2 })], false);

    expect(ids()).toEqual(['a', 'b']);
  });

  it('gap 過大時整批重載', () => {
    messageStore.addMessage(msg('old', 1));

    messageStore.applySync([msg('x', 5), msg('y', 6)], true);

    expect(ids()).toEqual(['x', 'y']);
    expect(messageStore.hasMore).toBe(true);
  });

  it('getMaxSeq 只看指定房間的序號', () => {
    messageStore.addMessage(msg('a', 1, { seq: 5 }));
    messageStore.addMessage(msg('b', 2, { seq: 9, room_id: 'r2' }));
    messageStore.addMessage(msg('c', 3));

    expect(messageStore.getMaxSeq('r1')).toBe(5);
    expect(messageStore.getMaxSeq('r3')).toBeNull();
  });
});

describe('載入訊息', () => {
  it('第一頁滿 limit 筆表示可能還有更多', async () => {
    vi.spyOn(apiClient.messages, 'list').mockResolvedValue([msg('a', 1), msg('b', 2)]);

    await messageStore.loadMessages('r1', 2);

    expect(ids()).toEqual(['a', 'b']);
    expect(messageStore.hasMore).toBe(true);
    expect(messageStore.loading).toBe(false);
  });

  it('載入失敗時結束 loading 並拋出', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.spyOn(apiClient.messages, 'list').mockRejectedValue(new Error('down'));

    await expect(messageStore.loadMessages('r1')).rejects.toThrow('down');
    expect(messageStore.loading).toBe(false);
  });

  it('載入更多以最早訊息的 seq 為游標，並去重後接在前面', async () => {
    messageStore.applySync([msg('c', 3, { seq: 30 }), msg('d', 4, { seq: 40 })], true);
    const list = vi.spyOn(apiClient.messages, 'list').mockResolvedValue([msg('a', 1, { seq: 10 }), msg('c', 3, { seq: 30 })]);

    const added = await messageStore.loadMoreMessages('r1', 2);

    expect(list).toHaveBeenCalledWith('r1', 2, 2, 30);
    expect(added!.map((m) => m.id)).toEqual(['a']);
    expect(ids()).toEqual(['a', 'c', 'd']);
    expect(messageStore.hasMore).toBe(true);
  });

  it('沒有更多時不呼叫 API', async () => {
    vi.spyOn(apiClient.messages, 'list').mockResolvedValue([]);
    await messageStore.loadMessages('r1', 50);

    await messageStore.loadMoreMessages('r1');

    expect(apiClient.messages.list).toHaveBeenCalledOnce();
  });

  // 第一頁載入失敗後列表為空、hasMore 仍為 true，捲到頂端會觸發載入更多
  it('列表為空時載入更多不會卡在 loading', async () => {
    const list = vi.spyOn(apiClient.messages, 'list');

    await messageStore.loadMoreMessages('r1');

    expect(list).not.toHaveBeenCalled();
    expect(messageStore.loading).toBe(false);
  });

  // 快速切換房間：A 的回應比 B 晚回來
  it('較早發出、較晚回來的回應不覆蓋目前房間的訊息', async () => {
    const roomA = deferred<Message[]>();
    vi.spyOn(apiClient.messages, 'list').mockImplementation((roomId) =>
      roomId === 'A' ? roomA.promise : Promise.resolve([msg('b1', 1, { room_id: 'B' })]));

    const loadA = messageStore.loadMessages('A');
    await messageStore.loadMessages('B');
    roomA.resolve([msg('a1', 1, { room_id: 'A' })]);
    await loadA;

    expect(ids()).toEqual(['b1']);
    expect(messageStore.loading).toBe(false);
  });

  it('較早發出、較晚失敗的請求不影響目前的載入狀態', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const roomA = deferred<Message[]>();
    const roomB = deferred<Message[]>();
    vi.spyOn(apiClient.messages, 'list').mockImplementation((roomId) => (roomId === 'A' ? roomA.promise : roomB.promise));

    const loadA = messageStore.loadMessages('A');
    const loadB = messageStore.loadMessages('B');
    roomA.reject(new Error('down'));
    await expect(loadA).rejects.toThrow('down');
    expect(messageStore.loading).toBe(true);

    roomB.resolve([msg('b1', 1, { room_id: 'B' })]);
    await loadB;
    expect(ids()).toEqual(['b1']);
    expect(messageStore.loading).toBe(false);
  });

  it('切換房間後，前一個房間「載入更多」的結果不併入', async () => {
    messageStore.applySync([msg('a2', 2, { room_id: 'A', seq: 2 })], true);
    const older = deferred<Message[]>();
    vi.spyOn(apiClient.messages, 'list').mockImplementation((roomId) =>
      roomId === 'A' ? older.promise : Promise.resolve([msg('b1', 1, { room_id: 'B' })]));

    const more = messageStore.loadMoreMessages('A');
    await messageStore.loadMessages('B');
    older.resolve([msg('a1', 1, { room_id: 'A', seq: 1 })]);
    await more;

    expect(ids()).toEqual(['b1']);
    expect(messageStore.loading).toBe(false);
  });
});
