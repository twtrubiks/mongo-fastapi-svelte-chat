// 房主撤銷權限：移出成員時對方要立即離開房間；封鎖後不能再加入；邀請碼外流時重新產生，舊碼失效
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

test('移出並封鎖：公開房也不能再加入、探索也看不到，解除封鎖後可以', async ({ page, browser }) => {
  const ownerApi = page.context().request;
  await registerUser(ownerApi, 'owner');
  const suffix = uniqueSuffix();
  const room = await createRoom(ownerApi, `封鎖-${suffix}`);
  const other = await createRoom(ownerApi, `封鎖-${suffix}-其他`);

  const memberContext = await browser.newContext();
  const memberPage = await memberContext.newPage();
  const memberApi = memberContext.request;
  const member = await registerUser(memberApi, 'member');
  const own = await createRoom(memberApi, `成員自己的-${uniqueSuffix()}`);
  expect((await memberApi.post(`/api/rooms/${room.id}/join`)).ok()).toBe(true);
  await memberPage.goto(`/app/room/${room.id}`);
  await expect(memberPage.locator('.desktop-room-header')).toContainText(room.name);

  await page.goto(`/app/room/${room.id}`);
  const settings = await openSettings(page);
  await settings.getByRole('button', { name: '成員管理' }).click();
  await expect(settings).toContainText('沒有封鎖的使用者');
  await settings.getByRole('listitem').filter({ hasText: member.username }).getByRole('button', { name: '移出' }).click();
  await settings.getByRole('button', { name: `移出並封鎖 ${member.username}` }).click();
  await expect(settings).toContainText(`已封鎖 ${member.username}`);
  await expect(settings.getByRole('list', { name: '封鎖名單' })).toContainText(member.username);
  await expect(memberPage).toHaveURL(/\/app\/dashboard$/);
  await expect(memberPage.getByText('你已被房主移出並封鎖，無法再加入此聊天室')).toBeVisible();

  // 探索搜尋不到封鎖自己的房間（同名前綴的其他房間仍在）。搜尋關鍵字會被標亮，
  // 所以等搜尋結果回來後，以房間按鈕的完整名稱比對
  await memberPage.goto(`/app/room/${own.id}`);
  await memberPage.getByRole('tab', { name: '探索' }).click();
  const searched = memberPage.waitForResponse((r) => r.url().includes('/api/rooms?') && r.url().includes('search='));
  await memberPage.getByPlaceholder('搜尋公開房間...').fill(`封鎖-${suffix}`);
  await searched;
  const results = memberPage.locator('.room-list-content');
  await expect(results.getByRole('button', { name: `${other.name} by` })).toBeVisible();
  await expect(results.getByRole('button', { name: `${room.name} by` })).toHaveCount(0);

  // 直接開房間網址也加不進去，看到原因並回到自己的房間
  await memberPage.goto(`/app/room/${room.id}`);
  await expect(memberPage.getByText('你已被房主禁止加入此聊天室')).toBeVisible();
  await expect(memberPage).toHaveURL(new RegExp(`/app/room/${own.id}$`));

  await settings.getByRole('button', { name: `解除封鎖 ${member.username}` }).click();
  await expect(settings).toContainText(`已解除對 ${member.username} 的封鎖`);
  expect((await memberApi.post(`/api/rooms/${room.id}/join`)).ok()).toBe(true);
  await memberContext.close();
});

test('以使用者名稱封鎖已經離開的人，之後不能再加入', async ({ page, browser }) => {
  const ownerApi = page.context().request;
  await registerUser(ownerApi, 'owner');
  const room = await createRoom(ownerApi, `封鎖離開的人-${uniqueSuffix()}`);

  const memberContext = await browser.newContext();
  const memberApi = memberContext.request;
  const member = await registerUser(memberApi, 'member');
  expect((await memberApi.post(`/api/rooms/${room.id}/join`)).ok()).toBe(true);
  expect((await memberApi.post(`/api/rooms/${room.id}/leave`)).ok()).toBe(true);

  await page.goto(`/app/room/${room.id}`);
  const settings = await openSettings(page);
  await settings.getByRole('button', { name: '成員管理' }).click();
  await settings.getByLabel('要封鎖的使用者名稱').fill(member.username);
  await settings.getByRole('button', { name: '封鎖', exact: true }).click();
  await expect(settings).toContainText(`已封鎖 ${member.username}`);
  await expect(settings.getByRole('list', { name: '封鎖名單' })).toContainText(member.username);

  const rejoin = await memberApi.post(`/api/rooms/${room.id}/join`);
  expect(rejoin.status()).toBe(403);
  await memberContext.close();
});

// 按下離開、確認框開著時被房主封鎖：離開請求回 404，連線也被關閉。
// 不能停在已斷線的房間頁並提示「離開失敗」，要導回儀表板並說明被封鎖
test('按離開時剛好被封鎖：導回儀表板並說明，不提示離開失敗', async ({ page, browser }) => {
  const ownerContext = await browser.newContext();
  const ownerApi = ownerContext.request;
  await registerUser(ownerApi, 'owner');
  const room = await createRoom(ownerApi, `離開時被封鎖-${uniqueSuffix()}`);

  const memberApi = page.context().request;
  const member = await registerUser(memberApi, 'member');
  expect((await memberApi.post(`/api/rooms/${room.id}/join`)).ok()).toBe(true);
  await page.goto(`/app/room/${room.id}`);
  await expect(page.locator('.desktop-room-header')).toContainText(room.name);

  page.once('dialog', async (dialog) => {
    const banned = await ownerApi.delete(`/api/rooms/${room.id}/members/${member.id}?ban=true`);
    expect(banned.ok()).toBe(true);
    await dialog.accept();
  });
  await page.locator('.desktop-room-header').getByRole('button', { name: '更多選項' }).click();
  await page.getByRole('button', { name: '離開聊天室' }).click();

  await expect(page).toHaveURL(/\/app\/dashboard$/);
  await expect(page.getByText('你已被房主移出並封鎖，無法再加入此聊天室')).toBeVisible();
  await expect(page.getByText('離開聊天室失敗')).toHaveCount(0);
  await ownerContext.close();
});
