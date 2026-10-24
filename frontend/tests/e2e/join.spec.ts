// 加入房間：邀請碼錯誤或加入失敗時，要告訴使用者原因，不能當作已加入
import { expect, test, type Page } from '@playwright/test';
import { createRoom, registerUser, uniqueSuffix, updateRoom } from './helpers';

// 加入者先進到自己的房間，從側欄的房間列表操作
async function openOwnRoom(page: Page) {
  const api = page.context().request;
  await registerUser(api, 'joiner');
  const own = await createRoom(api, `自己的-${uniqueSuffix()}`);
  await page.goto(`/app/room/${own.id}`);
  await expect(page.locator('.desktop-room-header')).toContainText(own.name);
  return own;
}

test('從探索加入邀請制房間時輸入錯誤的邀請碼，顯示邀請碼無效', async ({ page, request }) => {
  await registerUser(request, 'owner');
  const room = await createRoom(request, `邀請制-${uniqueSuffix()}`, { room_type: 'public', join_policy: 'invite' });
  await openOwnRoom(page);

  await page.getByRole('tab', { name: '探索' }).click();
  await page.getByPlaceholder('搜尋公開房間...').fill(room.name);
  await page.locator('.room-list-content').getByText(room.name).click();

  const modal = page.getByRole('dialog');
  await modal.getByPlaceholder('邀請碼').fill('wrong-code');
  await modal.getByRole('button', { name: '加入', exact: true }).click();

  await expect(modal.locator('.alert-error')).toContainText('邀請碼無效');
});

test('邀請碼對應的房間已改成需要密碼時，用邀請碼加入會說明原因，不當作已加入', async ({ page, request }) => {
  await registerUser(request, 'owner');
  const room = await createRoom(request, `改成密碼-${uniqueSuffix()}`, { room_type: 'public', join_policy: 'invite' });
  // 分享出去的邀請碼仍可通過驗證，但加入時要密碼
  await updateRoom(request, room.id, { join_policy: 'password', password: 'roompass1' });
  const own = await openOwnRoom(page);

  await page.getByRole('button', { name: '通過邀請碼加入' }).click();
  const modal = page.getByRole('dialog');
  await modal.getByPlaceholder('請輸入邀請碼').fill(room.invite_code!);
  await modal.getByRole('button', { name: '加入房間' }).click();

  await expect(modal).toContainText('此聊天室需要密碼才能加入');
  await expect(page).toHaveURL(new RegExp(`/app/room/${own.id}$`));
});
