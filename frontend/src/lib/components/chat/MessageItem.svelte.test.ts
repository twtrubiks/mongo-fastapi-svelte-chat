// 訊息泡泡：自己訊息的發送狀態、重試，以及編輯／刪除的顯示條件
import { fireEvent, render, screen } from '@testing-library/svelte';
import { flushSync } from 'svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
import { messageStore } from '$lib/stores/message.svelte';
import { messageRetryManager } from '$lib/utils/messageRetry';
import type { Message } from '$lib/types';
import MessageItem from './MessageItem.svelte';

function makeMessage(overrides: Partial<Message> = {}): Message {
  return {
    id: 'srv-1',
    room_id: 'r1',
    user_id: 'u1',
    username: 'alice',
    content: '哈囉',
    message_type: 'text',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

// 剛送出、尚未收到伺服器確認的訊息：id 仍是用戶端產生的 client_id
const pendingMessage = () => makeMessage({ id: 'c1', client_id: 'c1', pending: true });

function setStatus(update: () => void) {
  update();
  flushSync();
}

beforeEach(() => {
  messageStatusStore.clearAll();
});

describe('發送狀態', () => {
  it('依 client_id 顯示傳送中、已送達與傳送失敗', () => {
    render(MessageItem, { message: pendingMessage(), isCurrentUser: true });

    setStatus(() => messageStatusStore.setSending('c1'));
    expect(screen.getByText('傳送中')).toBeTruthy();

    setStatus(() => messageStatusStore.setFailed('c1', '伺服器未確認訊息，請重試'));
    expect(screen.getByText('⚠ 傳送失敗')).toBeTruthy();

    setStatus(() => messageStatusStore.setSent('c1'));
    expect(screen.getByText('✓ 已送達')).toBeTruthy();
    expect(screen.queryByText('⚠ 傳送失敗')).toBeNull();
  });

  it('收到確認、id 換成伺服器 id 後，仍以 client_id 對應狀態', () => {
    messageStatusStore.setSent('c1');

    render(MessageItem, { message: makeMessage({ id: 'srv-1', client_id: 'c1' }), isCurrentUser: true });

    expect(screen.getByText('✓ 已送達')).toBeTruthy();
  });

  it('傳送失敗時按重試，以 client_id 重送', async () => {
    const manualRetry = vi.spyOn(messageRetryManager, 'manualRetry').mockResolvedValue(true);
    messageStatusStore.setFailed('c1', '連線中斷，訊息未送達');
    render(MessageItem, { message: pendingMessage(), isCurrentUser: true });

    await fireEvent.click(screen.getByRole('button', { name: '重試' }));

    expect(manualRetry).toHaveBeenCalledWith('c1');
  });

  it('別人的訊息不顯示發送狀態', () => {
    messageStatusStore.setFailed('c1', '連線中斷，訊息未送達');

    render(MessageItem, { message: makeMessage({ client_id: 'c1', user_id: 'u2' }), isCurrentUser: false });

    expect(screen.queryByText('⚠ 傳送失敗')).toBeNull();
    expect(screen.queryByRole('button', { name: '重試' })).toBeNull();
  });
});

describe('編輯與刪除', () => {
  it('自己已送達的文字訊息可以編輯，儲存時以伺服器 id 呼叫 API', async () => {
    const editMessage = vi.spyOn(messageStore, 'editMessage').mockResolvedValue(makeMessage({ content: '改過了' }));
    render(MessageItem, { message: makeMessage(), isCurrentUser: true });

    await fireEvent.click(screen.getByRole('button', { name: '編輯訊息' }));
    await fireEvent.input(screen.getByRole('textbox', { name: '編輯訊息' }), { target: { value: '改過了' } });
    await fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(editMessage).toHaveBeenCalledWith('srv-1', '改過了');
  });

  it('編輯失敗時留在編輯狀態並顯示錯誤', async () => {
    vi.spyOn(messageStore, 'editMessage').mockRejectedValue(new Error('boom'));
    render(MessageItem, { message: makeMessage(), isCurrentUser: true });

    await fireEvent.click(screen.getByRole('button', { name: '編輯訊息' }));
    await fireEvent.input(screen.getByRole('textbox', { name: '編輯訊息' }), { target: { value: '改過了' } });
    await fireEvent.click(screen.getByRole('button', { name: '儲存' }));

    expect(await screen.findByText('編輯失敗，請稍後再試')).toBeTruthy();
    expect(screen.getByRole('textbox', { name: '編輯訊息' })).toBeTruthy();
  });

  it('刪除須先確認', async () => {
    const deleteMessage = vi.spyOn(messageStore, 'deleteMessage').mockResolvedValue();
    render(MessageItem, { message: makeMessage(), isCurrentUser: true });

    await fireEvent.click(screen.getByRole('button', { name: '刪除訊息' }));
    expect(deleteMessage).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button', { name: '刪除' }));

    expect(deleteMessage).toHaveBeenCalledWith('srv-1');
  });

  it('別人的訊息、圖片與檔案訊息不能編輯', () => {
    const { unmount } = render(MessageItem, { message: makeMessage({ user_id: 'u2' }), isCurrentUser: false });
    expect(screen.queryByRole('button', { name: '編輯訊息' })).toBeNull();
    expect(screen.queryByRole('button', { name: '刪除訊息' })).toBeNull();
    unmount();

    render(MessageItem, {
      message: makeMessage({ message_type: 'image', content: '/uploads/a.png' }),
      isCurrentUser: true,
    });
    expect(screen.queryByRole('button', { name: '編輯訊息' })).toBeNull();
    expect(screen.getByRole('button', { name: '刪除訊息' })).toBeTruthy();
  });

});
