// 訊息列表：日期分組、連續訊息合併、打字提示、往上捲載入舊訊息，
// 以及不在底部時收到新訊息的預覽卡與自動捲動
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { authStore } from '$lib/stores/auth.svelte';
import { messageStore } from '$lib/stores/message.svelte';
import type { Message, User } from '$lib/types';
import MessageList from './MessageList.svelte';

function makeMessage(id: string, userId: string, createdAt: string, overrides: Partial<Message> = {}): Message {
  return {
    id,
    room_id: 'r1',
    user_id: userId,
    username: userId === 'me' ? '我' : `user-${userId}`,
    content: `訊息 ${id}`,
    message_type: 'text',
    created_at: createdAt,
    updated_at: createdAt,
    ...overrides,
  };
}

// jsdom 沒有排版：以可調整的尺寸模擬捲動容器，scrollTo 依內容高度夾住捲動位置
const geometry = { scrollHeight: 1000, clientHeight: 300, scrollTop: 0 };
const scrollTo = vi.fn(function (this: HTMLElement, options?: ScrollToOptions | number) {
  const top = typeof options === 'number' ? options : (options?.top ?? 0);
  geometry.scrollTop = Math.max(0, Math.min(top, geometry.scrollHeight - geometry.clientHeight));
});
const scrollIntoView = vi.fn();

class FakeResizeObserver {
  observe() {}
  disconnect() {}
}

function listContainer(container: HTMLElement) {
  const el = container.querySelector<HTMLDivElement>('.message-list')!;
  Object.defineProperties(el, {
    scrollHeight: { configurable: true, get: () => geometry.scrollHeight },
    clientHeight: { configurable: true, get: () => geometry.clientHeight },
    scrollTop: {
      configurable: true,
      get: () => geometry.scrollTop,
      set: (value: number) => { geometry.scrollTop = value; },
    },
  });
  return el;
}

function setup(props: Record<string, unknown> = {}) {
  const { container, rerender, component } = render(MessageList, { roomId: 'r1', hasMore: false, ...props });
  return { list: listContainer(container), rerender, component };
}

const settle = () => vi.advanceTimersByTimeAsync(400);

// 使用者往上捲離底部
async function scrollUp(list: HTMLElement, to = 100) {
  geometry.scrollTop = to;
  await fireEvent.scroll(list);
  await settle();
}

const T = (minute: number) => `2026-01-01T12:${String(minute).padStart(2, '0')}:00Z`;

beforeEach(() => {
  vi.useFakeTimers();
  Object.assign(geometry, { scrollHeight: 1000, clientHeight: 300, scrollTop: 0 });
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
  Element.prototype.scrollTo = scrollTo as unknown as Element['scrollTo'];
  Element.prototype.scrollIntoView = scrollIntoView;
  authStore.setAuthState({ user: { id: 'me', username: '我' } as User });
});

afterEach(() => {
  vi.useRealTimers();
});

describe('顯示', () => {
  it('載入中且沒有訊息時顯示載入提示，沒有訊息時顯示空狀態', () => {
    const { unmount } = render(MessageList, { roomId: 'r1', loading: true, messages: [] });
    expect(screen.getByText('載入訊息中...')).toBeTruthy();
    unmount();

    render(MessageList, { roomId: 'r1', messages: [] });
    expect(screen.getByText('還沒有訊息')).toBeTruthy();
  });

  it('依日期分組，舊的日期在前，同一天依時間排序', () => {
    const { list } = setup({
      messages: [
        makeMessage('b', 'u2', '2026-01-02T12:00:00Z'),
        makeMessage('a2', 'u2', '2026-01-01T12:30:00Z'),
        makeMessage('a1', 'u3', '2026-01-01T12:00:00Z'),
      ],
    });

    expect([...list.querySelectorAll('.divider')].map((d) => d.textContent?.trim())).toEqual(['2026-01-01', '2026-01-02']);
    expect([...list.querySelectorAll('[data-message-id]')].map((m) => m.getAttribute('data-message-id'))).toEqual(['a1', 'a2', 'b']);
  });

  it('同一人連續的訊息只在第一則顯示名稱；自己的訊息靠右顯示', () => {
    const { list } = setup({
      messages: [
        makeMessage('1', 'u2', T(0)),
        makeMessage('2', 'u2', T(1)),
        makeMessage('3', 'me', T(2)),
        makeMessage('4', 'u2', T(3)),
      ],
    });

    expect(screen.getAllByText('user-u2', { selector: '.message-username' })).toHaveLength(2);
    const items = [...list.querySelectorAll('.message-item')];
    expect(items.map((item) => item.classList.contains('compact'))).toEqual([false, true, false, false]);
    expect(items.map((item) => item.classList.contains('message-own'))).toEqual([false, false, true, false]);
  });

  it.each([
    [[{ userId: 'u2', username: 'bob' }], 'bob 正在輸入...'],
    [[{ userId: 'u2', username: 'bob' }, { userId: 'u3', username: 'carol' }], 'bob 和 carol 正在輸入...'],
    [
      [{ userId: 'u2', username: 'bob' }, { userId: 'u3', username: 'carol' }, { userId: 'u4', username: 'dave' }],
      'bob 和其他 2 人正在輸入...',
    ],
  ])('打字提示：%#', (typingUsers, text) => {
    setup({ messages: [makeMessage('1', 'u2', T(0))], typingUsers });

    expect(screen.getByText(text)).toBeTruthy();
  });
});

describe('載入舊訊息', () => {
  it('捲到頂端時載入更早的訊息，並保持目前看到的位置', async () => {
    const loadMore = vi.spyOn(messageStore, 'loadMoreMessages').mockImplementation(async () => {
      geometry.scrollHeight = 1600; // 上方多出 600px 的舊訊息
    });
    const { list } = setup({ hasMore: true, messages: [makeMessage('1', 'u2', T(0))] });

    await scrollUp(list, 0);

    expect(loadMore).toHaveBeenCalledWith('r1', 20);
    expect(geometry.scrollTop).toBe(600);
  });

  it('沒有更多訊息或正在載入時不再請求', async () => {
    const loadMore = vi.spyOn(messageStore, 'loadMoreMessages').mockResolvedValue([]);
    const { list, rerender } = setup({ hasMore: false, messages: [makeMessage('1', 'u2', T(0))] });

    await scrollUp(list, 0);
    await rerender({ hasMore: true, loading: true });
    await scrollUp(list, 0);

    expect(loadMore).not.toHaveBeenCalled();
  });
});

describe('新訊息', () => {
  const history = [makeMessage('1', 'u2', T(0)), makeMessage('2', 'u3', T(1))];

  it('在底部時收到新訊息會自動捲到最新', async () => {
    const { rerender } = setup({ messages: history });
    await settle();
    geometry.scrollHeight = 1200;
    scrollTo.mockClear();

    await rerender({ messages: [...history, makeMessage('3', 'u2', T(2))] });
    await settle();

    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 1200 }));
    expect(screen.queryByRole('button', { name: '跳至最新訊息' })).toBeNull();
  });

  it('往上看舊訊息時收到別人的新訊息：不打斷閱讀，顯示預覽卡與未讀數，點擊跳到最新', async () => {
    const { list, rerender } = setup({ messages: history });
    await settle();
    await scrollUp(list);
    expect(screen.getByRole('button', { name: '滾動到底部' })).toBeTruthy();
    scrollTo.mockClear();

    const third = makeMessage('3', 'u2', T(2), { content: '有人在嗎' });
    await rerender({ messages: [...history, third] });
    await settle();

    const preview = screen.getByRole('button', { name: '跳至最新訊息' });
    expect(preview.textContent).toContain('user-u2');
    expect(preview.textContent).toContain('有人在嗎');
    expect(scrollTo).not.toHaveBeenCalled();
    expect(geometry.scrollTop).toBe(100);

    await rerender({ messages: [...history, third, makeMessage('4', 'u3', T(3))] });
    await settle();
    expect(screen.getByRole('button', { name: '跳至最新訊息' }).textContent).toContain('2');

    await fireEvent.click(screen.getByRole('button', { name: '跳至最新訊息' }));
    await settle();
    expect(geometry.scrollTop).toBe(geometry.scrollHeight - geometry.clientHeight);
    expect(screen.queryByRole('button', { name: '跳至最新訊息' })).toBeNull();
  });

  it('往上看舊訊息時自己送出訊息，直接捲到最新', async () => {
    const { list, rerender } = setup({ messages: history });
    await settle();
    await scrollUp(list);

    await rerender({ messages: [...history, makeMessage('3', 'me', T(2))] });
    await settle();

    expect(geometry.scrollTop).toBe(geometry.scrollHeight - geometry.clientHeight);
    expect(screen.queryByRole('button', { name: '跳至最新訊息' })).toBeNull();
  });

  it('載入更早的訊息（加在前面）不算新訊息，不顯示預覽卡', async () => {
    const { list, rerender } = setup({ messages: history });
    await settle();
    await scrollUp(list);

    await rerender({ messages: [makeMessage('0', 'u3', '2026-01-01T11:00:00Z'), ...history] });
    await settle();

    expect(screen.queryByRole('button', { name: '跳至最新訊息' })).toBeNull();
    expect(screen.getByRole('button', { name: '滾動到底部' })).toBeTruthy();
  });

  // 訊息被刪除（或 bot 回覆失敗收掉預覽）會讓數量變少，之後的新訊息仍要被偵測到
  it('有訊息被刪除後，之後收到的新訊息仍會顯示預覽卡', async () => {
    const { list, rerender } = setup({ messages: history });
    await settle();
    await scrollUp(list);

    await rerender({ messages: [history[0]!] });
    await settle();
    await rerender({ messages: [history[0]!, makeMessage('3', 'u2', T(2), { content: '刪除後的新訊息' })] });
    await settle();

    expect(screen.getByRole('button', { name: '跳至最新訊息' }).textContent).toContain('刪除後的新訊息');
  });

  it('在底部時有訊息被刪除，之後的新訊息仍會自動捲到最新', async () => {
    const { rerender } = setup({ messages: history });
    await settle();

    await rerender({ messages: [history[0]!] });
    await settle();
    geometry.scrollHeight = 1200;
    scrollTo.mockClear();
    await rerender({ messages: [history[0]!, makeMessage('3', 'u2', T(2))] });
    await settle();

    expect(scrollTo).toHaveBeenCalledWith(expect.objectContaining({ top: 1200 }));
  });
});

describe('捲到指定訊息', () => {
  it('找到訊息時捲過去並短暫標示，找不到時回傳 false', async () => {
    const { list, component } = setup({ messages: [makeMessage('1', 'u2', T(0)), makeMessage('2', 'u3', T(1))] });
    const scroller = component as unknown as { scrollToMessage: (id: string) => boolean };

    expect(scroller.scrollToMessage('2')).toBe(true);
    const target = list.querySelector('[data-message-id="2"]')!;
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' });
    expect(target.classList.contains('highlight-message')).toBe(true);

    await vi.advanceTimersByTimeAsync(3000);
    expect(target.classList.contains('highlight-message')).toBe(false);
    expect(scroller.scrollToMessage('missing')).toBe(false);
  });
});
