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

  // 切到探索觸發一次 API 呼叫（舊 token 已失效）；探索是 tab 不是 button，
  // 找錯 role 時點擊逾時被吞掉，只能等背景請求碰巧觸發，冷啟動時會失敗
  await page.getByRole('tab', { name: '探索' }).click();
  await expect(page).toHaveURL(/\/login/);
  expect(await page.evaluate(() => localStorage.getItem('auth_user'))).toBeNull();
});

test('在另一個 session 改密碼後，在儀表板按刷新導回登入頁', async ({ page, request }) => {
  const user = await registerUser(request, 'dash');
  const login = await page.context().request.post('/api/auth/login', {
    form: { username: user.username, password: PASSWORD },
  });
  expect(login.ok()).toBe(true);

  await page.goto('/app/dashboard');
  await expect(page.getByText('查看您的聊天室統計資訊和最近活動')).toBeVisible();
  const refresh = page.getByRole('button', { name: '刷新' });
  await expect(refresh).toBeEnabled();

  const changed = await request.put('/api/auth/change-password', {
    data: { current_password: PASSWORD, new_password: 'password456' },
  });
  expect(changed.ok()).toBe(true);

  await refresh.click();
  await expect(page).toHaveURL(/\/login/);
});
