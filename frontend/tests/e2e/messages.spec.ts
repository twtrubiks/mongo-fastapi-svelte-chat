// 訊息送出：途中遺失或離線時送出的訊息，都能重試直到送達
import { expect, test, type WebSocketRoute } from '@playwright/test';
import { createRoom, messageContents, registerUser, uniqueSuffix } from './helpers';

test('訊息在途中遺失、重試後又遺失時，仍可再次重試直到送達', async ({ page }) => {
  test.setTimeout(90_000);
  const api = page.context().request;
  await registerUser(api, 'retry');
  const room = await createRoom(api, `重試-${uniqueSuffix()}`);

  // 攔截連到後端的 WebSocket：前兩則送出的聊天訊息丟掉，伺服器收不到，也就不會回 ack
  let toDrop = 2;
  let connected = false;
  await page.routeWebSocket(/:8000\/ws\//, (ws) => {
    const server = ws.connectToServer();
    ws.onMessage((message) => {
      if (toDrop > 0 && typeof message === 'string' && JSON.parse(message).type === 'message') {
        toDrop--;
        return;
      }
      server.send(message);
    });
    server.onMessage((message) => {
      connected = true;
      ws.send(message);
    });
  });

  await page.goto(`/app/room/${room.id}`);
  await expect(page.locator('.desktop-room-header')).toContainText(room.name);
  await expect.poll(() => connected).toBe(true);

  const content = `會遺失的訊息-${uniqueSuffix()}`;
  const input = page.locator('.chat-area textarea').first();
  await input.fill(content);
  await input.press('Enter');

  // 10 秒沒收到 ack 才標記失敗
  const retryButton = page.locator('.send-retry-button');
  await expect(retryButton).toBeVisible({ timeout: 15_000 });
  await retryButton.click();
  await expect(retryButton).toBeHidden();

  await expect(retryButton).toBeVisible({ timeout: 15_000 });
  await retryButton.click();

  await expect.poll(() => messageContents(api, room.id)).toContain(content);
  await expect(retryButton).toBeHidden();
  expect((await messageContents(api, room.id)).filter((c) => c === content)).toHaveLength(1);
});

test('離線時送出的訊息標記失敗，網路恢復後自動送達', async ({ page, context }) => {
  const api = page.context().request;
  await registerUser(api, 'offline');
  const room = await createRoom(api, `離線-${uniqueSuffix()}`);

  // 攔截連到後端的 WebSocket，之後由這裡關閉頁面端的連線
  let pageSide: WebSocketRoute | undefined;
  await page.routeWebSocket(/:8000\/ws\//, (ws) => {
    pageSide = ws;
    const server = ws.connectToServer();
    ws.onMessage((message) => server.send(message));
    server.onMessage((message) => ws.send(message));
  });

  await page.goto(`/app/room/${room.id}`);
  await expect(page.locator('.desktop-room-header')).toContainText(room.name);
  await expect.poll(() => pageSide).toBeDefined();

  // 網路中斷：WebSocket 斷線，頁面改用 HTTP 送出，但 HTTP 也送不出去
  await context.setOffline(true);
  await pageSide!.close();
  await expect(page.getByText('連接中斷')).toBeVisible();

  const content = `離線時送出-${uniqueSuffix()}`;
  const input = page.locator('.chat-area textarea').first();
  await input.fill(content);
  await input.press('Enter');

  const retryButton = page.locator('.send-retry-button');
  await expect(retryButton).toBeVisible();

  // 仍離線時按重試：送不出去，訊息維持失敗，不能看起來像已送出
  await retryButton.click();
  await expect(retryButton).toBeVisible();

  // 網路恢復：重新連上 WebSocket 後自動重送
  await context.setOffline(false);
  await expect.poll(() => messageContents(api, room.id)).toContain(content);
  await expect(retryButton).toBeHidden();
  expect((await messageContents(api, room.id)).filter((c) => c === content)).toHaveLength(1);
});

test('在 A 送出失敗的訊息，切到 B 之後不會送進 B', async ({ page, context }) => {
  const api = page.context().request;
  const user = await registerUser(api, 'switch');
  const suffix = uniqueSuffix();
  const roomA = await createRoom(api, `失敗後切換A-${suffix}`);
  const roomB = await createRoom(api, `失敗後切換B-${suffix}`);
  // 經由登入頁登入時，localStorage 已有使用者資料
  await page.addInitScript((stored) => localStorage.setItem('auth_user', stored), JSON.stringify(user));

  // A 斷線後不讓它再連上，訊息只能停在失敗狀態；B 的連線正常轉送
  let roomASide: WebSocketRoute | undefined;
  let blockRoomA = false;
  let roomBConnected = false;
  await page.routeWebSocket(/:8000\/ws\//, (ws) => {
    const isRoomA = ws.url().includes(`/ws/${roomA.id}`);
    if (isRoomA && blockRoomA) {
      void ws.close();
      return;
    }
    if (isRoomA) roomASide = ws;
    const server = ws.connectToServer();
    ws.onMessage((message) => server.send(message));
    server.onMessage((message) => {
      if (!isRoomA) roomBConnected = true;
      ws.send(message);
    });
  });

  await page.goto(`/app/room/${roomA.id}`);
  await expect(page.locator('.desktop-room-header')).toContainText(roomA.name);
  await expect.poll(() => roomASide).toBeDefined();

  await context.setOffline(true);
  blockRoomA = true;
  await roomASide!.close();
  await expect(page.getByText('連接中斷')).toBeVisible();

  const content = `在 A 送出失敗-${suffix}`;
  const input = page.locator('.chat-area textarea').first();
  await input.fill(content);
  await input.press('Enter');
  await expect(page.locator('.send-retry-button')).toBeVisible();

  await context.setOffline(false);
  await page.locator('.room-sidebar').getByText(roomB.name).click();
  await expect(page.locator('.desktop-room-header')).toContainText(roomB.name);
  await expect.poll(() => roomBConnected).toBe(true);

  // 連上後約 1 秒會重送失敗的訊息；多等一段時間，確認沒有送進 B
  await page.waitForTimeout(3000);
  expect(await messageContents(api, roomB.id)).not.toContain(content);
  await expect(page.getByText('則訊息發送失敗')).toBeHidden();
});
