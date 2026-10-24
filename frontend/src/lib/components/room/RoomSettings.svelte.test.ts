// 房間設定：一般設定的儲存，以及房主撤銷權限（重新產生邀請碼、移出成員）
import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { authStore } from '$lib/stores/auth.svelte';
import { roomStore } from '$lib/stores/room.svelte';
import { JoinPolicy, RoomType } from '$lib/types';
import type { Room, User } from '$lib/types';
import RoomSettings from './RoomSettings.svelte';

function makeRoom(overrides: Partial<Room> = {}): Room {
  return {
    id: 'r1',
    name: '讀書會',
    description: '每週一聚',
    owner_id: 'owner',
    room_type: RoomType.PRIVATE,
    join_policy: JoinPolicy.INVITE,
    invite_code: 'old-code',
    members: ['owner', 'u2', 'u3'],
    member_count: 3,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as Room;
}

// 沒有邀請碼的公開房間
function publicRoom(join_policy: JoinPolicy): Room {
  const room = makeRoom({ room_type: RoomType.PUBLIC, join_policy });
  delete room.invite_code;
  return room;
}

const member = (id: string, username: string): User => ({ id, username, is_active: true });

function setup(room = makeRoom(), userId = 'owner') {
  authStore.setAuthState({ user: { id: userId, username: userId } as User });
  const onUpdate = vi.fn();
  const onClose = vi.fn();
  render(RoomSettings, { room, show: true, onUpdate, onClose });
  return { onUpdate, onClose };
}

beforeEach(() => {
  roomStore.setUsers([member('owner', '房主'), member('u2', 'bob'), member('u3', 'carol')]);
});

describe('一般設定', () => {
  it('儲存名稱與描述，並帶入新密碼', async () => {
    const updated = makeRoom({ name: '新名稱', room_type: RoomType.PUBLIC });
    const updateRoomSettings = vi.spyOn(roomStore, 'updateRoomSettings').mockResolvedValue(updated);
    const { onUpdate } = setup(publicRoom(JoinPolicy.DIRECT));

    await fireEvent.input(screen.getByLabelText('房間名稱'), { target: { value: '  新名稱 ' } });
    await fireEvent.input(screen.getByPlaceholderText('輸入新密碼（可選）'), { target: { value: 'secret1' } });
    await fireEvent.click(screen.getByRole('button', { name: '儲存設定' }));

    expect(updateRoomSettings).toHaveBeenCalledWith('r1', { name: '新名稱', description: '每週一聚', password: 'secret1' });
    expect(onUpdate).toHaveBeenCalledWith(updated);
    expect(await screen.findByText('房間設定已更新')).toBeTruthy();
  });

  it('儲存失敗時顯示後端的錯誤原因', async () => {
    vi.spyOn(roomStore, 'updateRoomSettings').mockRejectedValue(new Error('房間名稱已存在: 大廳'));
    const { onUpdate } = setup();

    await fireEvent.click(screen.getByRole('button', { name: '儲存設定' }));

    expect(await screen.findByText('房間名稱已存在: 大廳')).toBeTruthy();
    expect(onUpdate).not.toHaveBeenCalled();
  });

  // 開著設定時有人加入房間，room_updated 會更新 room（例如人數）
  it('房間資料在開啟期間更新時，不清掉正在輸入的內容', async () => {
    authStore.setAuthState({ user: { id: 'owner', username: 'owner' } as User });
    const room = makeRoom();
    const { rerender } = render(RoomSettings, { room, show: true, onClose: vi.fn() });

    await fireEvent.input(screen.getByLabelText('房間描述'), { target: { value: '改到一半的描述' } });
    await rerender({ room: { ...room, member_count: 4 } });

    expect((screen.getByLabelText('房間描述') as HTMLTextAreaElement).value).toBe('改到一半的描述');
  });

  it('非房主只能檢視，看不到邀請碼與成員管理', () => {
    setup(makeRoom(), 'u2');

    expect(screen.getByText(/只有房間擁有者才能修改房間設定/)).toBeTruthy();
    expect((screen.getByLabelText('房間名稱') as HTMLInputElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: '儲存設定' })).toBeNull();
    expect(screen.queryByText('邀請碼')).toBeNull();
    expect(screen.queryByRole('button', { name: '成員管理' })).toBeNull();
  });
});

describe('重新產生邀請碼', () => {
  it('確認後換成新的邀請碼並通知頁面', async () => {
    const regenerate = vi.spyOn(roomStore, 'regenerateInviteCode').mockResolvedValue('new-code');
    const { onUpdate } = setup();

    await fireEvent.click(screen.getByRole('button', { name: '重新產生邀請碼' }));
    expect(regenerate).not.toHaveBeenCalled();
    expect(screen.getByText(/舊的邀請碼會立即失效/)).toBeTruthy();
    await fireEvent.click(screen.getByRole('button', { name: '產生新邀請碼' }));

    expect(regenerate).toHaveBeenCalledWith('r1');
    expect(onUpdate).toHaveBeenCalledWith(expect.objectContaining({ id: 'r1', invite_code: 'new-code' }));
    expect(await screen.findByText('已產生新的邀請碼，舊的邀請碼已失效')).toBeTruthy();
  });

  it('頁面換上新的房間資料後，新邀請碼保持顯示', async () => {
    authStore.setAuthState({ user: { id: 'owner', username: 'owner' } as User });
    vi.spyOn(roomStore, 'regenerateInviteCode').mockResolvedValue('new-code');
    const room = makeRoom();
    const onUpdate = vi.fn();
    const { rerender } = render(RoomSettings, { room, show: true, onClose: vi.fn(), onUpdate });

    await fireEvent.click(screen.getByRole('button', { name: '重新產生邀請碼' }));
    await fireEvent.click(screen.getByRole('button', { name: '產生新邀請碼' }));
    await rerender({ room: onUpdate.mock.calls[0]![0] as Room });

    expect(screen.getByText('new-code').tagName).toBe('CODE');
  });

  it('可以取消', async () => {
    const regenerate = vi.spyOn(roomStore, 'regenerateInviteCode');
    setup();

    await fireEvent.click(screen.getByRole('button', { name: '重新產生邀請碼' }));
    await fireEvent.click(screen.getByRole('button', { name: '取消重新產生邀請碼' }));

    expect(regenerate).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '重新產生邀請碼' })).toBeTruthy();
  });

  it('失敗時顯示原因', async () => {
    vi.spyOn(roomStore, 'regenerateInviteCode').mockRejectedValue(new Error('只有房間擁有者可以重新產生邀請碼'));
    const { onUpdate } = setup();

    await fireEvent.click(screen.getByRole('button', { name: '重新產生邀請碼' }));
    await fireEvent.click(screen.getByRole('button', { name: '產生新邀請碼' }));

    expect(await screen.findByText('只有房間擁有者可以重新產生邀請碼')).toBeTruthy();
    expect(onUpdate).not.toHaveBeenCalled();
  });
});

describe('成員管理', () => {
  async function openMembersTab() {
    await fireEvent.click(screen.getByRole('button', { name: '成員管理' }));
    return screen.getByRole('list', { name: '房間成員' });
  }

  beforeEach(() => {
    vi.spyOn(roomStore, 'getBannedUsers').mockResolvedValue([]);
  });

  it('列出房主以外的成員', async () => {
    setup();

    const list = await openMembersTab();

    expect(within(list).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      expect.stringContaining('bob'),
      expect.stringContaining('carol'),
    ]);
  });

  it('確認後移出成員', async () => {
    const removeMember = vi.spyOn(roomStore, 'removeMember').mockResolvedValue();
    setup();
    await openMembersTab();

    const [bobRow] = screen.getAllByRole('listitem');
    await fireEvent.click(within(bobRow!).getByRole('button', { name: '移出' }));
    expect(removeMember).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button', { name: '確定移出 bob' }));

    expect(removeMember).toHaveBeenCalledWith('r1', 'u2', false);
    expect(await screen.findByText('已將 bob 移出聊天室')).toBeTruthy();
  });

  it('移出並封鎖：封鎖後列入封鎖名單', async () => {
    const removeMember = vi.spyOn(roomStore, 'removeMember').mockResolvedValue();
    setup();
    await openMembersTab();
    expect(await screen.findByText('沒有封鎖的使用者')).toBeTruthy();

    await fireEvent.click(screen.getAllByRole('button', { name: '移出' })[0]!);
    await fireEvent.click(screen.getByRole('button', { name: '移出並封鎖 bob' }));

    expect(removeMember).toHaveBeenCalledWith('r1', 'u2', true);
    expect(await screen.findByText('已封鎖 bob')).toBeTruthy();
    const banned = screen.getByRole('list', { name: '封鎖名單' });
    expect(within(banned).getByText('bob')).toBeTruthy();
  });

  it('開啟時載入封鎖名單，可解除封鎖', async () => {
    vi.spyOn(roomStore, 'getBannedUsers').mockResolvedValue([member('u9', 'dave')]);
    const unbanUser = vi.spyOn(roomStore, 'unbanUser').mockResolvedValue();
    setup();
    await openMembersTab();

    const banned = await screen.findByRole('list', { name: '封鎖名單' });
    await fireEvent.click(within(banned).getByRole('button', { name: '解除封鎖 dave' }));

    expect(unbanUser).toHaveBeenCalledWith('r1', 'u9');
    expect(await screen.findByText('已解除對 dave 的封鎖')).toBeTruthy();
    expect(screen.queryByRole('list', { name: '封鎖名單' })).toBeNull();
    expect(screen.getByText('沒有封鎖的使用者')).toBeTruthy();
  });

  // 設定頁的實例在換房間時保留：上一個房間的回應晚到，不能蓋掉這個房間的名單
  it('關掉設定後才回來的封鎖名單不顯示在下一個房間', async () => {
    let finishFirst!: (users: User[]) => void;
    vi.spyOn(roomStore, 'getBannedUsers')
      .mockImplementationOnce(() => new Promise((resolve) => { finishFirst = resolve; }))
      .mockResolvedValueOnce([]);
    authStore.setAuthState({ user: { id: 'owner', username: 'owner' } as User });
    const { rerender } = render(RoomSettings, { room: makeRoom(), show: true, onClose: vi.fn() });
    await openMembersTab();
    await fireEvent.click(screen.getByRole('button', { name: '關閉' }));

    await rerender({ room: makeRoom({ id: 'r2' }), show: false });
    await rerender({ show: true });
    await openMembersTab();
    expect(await screen.findByText('沒有封鎖的使用者')).toBeTruthy();
    finishFirst([member('u9', 'dave')]);
    await new Promise((resolve) => setTimeout(resolve));

    expect(screen.queryByText('dave')).toBeNull();
    expect(screen.getByText('沒有封鎖的使用者')).toBeTruthy();
  });

  it('名單還在載入時封鎖，重新載入讓名單包含剛封鎖的人', async () => {
    const getBannedUsers = vi.spyOn(roomStore, 'getBannedUsers')
      .mockImplementationOnce(() => new Promise(() => {}))
      .mockResolvedValueOnce([member('u2', 'bob')]);
    vi.spyOn(roomStore, 'removeMember').mockResolvedValue();
    setup();
    await openMembersTab();

    await fireEvent.click(screen.getAllByRole('button', { name: '移出' })[0]!);
    await fireEvent.click(screen.getByRole('button', { name: '移出並封鎖 bob' }));

    const banned = await screen.findByRole('list', { name: '封鎖名單' });
    expect(within(banned).getByText('bob')).toBeTruthy();
    expect(getBannedUsers).toHaveBeenCalledTimes(2);
  });

  it('以使用者名稱封鎖（可封鎖已離開或從未加入的人）', async () => {
    const banUser = vi.spyOn(roomStore, 'banUser').mockResolvedValue(member('u9', 'dave'));
    setup();
    await openMembersTab();
    await screen.findByText('沒有封鎖的使用者');

    const input = screen.getByLabelText('要封鎖的使用者名稱') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: ' dave ' } });
    await fireEvent.click(screen.getByRole('button', { name: '封鎖' }));

    expect(banUser).toHaveBeenCalledWith('r1', 'dave');
    expect(await screen.findByText('已封鎖 dave')).toBeTruthy();
    expect(within(screen.getByRole('list', { name: '封鎖名單' })).getByText('dave')).toBeTruthy();
    expect(input.value).toBe('');
  });

  it('以名稱封鎖失敗時顯示原因並保留輸入', async () => {
    vi.spyOn(roomStore, 'banUser').mockRejectedValue(new Error('找不到這個使用者'));
    setup();
    await openMembersTab();

    const input = screen.getByLabelText('要封鎖的使用者名稱') as HTMLInputElement;
    await fireEvent.input(input, { target: { value: 'nobody' } });
    await fireEvent.click(screen.getByRole('button', { name: '封鎖' }));

    expect(await screen.findByText('找不到這個使用者')).toBeTruthy();
    expect(input.value).toBe('nobody');
  });

  it('沒有輸入名稱時不能按封鎖', async () => {
    setup();
    await openMembersTab();

    expect((screen.getByRole('button', { name: '封鎖' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('封鎖名單載入失敗時顯示原因，可重試', async () => {
    const getBannedUsers = vi
      .spyOn(roomStore, 'getBannedUsers')
      .mockRejectedValueOnce(new Error('網路連線失敗'))
      .mockResolvedValueOnce([member('u9', 'dave')]);
    setup();
    await openMembersTab();

    expect(await screen.findByText('網路連線失敗')).toBeTruthy();
    await fireEvent.click(screen.getByRole('button', { name: '重新載入封鎖名單' }));

    expect(await screen.findByRole('list', { name: '封鎖名單' })).toBeTruthy();
    expect(getBannedUsers).toHaveBeenCalledTimes(2);
  });

  it('移出失敗時顯示原因', async () => {
    vi.spyOn(roomStore, 'removeMember').mockRejectedValue(new Error('該使用者不是房間成員'));
    setup();
    await openMembersTab();

    await fireEvent.click(screen.getAllByRole('button', { name: '移出' })[0]!);
    await fireEvent.click(screen.getByRole('button', { name: '確定移出 bob' }));

    expect(await screen.findByText('該使用者不是房間成員')).toBeTruthy();
  });

  it.each([
    ['邀請制房間', makeRoom(), '重新產生邀請碼'],
    ['密碼房間', publicRoom(JoinPolicy.PASSWORD), '變更房間密碼'],
    ['公開房間', publicRoom(JoinPolicy.DIRECT), '仍可重新加入'],
  ])('%s：說明被移出的人能否再加入', async (_, room, hint) => {
    setup(room);

    await openMembersTab();

    expect(screen.getByText(new RegExp(hint))).toBeTruthy();
    expect(screen.getByText(/要阻止請選「移出並封鎖」/)).toBeTruthy();
  });
});
