// 房間頁：直接開啟房間連結、快速切換房間
import { expect, test, type Page, type Route } from '@playwright/test';
import { createRoom, messageContents, postMessage, registerUser, uniqueSuffix, type TestRoom } from './helpers';

const DELAY_MS = 2500;
const ROOM_KEYS = ['P', 'A', 'B'] as const;
type RoomKey = (typeof ROOM_KEYS)[number];

async function setupRooms(page: Page) {
  const api = page.context().request;
  const user = await registerUser(api, 'room');
  const suffix = uniqueSuffix();
  const rooms = {} as Record<RoomKey, TestRoom>;
  for (const key of ROOM_KEYS) {
    rooms[key] = await createRoom(api, `房間${key}-${suffix}`);
    await postMessage(api, rooms[key].id, `${key} 房間的訊息-${suffix}`);
  }
  return { api, user, suffix, rooms };
}

// 記錄連到後端的 WebSocket（略過 Vite HMR）屬於哪個房間、是否已關閉
function trackSockets(page: Page, rooms: Record<RoomKey, TestRoom>) {
  const sockets: Array<{ room: string; closed: boolean }> = [];
  page.on('websocket', (ws) => {
    const url = ws.url();
    if (!url.includes(':8000/ws/')) return;
    const key = ROOM_KEYS.find((k) => url.includes(`/ws/${rooms[k].id}`));
    const entry = { room: key ?? url, closed: false };
    sockets.push(entry);
    ws.on('close', () => { entry.closed = true; });
  });
  return () => sockets.filter((s) => !s.closed).map((s) => s.room);
}

test('只有登入 cookie、本地沒有使用者資料時，直接開啟房間連結停在該房間', async ({ page }) => {
  const { rooms } = await setupRooms(page);
  const visited: string[] = [];
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) visited.push(new URL(frame.url()).pathname);
  });

  await page.goto(`/app/room/${rooms.P.id}`);
  await expect(page.locator('.desktop-room-header')).toContainText(rooms.P.name);

  expect(page.url()).toMatch(new RegExp(`/app/room/${rooms.P.id}$`));
  expect(visited.filter((path) => path.startsWith('/login'))).toEqual([]);
});

// 延遲房間 A 的某一種請求，模擬 A 的回應較慢（例如歷史訊息較多）
const DELAYED_REQUESTS = {
  messages: '訊息',
  room: '房間資料',
  ticket: 'WebSocket ticket',
} as const;

async function delayRoomA(page: Page, kind: keyof typeof DELAYED_REQUESTS, roomA: TestRoom) {
  const hold = async (route: Route) => {
    await new Promise((resolve) => setTimeout(resolve, DELAY_MS));
    await route.continue().catch(() => {}); // 頁面可能已取消請求
  };
  if (kind === 'messages') {
    await page.route(`**/api/rooms/${roomA.id}/messages*`, hold);
  } else if (kind === 'room') {
    await page.route(`**/api/rooms/${roomA.id}`, hold);
  } else {
    await page.route((url) => url.pathname === '/api/ws/ticket', (route) =>
      (route.request().postData() ?? '').includes(roomA.id) ? hold(route) : route.continue());
  }
}

for (const [kind, label] of Object.entries(DELAYED_REQUESTS) as Array<[keyof typeof DELAYED_REQUESTS, string]>) {
  test(`從 A 快速切到 B，A 的${label}較晚回來時，畫面、連線與送出的訊息都屬於 B`, async ({ page }) => {
    const { api, user, suffix, rooms } = await setupRooms(page);
    // 經由登入頁登入時，localStorage 已有使用者資料
    await page.addInitScript((stored) => localStorage.setItem('auth_user', stored), JSON.stringify(user));
    const openSockets = trackSockets(page, rooms);

    await page.goto(`/app/room/${rooms.P.id}`);
    await expect(page.getByText(`P 房間的訊息-${suffix}`)).toBeVisible({ timeout: 15_000 });
    await delayRoomA(page, kind, rooms.A);

    const sidebar = page.locator('.room-sidebar');
    await sidebar.getByText(rooms.A.name).click();
    await page.waitForTimeout(400);
    await sidebar.getByText(rooms.B.name).click();
    // 等 A 的延遲請求完成並處理完
    await page.waitForTimeout(DELAY_MS + 3000);

    expect(page.url()).toMatch(new RegExp(`/app/room/${rooms.B.id}$`));
    const header = page.locator('.desktop-room-header');
    await expect(header).toContainText(rooms.B.name);
    await expect(header).not.toContainText(rooms.A.name);
    await expect(page.getByText(`B 房間的訊息-${suffix}`)).toBeVisible();
    expect(openSockets()).toEqual(['B']);

    const content = `在 B 頁面送出-${suffix}`;
    const input = page.locator('.chat-area textarea').first();
    await input.fill(content);
    await input.press('Enter');
    await expect.poll(() => messageContents(api, rooms.B.id)).toContain(content);
    expect(await messageContents(api, rooms.A.id)).not.toContain(content);
  });
}
