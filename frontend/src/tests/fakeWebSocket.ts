type CloseEventInit = { code: number; reason: string; wasClean: boolean };

// 以測試驅動的 WebSocket：由測試決定何時開啟、收到訊息與關閉
export class FakeWebSocket {
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
