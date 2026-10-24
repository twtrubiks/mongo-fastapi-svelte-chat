// WebSocket 連線管理：建立連線、重連退避、心跳、ack 逾時、重疊的連線請求
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { apiClient } from '$lib/api/client';
import { messageStore } from '$lib/stores/message.svelte';
import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
import type { Message } from '$lib/types';
import { deferred } from '../../tests/deferred';
import { WebSocketManager } from './manager';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

type CloseEventInit = { code: number; reason: string; wasClean: boolean };

// 以測試驅動的 WebSocket：由測試決定何時開啟、收到訊息與關閉
class FakeWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  readyState = FakeWebSocket.CONNECTING;
  sent: Array<Record<string, unknown>> = [];
  closeCalls: Array<{ code: number | undefined; reason: string | undefined }> = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: CloseEventInit) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(JSON.parse(data));
  }

  close(code?: number, reason?: string) {
    this.closeCalls.push({ code, reason });
    if (this.readyState < FakeWebSocket.CLOSING) this.readyState = FakeWebSocket.CLOSING;
  }

  serverOpen() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  serverSend(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  serverClose(code: number, wasClean: boolean) {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code, reason: '', wasClean });
  }

  // 握手失敗：瀏覽器先觸發 error 再觸發 close
  serverFail() {
    this.onerror?.(new Event('error'));
    this.serverClose(1006, false);
  }
}

const last = () => FakeWebSocket.instances.at(-1)!;

let windowListeners: Record<string, () => void>;
let doc: { hidden: boolean; addEventListener: (event: string, fn: () => void) => void; removeEventListener: () => void };
let visibilityListener: () => void;
let ticket: MockInstance<typeof apiClient.wsTicket.create>;
let manager: WebSocketManager;

// 讓 ticket 等 promise 完成，但不推進計時器
const flush = () => vi.advanceTimersByTimeAsync(0);

const pings = (ws: FakeWebSocket) => ws.sent.filter((m) => m['type'] === 'ping').length;

async function connectOpen(roomId = 'r1') {
  const done = manager.connect(roomId);
  await flush();
  last().serverOpen();
  await done;
  return last();
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeWebSocket.instances = [];
  windowListeners = {};
  vi.stubGlobal('WebSocket', FakeWebSocket);
  doc = {
    hidden: false,
    addEventListener: (event, fn) => { if (event === 'visibilitychange') visibilityListener = fn; },
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal('document', doc);
  vi.stubGlobal('window', {
    location: { protocol: 'http:', hostname: 'chat.example.com', port: '' },
    setTimeout: (fn: () => void, ms: number) => setTimeout(fn, ms),
    setInterval: (fn: () => void, ms: number) => setInterval(fn, ms),
    addEventListener: (event: string, fn: () => void) => { windowListeners[event] = fn; },
    removeEventListener: vi.fn(),
  });
  // 去掉退避的隨機抖動，讓延遲可預期
  vi.spyOn(Math, 'random').mockReturnValue(0);
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'debug').mockImplementation(() => {});
  let n = 0;
  ticket = vi.spyOn(apiClient.wsTicket, 'create').mockImplementation(async () => `t${++n}`);
  messageStore.clearMessages();
  messageStatusStore.clearAll();
  manager = new WebSocketManager();
});

afterEach(() => {
  manager.destroy();
  vi.useRealTimers();
});

describe('建立連線', () => {
  it('以 ticket 連到房間，並帶上本地已知的最大 seq', async () => {
    messageStore.addMessage({ id: 'm1', room_id: 'r1', seq: 7, created_at: '2026-01-01T00:00:00Z' } as Message);
    const connected = vi.fn();
    manager.on('connected', connected);

    const ws = await connectOpen('r1');

    expect(ticket).toHaveBeenCalledWith('r1');
    expect(ws.url).toBe('ws://chat.example.com/ws/r1?ticket=t1&last_seq=7');
    expect(manager.isConnected()).toBe(true);
    expect(manager.getConnectionState()).toBe('connected');
    expect(connected).toHaveBeenCalledTimes(1);
  });

  it('https 頁面使用 wss', async () => {
    vi.stubGlobal('window', { ...window, location: { protocol: 'https:', hostname: 'chat.example.com', port: '' } });

    const ws = await connectOpen('r1');

    expect(ws.url).toBe('wss://chat.example.com/ws/r1?ticket=t1');
  });

  it('收到的事件分派到 store，格式不符的訊息略過', async () => {
    const ws = await connectOpen('r1');

    ws.serverSend({ type: 'message', payload: { id: 'm1', room_id: 'r1', content: '嗨', created_at: '2026-01-01T00:00:00Z' } });
    ws.serverSend({ type: 'not-a-known-type' });
    ws.onmessage?.({ data: '{broken json' });

    expect(messageStore.messages.map((m) => m.id)).toEqual(['m1']);
  });
});

describe('斷線重連', () => {
  it('非正常關閉後以指數退避重連，每次重新取得 ticket', async () => {
    const first = await connectOpen('r1');
    const disconnected = vi.fn();
    manager.on('disconnected', disconnected);

    first.serverClose(1006, false);
    expect(disconnected).toHaveBeenCalledWith({ code: 1006, reason: '' });

    await vi.advanceTimersByTimeAsync(999);
    expect(ticket).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(ticket).toHaveBeenCalledTimes(2);
    expect(last().url).toBe('ws://chat.example.com/ws/r1?ticket=t2');

    // 第二次仍失敗：延遲加倍
    last().serverFail();
    await vi.advanceTimersByTimeAsync(1999);
    expect(ticket).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(ticket).toHaveBeenCalledTimes(3);

    // 連上後重設退避
    last().serverOpen();
    await flush();
    last().serverClose(1006, false);
    await vi.advanceTimersByTimeAsync(1000);
    expect(ticket).toHaveBeenCalledTimes(4);
  });

  it.each([1000, 1001, 4001, 4003])('關閉代碼 %i 不重連', async (code) => {
    const ws = await connectOpen('r1');

    ws.serverClose(code, false);
    await vi.advanceTimersByTimeAsync(60_000);

    expect(ticket).toHaveBeenCalledTimes(1);
  });

  it('連續失敗達上限後發出 reconnect_failed；網路恢復時重新嘗試', async () => {
    const ws = await connectOpen('r1');
    ticket.mockRejectedValue(new Error('網路中斷'));
    const failed = vi.fn();
    manager.on('reconnect_failed', failed);

    ws.serverClose(1006, false);
    // 1 + 2 + 4 + 8 + 16 + 30 × 5 秒
    await vi.advanceTimersByTimeAsync(181_000);

    expect(ticket).toHaveBeenCalledTimes(11);
    expect(failed).toHaveBeenCalledTimes(1);
    expect(failed.mock.calls[0]![0]).toMatchObject({ attempts: 10 });

    ticket.mockResolvedValue('t-online');
    windowListeners['online']!();
    await vi.advanceTimersByTimeAsync(1000);
    expect(last().url).toContain('ticket=t-online');
  });

  it('主動 disconnect 後不重連', async () => {
    const ws = await connectOpen('r1');

    manager.disconnect();
    ws.serverClose(1000, true);
    await vi.advanceTimersByTimeAsync(60_000);

    expect(ws.closeCalls).toEqual([{ code: 1000, reason: 'Client disconnect' }]);
    expect(ticket).toHaveBeenCalledTimes(1);
    expect(manager.isConnected()).toBe(false);
  });
});

describe('心跳', () => {
  it('每 20 秒送出 ping，收到 pong 就維持連線', async () => {
    const ws = await connectOpen('r1');

    await vi.advanceTimersByTimeAsync(20_000);
    expect(ws.sent).toEqual([{ type: 'ping' }]);

    ws.serverSend({ type: 'pong' });
    await vi.advanceTimersByTimeAsync(10_000);
    expect(ws.closeCalls).toEqual([]);
  });

  it('ping 10 秒沒有回應時重新連線（即使伺服器正常完成關閉握手）', async () => {
    const ws = await connectOpen('r1');

    await vi.advanceTimersByTimeAsync(30_000);
    expect(ws.closeCalls).toEqual([{ code: 4000, reason: 'Ping timeout' }]);

    // 伺服器回應關閉：wasClean 為 true
    ws.serverClose(4000, true);
    await vi.advanceTimersByTimeAsync(1000);

    expect(ticket).toHaveBeenCalledTimes(2);
    last().serverOpen();
    expect(manager.isConnected()).toBe(true);
  });

  it('ping 逾時後即使關閉事件遲遲未到，也立即開始重連', async () => {
    const ws = await connectOpen('r1');
    const disconnected = vi.fn();
    manager.on('disconnected', disconnected);

    await vi.advanceTimersByTimeAsync(30_000);
    expect(disconnected).toHaveBeenCalledTimes(1);

    // 舊連線的關閉事件在重連前才到：不再重複觸發斷線
    ws.serverClose(1006, false);
    expect(disconnected).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1000);
    expect(ticket).toHaveBeenCalledTimes(2);
    last().serverOpen();
    expect(manager.isConnected()).toBe(true);
  });

  it('分頁在背景時建立連線，切回前台後仍是每 20 秒一次 ping', async () => {
    doc.hidden = true;
    const ws = await connectOpen('r1');

    await vi.advanceTimersByTimeAsync(5000);
    doc.hidden = false;
    visibilityListener();

    await vi.advanceTimersByTimeAsync(20_000);
    expect(pings(ws)).toBe(1);
    ws.serverSend({ type: 'pong' });

    await vi.advanceTimersByTimeAsync(20_000);
    expect(pings(ws)).toBe(2);
  });

  it('切回前台後切換房間，新的連線不會收到上一條連線留下的 ping', async () => {
    doc.hidden = true;
    await connectOpen('r1');
    await vi.advanceTimersByTimeAsync(5000);
    doc.hidden = false;
    visibilityListener();

    const ws = await connectOpen('r2');
    await vi.advanceTimersByTimeAsync(20_000);

    expect(pings(ws)).toBe(1);
  });
});

describe('訊息 ack', () => {
  it('送出後 10 秒未收到 ack 標記失敗；收到 ack 則否', async () => {
    const ws = await connectOpen('r1');

    expect(manager.sendMessage('第一則', 'text', 'c1')).toBe(true);
    manager.sendMessage('第二則', 'text', 'c2');
    expect(ws.sent.map((m) => m['client_id'])).toEqual(['c1', 'c2']);
    expect(messageStatusStore.getStatus('c1')?.status).toBe('sending');

    ws.serverSend({ type: 'ack', client_id: 'c2', message_id: 'm2', seq: 2 });
    await vi.advanceTimersByTimeAsync(10_000);

    expect(messageStatusStore.getStatus('c1')).toMatchObject({ status: 'failed', error: '伺服器未確認訊息，請重試' });
    expect(messageStatusStore.getStatus('c2')?.status).not.toBe('failed');
  });

  it('斷線時等待 ack 的訊息立即標記失敗', async () => {
    await connectOpen('r1');
    manager.sendMessage('內容', 'text', 'c1');

    manager.disconnect();

    expect(messageStatusStore.getStatus('c1')).toMatchObject({ status: 'failed', error: '連線中斷，訊息未送達' });
  });

  it('未連線時送出直接失敗', () => {
    expect(manager.sendMessage('內容', 'text', 'c1')).toBe(false);
    expect(messageStatusStore.getStatus('c1')).toMatchObject({ status: 'failed', error: 'WebSocket 未連接' });
  });
});

describe('重疊的連線請求', () => {
  it('較早的請求較晚拿到 ticket 時，不會取代較新的連線', async () => {
    const ticketA = deferred<string>();
    const ticketB = deferred<string>();
    ticket.mockImplementation((roomId) => (roomId === 'A' ? ticketA.promise : ticketB.promise));

    let settledA = false;
    void manager.connect('A').then(() => { settledA = true; });
    const connectB = manager.connect('B');
    ticketB.resolve('tB');
    await flush();
    const wsB = last();
    wsB.serverOpen();
    await connectB;

    ticketA.resolve('tA');
    await flush();

    expect(FakeWebSocket.instances.map((ws) => ws.url)).toEqual(['ws://chat.example.com/ws/B?ticket=tB']);
    expect(wsB.closeCalls).toEqual([]);
    expect(manager.isConnected()).toBe(true);
    expect(settledA).toBe(true);
  });

  it('取得 ticket 期間呼叫 disconnect，之後不會建立連線', async () => {
    const pending = deferred<string>();
    ticket.mockReturnValue(pending.promise);

    let settled = false;
    void manager.connect('A').then(() => { settled = true; });
    manager.disconnect();
    pending.resolve('tA');
    await flush();

    expect(FakeWebSocket.instances).toEqual([]);
    expect(settled).toBe(true);
  });

  it('切換房間時關閉仍在連線中的舊連線', async () => {
    let settledA = false;
    void manager.connect('A').finally(() => { settledA = true; });
    await flush();
    const wsA = last();

    const connectB = manager.connect('B');
    await flush();
    last().serverOpen();
    await connectB;

    expect(wsA.closeCalls).toHaveLength(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    // 被關閉的舊連線觸發錯誤事件：舊的 connect() 結束，新連線不受影響
    wsA.serverFail();
    await flush();
    expect(settledA).toBe(true);
    expect(manager.isConnected()).toBe(true);
  });

  it('舊連線的逾時計時器與錯誤事件不影響新的連線', async () => {
    const connectA = manager.connect('A');
    connectA.catch(() => {});
    await flush();
    const wsA = last();

    await vi.advanceTimersByTimeAsync(6000);
    const connectB = manager.connect('B');
    connectB.catch(() => {});
    await flush();
    const wsB = last();

    // A 的 10 秒連線逾時到期、A 的錯誤事件：B 仍在連線中，不應被關閉或判定失敗
    await vi.advanceTimersByTimeAsync(4000);
    wsA.serverFail();
    expect(wsB.closeCalls).toEqual([]);
    expect(manager.getConnectionState()).toBe('connecting');

    wsB.serverOpen();
    await expect(connectB).resolves.toBeUndefined();
    expect(manager.isConnected()).toBe(true);
  });
});
