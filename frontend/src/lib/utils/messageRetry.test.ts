// 訊息重試：搭配真的 WebSocketManager 與假的 WebSocket，驗證 ack 逾時、手動重試、
// 重新連線後自動重送與檔案訊息重試（含 HTTP 備援）
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FakeWebSocket } from '../../tests/fakeWebSocket';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

type ManagerModule = typeof import('$lib/websocket/manager');

let retry: (typeof import('./messageRetry'))['messageRetryManager'];
let statusStore: (typeof import('$lib/stores/messageStatus.svelte'))['messageStatusStore'];
let processFileUpload: (typeof import('./fileUploadHandler'))['processFileUpload'];
let wsManager: ManagerModule['wsManager'];
let manager: ReturnType<ManagerModule['wsManager']['getInstance']>;

const last = () => FakeWebSocket.instances.at(-1)!;
const flush = () => vi.advanceTimersByTimeAsync(0);
const sentWith = (ws: FakeWebSocket, clientId: string) =>
  ws.sent.filter((m) => m['type'] === 'message' && m['client_id'] === clientId);
const status = (clientId: string) => statusStore.getStatus(clientId)?.status;

// 伺服器正常回應 ping，避免測試時間超過 30 秒時被心跳逾時斷線
function answerPings(ws: FakeWebSocket) {
  const send = ws.send.bind(ws);
  ws.send = (data: string) => {
    send(data);
    if (JSON.parse(data).type === 'ping') queueMicrotask(() => ws.serverSend({ type: 'pong' }));
  };
}

async function connectOpen(roomId = 'r1') {
  const done = manager.connect(roomId);
  await flush();
  answerPings(last());
  last().serverOpen();
  await done;
  return last();
}

function ack(ws: FakeWebSocket, clientId: string) {
  ws.serverSend({ type: 'ack', client_id: clientId, message_id: `server-${clientId}`, seq: 1, room_id: 'r1', timestamp: '2026-01-01T00:00:00Z' });
}

// 送出訊息並等到 10 秒 ack 逾時，訊息標記為失敗
async function sendAndTimeOut(ws: FakeWebSocket, clientId: string) {
  retry.addToRetryQueue({ id: clientId, content: '嗨', type: 'text' });
  manager.sendMessage('嗨', 'text', clientId);
  await vi.advanceTimersByTimeAsync(10_000);
  expect(status(clientId)).toBe('failed');
  return ws;
}

beforeEach(async () => {
  vi.useFakeTimers();
  vi.resetModules();
  FakeWebSocket.instances = [];
  vi.stubGlobal('WebSocket', FakeWebSocket);
  vi.stubGlobal('document', { hidden: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  vi.stubGlobal('window', {
    location: { protocol: 'http:', hostname: 'chat.example.com', port: '' },
    setTimeout: (fn: () => void, ms: number) => setTimeout(fn, ms),
    setInterval: (fn: () => void, ms: number) => setInterval(fn, ms),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
  vi.spyOn(Math, 'random').mockReturnValue(0);
  vi.spyOn(console, 'log').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
  vi.spyOn(console, 'warn').mockImplementation(() => {});
  vi.spyOn(console, 'debug').mockImplementation(() => {});

  // messageRetry 在模組載入時才註冊「連線成功就重送」的監聽，須在 stub window 之後匯入
  ({ messageRetryManager: retry } = await import('./messageRetry'));
  ({ messageStatusStore: statusStore } = await import('$lib/stores/messageStatus.svelte'));
  ({ processFileUpload } = await import('./fileUploadHandler'));
  ({ wsManager } = await import('$lib/websocket/manager'));
  const { apiClient } = await import('$lib/api/client');
  vi.spyOn(apiClient.wsTicket, 'create').mockResolvedValue('ticket');
  manager = wsManager.getInstance();
});

afterEach(() => {
  wsManager.destroy();
  vi.useRealTimers();
});

describe('手動重試', () => {
  it('ack 逾時後重試，以同一個 client_id 重送；收到 ack 後移出佇列並標記已送達', async () => {
    const ws = await sendAndTimeOut(await connectOpen(), 'c1');

    expect(await retry.manualRetry('c1')).toBe(true);
    expect(sentWith(ws, 'c1')).toHaveLength(2);
    expect(status('c1')).toBe('sending');

    ack(ws, 'c1');
    await flush();
    expect(retry.isInQueue('c1')).toBe(false);
    expect(status('c1')).toBe('sent');
  });

  it('重試後仍沒有收到 ack 時，訊息再次標記失敗，且可以再重試', async () => {
    const ws = await sendAndTimeOut(await connectOpen(), 'c1');
    await retry.manualRetry('c1');

    await vi.advanceTimersByTimeAsync(10_000);
    expect(status('c1')).toBe('failed');

    expect(await retry.manualRetry('c1')).toBe(true);
    expect(sentWith(ws, 'c1')).toHaveLength(3);
    expect(status('c1')).toBe('sending');
  });

  it('每次手動重試都重新計算次數，不會因為先前的失敗而停止重送', async () => {
    const ws = await sendAndTimeOut(await connectOpen(), 'c1');

    for (let round = 0; round < 4; round++) {
      expect(await retry.manualRetry('c1')).toBe(true);
      await vi.advanceTimersByTimeAsync(10_000);
      expect(status('c1')).toBe('failed');
    }
    expect(sentWith(ws, 'c1')).toHaveLength(5);
  });

  it('清除後移出佇列，重試不再送出', async () => {
    const ws = await sendAndTimeOut(await connectOpen(), 'c1');

    retry.removeFromQueue('c1');

    expect(status('c1')).toBeUndefined();
    expect(await retry.manualRetry('c1')).toBe(false);
    expect(sentWith(ws, 'c1')).toHaveLength(1);
  });
});

describe('重新連線', () => {
  it('手動重新連線時未確認的訊息標記失敗，連上後 1 秒自動重送', async () => {
    const first = await connectOpen();
    retry.addToRetryQueue({ id: 'c1', content: '嗨', type: 'text' });
    manager.sendMessage('嗨', 'text', 'c1');

    const reconnected = manager.manualReconnect();
    expect(status('c1')).toBe('failed');
    await flush();
    last().serverOpen();
    await reconnected;
    const second = last();
    expect(second).not.toBe(first);

    await vi.advanceTimersByTimeAsync(1000);
    expect(sentWith(second, 'c1')).toHaveLength(1);
    expect(status('c1')).toBe('sending');
  });

  it('連線意外中斷時，等待確認的訊息在重新連上後自動重送', async () => {
    const first = await connectOpen();
    retry.addToRetryQueue({ id: 'c1', content: '嗨', type: 'text' });
    manager.sendMessage('嗨', 'text', 'c1');

    first.serverClose(1006, false);
    expect(status('c1')).toBe('failed');

    // 1 秒後重新連線，連上後再 1 秒重送（不必等 10 秒的 ack 逾時）
    await vi.advanceTimersByTimeAsync(1000);
    answerPings(last());
    last().serverOpen();
    await vi.advanceTimersByTimeAsync(1000);
    expect(sentWith(last(), 'c1')).toHaveLength(1);
    expect(status('c1')).toBe('sending');
  });

  it('未連線時手動重試，訊息維持失敗，連上後自動重送', async () => {
    const ws = await sendAndTimeOut(await connectOpen(), 'c1');
    ws.serverClose(1006, false);

    expect(await retry.manualRetry('c1')).toBe(false);
    // 沒有送出就不能清掉失敗狀態，否則訊息看起來像已送出
    expect(statusStore.getStatus('c1')).toMatchObject({ status: 'failed', error: '尚未連線，連線恢復後會自動重送' });

    await vi.advanceTimersByTimeAsync(1000);
    last().serverOpen();
    await vi.advanceTimersByTimeAsync(5000);
    expect(sentWith(last(), 'c1')).toHaveLength(1);
  });
});

describe('檔案訊息', () => {
  it('重試時帶上原本的檔案資訊', async () => {
    const ws = await connectOpen();
    const file = new File(['x'.repeat(2048)], 'photo.png', { type: 'image/png' });

    await processFileUpload({
      file,
      url: '/uploads/photo.png',
      filename: 'photo.png',
      roomId: 'r1',
      isWsConnected: true,
      sendWsMessage: (content, type, id, metadata) => manager.sendMessage(content, type, id, metadata),
      sendHttpMessage: vi.fn(),
    });
    const [original] = ws.sent.filter((m) => m['type'] === 'message');
    const clientId = original!['client_id'] as string;
    expect(original!['metadata']).toMatchObject({ filename: 'photo.png', fileSize: 2048, mimeType: 'image/png' });

    await vi.advanceTimersByTimeAsync(10_000);
    const done = retry.retryAllFailed();
    await vi.advanceTimersByTimeAsync(100);
    await done;

    const retried = sentWith(ws, clientId);
    expect(retried).toHaveLength(2);
    expect(retried[1]).toMatchObject({ message_type: 'image', metadata: original!['metadata'] });
  });

  const uploadOverHttp = (sendHttpMessage: () => Promise<void>) =>
    processFileUpload({
      file: new File(['x'.repeat(2048)], 'report.pdf', { type: 'application/pdf' }),
      url: '/uploads/report.pdf',
      filename: 'report.pdf',
      roomId: 'r1',
      isWsConnected: false,
      sendWsMessage: vi.fn(),
      sendHttpMessage,
    });

  it('未連線時改用 HTTP 送出，同樣帶上 client_id 與檔案資訊', async () => {
    const sendHttpMessage = vi.fn().mockResolvedValue(undefined);

    expect((await uploadOverHttp(sendHttpMessage)).success).toBe(true);

    expect(sendHttpMessage).toHaveBeenCalledWith('r1', {
      content: '/uploads/report.pdf',
      message_type: 'file',
      client_id: expect.stringMatching(/^file_/),
      metadata: expect.objectContaining({ filename: 'report.pdf', fileSize: 2048, mimeType: 'application/pdf' }),
    });
    expect(retry.getQueueSize()).toBe(0);
  });

  it('HTTP 也送不出去時標記失敗，連上後以 WebSocket 重送', async () => {
    const sendHttpMessage = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    expect((await uploadOverHttp(sendHttpMessage)).success).toBe(false);
    const [clientId] = statusStore.getFailedMessageIds();
    expect(clientId).toMatch(/^file_/);

    const ws = await connectOpen();
    await vi.advanceTimersByTimeAsync(1000);
    const [resent] = sentWith(ws, clientId!);
    expect(resent).toMatchObject({ message_type: 'file', metadata: { filename: 'report.pdf', fileSize: 2048 } });
  });
});
