// 房主撤銷權限：移出成員時對方要立即離開房間；邀請碼外流時重新產生，舊碼失效
import { expect, test, type Page } from '@playwright/test';
import { createRoom, registerUser, uniqueSuffix } from './helpers';

async function openSettings(page: Page) {
  await page.locator('.desktop-room-header').getByRole('button', { name: '更多選項' }).click();
  await page.getByRole('button', { name: '聊天室設定' }).click();
  return page.getByRole('dialog');
}

test('房主移出成員：成員的頁面離開房間並提示，房主看到系統訊息', async ({ page, browser }) => {
  const ownerApi = page.context().request;
  await registerUser(ownerApi, 'owner');
  const room = await createRoom(ownerApi, `移出成員-${uniqueSuffix()}`, { room_type: 'private' });

  const memberContext = await browser.newContext();
  const memberPage = await memberContext.newPage();
  const member = await registerUser(memberContext.request, 'member');
  const joined = await memberContext.request.post(`/api/rooms/${room.id}/join`, {
    data: { invite_code: room.invite_code },
  });
  expect(joined.ok()).toBe(true);
  await memberPage.goto(`/app/room/${room.id}`);
  await expect(memberPage.locator('.desktop-room-header')).toContainText(room.name);

  await page.goto(`/app/room/${room.id}`);
  const settings = await openSettings(page);
  await settings.getByRole('button', { name: '成員管理' }).click();
  await settings.getByRole('listitem').filter({ hasText: member.username }).getByRole('button', { name: '移出' }).click();
  await settings.getByRole('button', { name: `確定移出 ${member.username}` }).click();
  await expect(settings).toContainText(`已將 ${member.username} 移出聊天室`);

  await expect(memberPage).toHaveURL(/\/app\/dashboard$/);
  await expect(memberPage.getByText('你已被房主移出聊天室')).toBeVisible();
  // 成員資格已撤銷，不能再讀取房間訊息（私人房對非成員隱藏存在，回 404）
  const messages = await memberContext.request.get(`/api/rooms/${room.id}/messages`);
  expect(messages.status()).toBe(404);

  await page.keyboard.press('Escape');
  await expect(page.getByText(`${member.username} 已被移出聊天室`)).toBeVisible();
  await memberContext.close();
});

test('重新產生邀請碼後，舊的邀請碼無法再加入', async ({ page, browser }) => {
  const ownerApi = page.context().request;
  await registerUser(ownerApi, 'owner');
  const room = await createRoom(ownerApi, `換邀請碼-${uniqueSuffix()}`, { room_type: 'private' });

  await page.goto(`/app/room/${room.id}`);
  const settings = await openSettings(page);
  await settings.getByRole('button', { name: '重新產生邀請碼' }).click();
  await settings.getByRole('button', { name: '產生新邀請碼' }).click();
  await expect(settings).toContainText('已產生新的邀請碼，舊的邀請碼已失效');
  const newCode = (await settings.locator('code').textContent())?.trim();
  expect(newCode).toBeTruthy();
  expect(newCode).not.toBe(room.invite_code);

  const outsiderContext = await browser.newContext();
  const outsider = outsiderContext.request;
  await registerUser(outsider, 'outsider');
  const withOldCode = await outsider.post(`/api/rooms/${room.id}/join`, { data: { invite_code: room.invite_code } });
  const withNewCode = await outsider.post(`/api/rooms/${room.id}/join`, { data: { invite_code: newCode } });
  expect(withOldCode.status()).toBe(400);
  expect(withNewCode.ok()).toBe(true);
  await outsiderContext.close();
});
