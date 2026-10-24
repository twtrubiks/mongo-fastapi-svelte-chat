// 訊息送出：途中遺失的訊息可以重試直到送達
import { expect, test } from '@playwright/test';
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
