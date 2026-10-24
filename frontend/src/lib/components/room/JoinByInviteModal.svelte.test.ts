// 以邀請碼加入：先驗證邀請碼再加入，加入失敗時不能當作已加入
import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { roomStore } from '$lib/stores';
import JoinByInviteModal from './JoinByInviteModal.svelte';

const ROOM = { id: 'r9', name: '讀書會' };

function setup() {
  const onSuccess = vi.fn();
  const onClose = vi.fn();
  render(JoinByInviteModal, { open: true, onSuccess, onClose });
  return { onSuccess, onClose };
}

async function submit(code: string) {
  await fireEvent.input(screen.getByPlaceholderText('請輸入邀請碼'), { target: { value: code } });
  await fireEvent.click(screen.getByRole('button', { name: '加入房間' }));
}

beforeEach(() => {
  vi.spyOn(roomStore, 'validateInvitation').mockResolvedValue({ valid: true, room: ROOM });
});

describe('以邀請碼加入', () => {
  it('加入成功時關閉視窗並通知', async () => {
    const joinRoom = vi.spyOn(roomStore, 'joinRoom').mockResolvedValue({ success: true, room: ROOM as never, users: [] });
    const { onSuccess } = setup();

    await submit(' abc123 ');

    expect(joinRoom).toHaveBeenCalledWith('r9', { invite_code: 'abc123' });
    expect(onSuccess).toHaveBeenCalledWith(ROOM);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('邀請碼通過驗證但加入失敗時，留在視窗並顯示原因', async () => {
    vi.spyOn(roomStore, 'joinRoom').mockResolvedValue({
      success: false,
      message: '需要提供密碼',
      requiresAction: { type: 'password', message: '此聊天室需要密碼才能加入' },
    });
    const { onSuccess } = setup();

    await submit('abc123');

    expect(await screen.findByText('此聊天室需要密碼才能加入')).toBeTruthy();
    expect(onSuccess).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeTruthy();
  });

  it('邀請碼驗證失敗時顯示原因，不嘗試加入', async () => {
    vi.spyOn(roomStore, 'validateInvitation').mockRejectedValue(new Error('邀請碼無效或已過期'));
    const joinRoom = vi.spyOn(roomStore, 'joinRoom');
    setup();

    await submit('wrong');

    expect(await screen.findByText('邀請碼驗證失敗：邀請碼無效或已過期')).toBeTruthy();
    expect(joinRoom).not.toHaveBeenCalled();
  });
});
