// 儀表板：按「刷新」取得最新資料
import { expect, test } from '@playwright/test';
import { createRoom, registerUser, uniqueSuffix } from './helpers';

test('加入新房間後按刷新，儀表板顯示最新的房間數', async ({ page }) => {
  const api = page.context().request;
  await registerUser(api, 'dash');

  await page.goto('/app/dashboard');
  const roomCount = page.getByText('已加入的房間').locator('..');
  await expect(roomCount).toContainText('0');
  const refresh = page.getByRole('button', { name: '刷新' });
  await expect(refresh).toBeEnabled();

  await createRoom(api, `儀表板-${uniqueSuffix()}`);
  await refresh.click();

  await expect(roomCount).toContainText('1');
});
