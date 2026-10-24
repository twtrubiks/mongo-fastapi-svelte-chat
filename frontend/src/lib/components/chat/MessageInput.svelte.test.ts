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

// 發送鍵只負責送出輸入框的內容；個別訊息的狀態與重試在訊息泡泡與「全部重試」
describe('發送鍵', () => {
  async function sendViaButton(type: (value: string) => Promise<unknown>, content: string) {
    await type(content);
    await fireEvent.click(screen.getByRole('button', { name: '發送' }));
  }

  it('上一則還在等伺服器確認時，仍可送出下一則', async () => {
    const { onSend, type } = setup();

    await sendViaButton(type, '第一則');
    messageStatusStore.setSending(onSend.mock.calls[0]![0].messageId);
    await sendViaButton(type, '第二則');

    expect(onSend.mock.calls.map(([sent]) => sent.content)).toEqual(['第一則', '第二則']);
  });

  it('上一則失敗時，按發送送出的是新打的內容，不是重送上一則', async () => {
    const manualRetry = vi.spyOn(messageRetryManager, 'manualRetry').mockResolvedValue(true);
    const { onSend, type } = setup();

    await sendViaButton(type, '第一則');
    messageStatusStore.setFailed(onSend.mock.calls[0]![0].messageId, '連線中斷，訊息未送達');
    await sendViaButton(type, '新的訊息');

    expect(onSend.mock.calls.map(([sent]) => sent.content)).toEqual(['第一則', '新的訊息']);
    expect(manualRetry).not.toHaveBeenCalled();
  });

  it('輸入框是空的時候不能按', () => {
    setup();

    expect((screen.getByRole('button', { name: '發送' }) as HTMLButtonElement).disabled).toBe(true);
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

  it('清除時移出重試佇列，並移除畫面上未送出的訊息', async () => {
    messageStore.addPendingMessage(pendingMessage('c1'));
    messageRetryManager.addToRetryQueue({ id: 'c1', content: '訊息 c1', type: 'text' });
    messageStatusStore.setFailed('c1', '訊息未送出，請重試');
    setup();

    await fireEvent.click(screen.getByRole('button', { name: '清除' }));

    expect(messageRetryManager.isInQueue('c1')).toBe(false);
    expect(messageStatusStore.getStatus('c1')).toBeUndefined();
    // 留著的話沒有任何狀態標示，看起來就像已送出
    expect(messageList().map((m) => m.client_id)).not.toContain('c1');
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
