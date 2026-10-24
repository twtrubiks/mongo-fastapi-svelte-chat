// 登入失效：在別處改密碼後，頁面導回登入頁
import { expect, test } from '@playwright/test';
import { createRoom, PASSWORD, registerUser, uniqueSuffix } from './helpers';

test('在另一個 session 改密碼後，頁面導回登入頁並清除本地使用者資料', async ({ page, request }) => {
  // request 是另一個 session（不與頁面共用 cookie）
  const user = await registerUser(request, 'expire');
  const room = await createRoom(request, `登入失效-${uniqueSuffix()}`);
  const login = await page.context().request.post('/api/auth/login', {
    form: { username: user.username, password: PASSWORD },
  });
  expect(login.ok()).toBe(true);

  await page.goto(`/app/room/${room.id}`);
  await expect(page.locator('.desktop-room-header')).toContainText(room.name);
  expect(await page.evaluate(() => localStorage.getItem('auth_user'))).not.toBeNull();

  const changed = await request.put('/api/auth/change-password', {
    data: { current_password: PASSWORD, new_password: 'password456' },
  });
  expect(changed.ok()).toBe(true);

  // WebSocket 被後端關閉後重連取 ticket 時就會導回；若還停在房間頁，切到探索觸發一次 API 呼叫
  await page.getByRole('button', { name: '探索', exact: true }).click({ timeout: 3000 }).catch(() => {});
  await expect(page).toHaveURL(/\/login/);
  expect(await page.evaluate(() => localStorage.getItem('auth_user'))).toBeNull();
});
