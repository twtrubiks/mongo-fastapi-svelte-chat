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

    expect(removeMember).toHaveBeenCalledWith('r1', 'u2');
    expect(await screen.findByText('已將 bob 移出聊天室')).toBeTruthy();
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
  });
});
