// 訊息輸入框：送出、輸入法選字、指令提示，以及失敗訊息的全部重試與清除
import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
import { messageList, messageStore } from '$lib/stores/message.svelte';
import { messageRetryManager } from '$lib/utils/messageRetry';
import type { Message } from '$lib/types';
import MessageInput from './MessageInput.svelte';

function setup() {
  const onSend = vi.fn();
  render(MessageInput, { onSend });
  const textarea = screen.getByPlaceholderText('輸入訊息...') as HTMLTextAreaElement;
  const type = (value: string) => fireEvent.input(textarea, { target: { value } });
  const press = (key: string, init: KeyboardEventInit = {}) => fireEvent.keyDown(textarea, { key, ...init });
  return { onSend, textarea, type, press };
}

function pendingMessage(clientId: string, overrides: Partial<Message> = {}): Message {
  return {
    id: clientId,
    client_id: clientId,
    room_id: 'r1',
    user_id: 'u1',
    content: `訊息 ${clientId}`,
    message_type: 'text',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

beforeEach(() => {
  messageRetryManager.clearAll();
  messageStore.clearMessages();
});

describe('送出', () => {
  it('按 Enter 送出：加入重試佇列、呼叫 onSend 並清空輸入框', async () => {
    const { onSend, textarea, type, press } = setup();

    await type('  哈囉  ');
    await press('Enter');

    expect(onSend).toHaveBeenCalledOnce();
    const sent = onSend.mock.calls[0]![0] as { content: string; type: string; messageId: string };
    expect(sent).toMatchObject({ content: '哈囉', type: 'text' });
    expect(messageRetryManager.isInQueue(sent.messageId)).toBe(true);
    expect(textarea.value).toBe('');
  });

  it('Shift+Enter 換行、只有空白時都不送出', async () => {
    const { onSend, type, press } = setup();

    await type('第一行');
    await press('Enter', { shiftKey: true });
    await type('   ');
    await press('Enter');

    expect(onSend).not.toHaveBeenCalled();
  });

  it('輸入法選字時按 Enter 不送出，選字結束後才送出', async () => {
    const { onSend, textarea, type, press } = setup();

    await fireEvent.compositionStart(textarea);
    await type('你好');
    await press('Enter');
    expect(onSend).not.toHaveBeenCalled();

    await fireEvent.compositionEnd(textarea);
    await press('Enter');
    expect(onSend).toHaveBeenCalledOnce();
  });

  it('輸入 / 時 Enter 選取指令提示，不送出', async () => {
    const { onSend, textarea, type, press } = setup();

    await type('/');
    expect(screen.getByRole('listbox', { name: '輸入提示' })).toBeTruthy();
    await press('Enter');

    expect(onSend).not.toHaveBeenCalled();
    expect(textarea.value.startsWith('/')).toBe(true);
    expect(textarea.value.length).toBeGreaterThan(1);
  });
});

describe('失敗的訊息', () => {
  it('顯示失敗數量與原因，全部重試會重送所有失敗訊息', async () => {
    const retryAllFailed = vi.spyOn(messageRetryManager, 'retryAllFailed').mockResolvedValue();
    messageStatusStore.setFailed('c1', '連線中斷，訊息未送達');
    setup();

    expect(screen.getByText(/1 則訊息發送失敗/)).toBeTruthy();
    expect(screen.getByText('(連線中斷，訊息未送達)')).toBeTruthy();

    await fireEvent.click(screen.getByRole('button', { name: '全部重試' }));
    expect(retryAllFailed).toHaveBeenCalledOnce();
  });

  it('清除時保留伺服器其實已收到的訊息', async () => {
    // 廣播或補發已帶回伺服器版本（id 已換成伺服器 id），只是沒收到 ack
    messageStore.addMessage(pendingMessage('c2', { id: 'srv-2' }));
    messageStatusStore.setFailed('c2', '連線中斷，訊息未送達');
    setup();

    await fireEvent.click(screen.getByRole('button', { name: '清除' }));

    expect(messageList().map((m) => m.id)).toEqual(['srv-2']);
  });
});
