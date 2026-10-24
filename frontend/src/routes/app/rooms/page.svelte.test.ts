// 房間入口頁：沒有已加入的房間時自動加入一個公開房；加入被拒時要說明原因
import { render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { apiClient } from '$lib/api/client';
import { authStore } from '$lib/stores/auth.svelte';
import { roomStore } from '$lib/stores/room.svelte';
import { JoinPolicy, RoomType } from '$lib/types';
import type { RoomSummary, User } from '$lib/types';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

const OPEN_ROOM = {
  id: 'r1',
  name: '大廳',
  is_member: false,
  join_policy: JoinPolicy.DIRECT,
  room_type: RoomType.PUBLIC,
} as RoomSummary;

beforeEach(() => {
  vi.mocked(goto).mockClear();
  authStore.setAuthState({ user: { id: 'u1', username: 'alice' } as User });
  vi.spyOn(roomStore, 'loadMyRooms').mockResolvedValue([]);
  vi.spyOn(apiClient.rooms, 'list').mockResolvedValue([OPEN_ROOM]);
});

it('沒有已加入的房間時，自動加入公開房並進入', async () => {
  const joinRoom = vi.spyOn(roomStore, 'joinRoom').mockResolvedValue({ success: true } as never);

  render(Page);

  await vi.waitFor(() => expect(goto).toHaveBeenCalledWith('/app/room/r1', { replaceState: true }));
  expect(joinRoom).toHaveBeenCalledWith('r1');
});

// 被封鎖的人沒有其他房間時，房間頁會導到這裡，這裡又會挑中同一個房間
it('自動加入被拒（被房主封鎖）時說明原因，不顯示成沒有聊天室', async () => {
  vi.spyOn(roomStore, 'joinRoom').mockRejectedValue(new Error('你已被房主禁止加入此聊天室'));

  render(Page);

  expect(await screen.findByText('你已被房主禁止加入此聊天室')).toBeTruthy();
  expect(screen.getByText('尚未加入任何聊天室')).toBeTruthy();
  expect(goto).not.toHaveBeenCalled();
});
