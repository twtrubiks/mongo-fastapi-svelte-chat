// 從探索加入房間：依房間的加入方式直接加入、要求密碼或邀請碼，失敗時說明原因
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { roomStore } from '$lib/stores/room.svelte';
import { JoinPolicy, RoomType } from '$lib/types';
import type { Room, RoomSummary } from '$lib/types';
import type { JoinRequirementsData } from '$lib/bff-api-client';
import JoinRoomModal from './JoinRoomModal.svelte';

const ROOM = { id: 'r1', name: '讀書會', room_type: RoomType.PUBLIC, member_count: 3 } as RoomSummary;
const JOINED = { ...ROOM, members: ['owner', 'me'] } as Room;

function requirements(policy: 'direct' | 'password' | 'invite'): JoinRequirementsData {
  return {
    isMember: false,
    room: { ...ROOM, join_policy: policy as JoinPolicy },
    requirements: {
      needsPassword: policy === 'password',
      needsInviteCode: policy === 'invite',
      canDirectJoin: policy === 'direct',
    },
  } as JoinRequirementsData;
}

function setup(check: JoinRequirementsData | Error) {
  const checkJoinRequirements = vi.spyOn(roomStore, 'checkJoinRequirements');
  if (check instanceof Error) checkJoinRequirements.mockRejectedValue(check);
  else checkJoinRequirements.mockResolvedValue(check);
  const onSuccess = vi.fn();
  const onClose = vi.fn();
  render(JoinRoomModal, { room: ROOM, show: true, onSuccess, onClose });
  return { onSuccess, onClose };
}

describe('直接加入', () => {
  it('公開房間開啟後直接加入並顯示成功', async () => {
    const joinRoom = vi.spyOn(roomStore, 'joinRoom').mockResolvedValue({ success: true, room: JOINED, users: [] });
    const { onSuccess } = setup(requirements('direct'));

    expect(await screen.findByText('加入成功！')).toBeTruthy();
    expect(joinRoom).toHaveBeenCalledWith('r1', undefined);
    expect(onSuccess).toHaveBeenCalledWith(JOINED);
  });

  it('已經是成員時不再加入，直接通知', async () => {
    const joinRoom = vi.spyOn(roomStore, 'joinRoom');
    // BFF 對已是成員的情況不回 requirements
    const { onSuccess } = setup({ isMember: true, room: ROOM } as unknown as JoinRequirementsData);

    await vi.waitFor(() => expect(onSuccess).toHaveBeenCalledWith(ROOM));
    expect(joinRoom).not.toHaveBeenCalled();
  });

  it('房間已滿時顯示原因', async () => {
    vi.spyOn(roomStore, 'joinRoom').mockRejectedValue(new Error('房間已滿'));
    const { onSuccess } = setup(requirements('direct'));

    expect(await screen.findByText('房間已滿')).toBeTruthy();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it('無法取得加入要求時顯示原因', async () => {
    setup(new Error('聊天室不存在'));

    expect(await screen.findByText('聊天室不存在')).toBeTruthy();
  });
});

describe('需要密碼', () => {
  async function typePassword(value: string) {
    await fireEvent.input(await screen.findByPlaceholderText('房間密碼'), { target: { value } });
  }

  it('密碼錯誤時留在密碼步驟並顯示原因，改對後加入成功', async () => {
    const joinRoom = vi
      .spyOn(roomStore, 'joinRoom')
      .mockResolvedValueOnce({ success: false, message: '密碼錯誤', requiresAction: { type: 'error', message: '密碼錯誤' } })
      .mockResolvedValueOnce({ success: true, room: JOINED, users: [] });
    const { onSuccess } = setup(requirements('password'));

    await typePassword('wrong');
    await fireEvent.click(screen.getByRole('button', { name: '加入' }));
    expect(await screen.findByText('密碼錯誤')).toBeTruthy();
    expect(onSuccess).not.toHaveBeenCalled();

    await typePassword(' secret1 ');
    await fireEvent.keyDown(screen.getByPlaceholderText('房間密碼'), { key: 'Enter' });

    expect(await screen.findByText('加入成功！')).toBeTruthy();
    expect(joinRoom).toHaveBeenNthCalledWith(1, 'r1', { password: 'wrong' });
    expect(joinRoom).toHaveBeenNthCalledWith(2, 'r1', { password: 'secret1' });
    expect(onSuccess).toHaveBeenCalledWith(JOINED);
  });

  it('沒有輸入密碼時不能送出', async () => {
    setup(requirements('password'));

    await screen.findByPlaceholderText('房間密碼');

    expect((screen.getByRole('button', { name: '加入' }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('需要邀請碼', () => {
  it('以去掉空白的邀請碼加入', async () => {
    const joinRoom = vi.spyOn(roomStore, 'joinRoom').mockResolvedValue({ success: true, room: JOINED, users: [] });
    setup(requirements('invite'));

    await fireEvent.input(await screen.findByPlaceholderText('邀請碼'), { target: { value: ' abc123 ' } });
    await fireEvent.click(screen.getByRole('button', { name: '加入' }));

    expect(await screen.findByText('加入成功！')).toBeTruthy();
    expect(joinRoom).toHaveBeenCalledWith('r1', { invite_code: 'abc123' });
  });

  it('邀請碼無效時顯示原因', async () => {
    vi.spyOn(roomStore, 'joinRoom').mockResolvedValue({
      success: false,
      message: '邀請碼無效',
      requiresAction: { type: 'error', message: '邀請碼無效' },
    });
    const { onSuccess } = setup(requirements('invite'));

    await fireEvent.input(await screen.findByPlaceholderText('邀請碼'), { target: { value: 'old-code' } });
    await fireEvent.click(screen.getByRole('button', { name: '加入' }));

    expect(await screen.findByText('邀請碼無效')).toBeTruthy();
    expect(screen.getByPlaceholderText('邀請碼')).toBeTruthy();
    expect(onSuccess).not.toHaveBeenCalled();
  });
});

it('取消時關閉', async () => {
  const { onClose } = setup(requirements('password'));

  await screen.findByPlaceholderText('房間密碼');
  await fireEvent.click(screen.getByRole('button', { name: '取消' }));

  expect(onClose).toHaveBeenCalledOnce();
});
