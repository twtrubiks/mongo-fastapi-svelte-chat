// 通知面板：開啟時載入、點通知前往訊息、全部已讀 / 清除 / 刪除，以及 API 失敗時與伺服器同步
import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { apiClient } from '$lib/api/client';
import { notificationStore, notifications, unreadCount } from '$lib/stores/notification.svelte';
import type { Notification } from '$lib/types';
import NotificationPanel from './NotificationPanel.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

function notification(id: string, overrides: Partial<Notification> = {}): Notification {
  return {
    id,
    user_id: 'me',
    type: 'MESSAGE',
    status: 'UNREAD',
    title: `標題 ${id}`,
    message: `內容 ${id}`,
    data: { message_id: `m-${id}` },
    room_id: 'r1',
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

const SERVER = [notification('n1'), notification('n2', { type: 'SYSTEM', status: 'READ', room_id: undefined as never })];

function serverList(list: Notification[] = SERVER) {
  return vi.spyOn(apiClient.notifications, 'list').mockResolvedValue({ notifications: list } as never);
}

function setup() {
  const onClose = vi.fn();
  render(NotificationPanel, { isOpen: true, onClose });
  return { onClose };
}

beforeEach(() => {
  notificationStore.clearAll();
  vi.mocked(goto).mockClear();
});

describe('載入', () => {
  it('開啟時向伺服器載入一次通知並顯示', async () => {
    const list = serverList();
    setup();

    expect(await screen.findByText('標題 n1')).toBeTruthy();
    expect(screen.getByText('內容 n2')).toBeTruthy();
    expect(list).toHaveBeenCalledOnce();
  });

  it('載入失敗時顯示原因，可重試', async () => {
    const list = vi
      .spyOn(apiClient.notifications, 'list')
      .mockRejectedValueOnce(new Error('網路連線失敗'))
      .mockResolvedValueOnce({ notifications: SERVER } as never);
    setup();

    expect(await screen.findByText('網路連線失敗')).toBeTruthy();
    await fireEvent.click(screen.getByRole('button', { name: '重試' }));

    expect(await screen.findByText('標題 n1')).toBeTruthy();
    expect(list).toHaveBeenCalledTimes(2);
  });

  it('沒有通知時顯示空狀態，不能全部已讀或清除', async () => {
    serverList([]);
    setup();

    expect(await screen.findByText('暫無通知')).toBeTruthy();
    expect((screen.getByRole('button', { name: '全部已讀' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '清除全部' }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('點選通知', () => {
  it('訊息通知：標記已讀、前往該訊息並關閉面板', async () => {
    serverList();
    const markAsRead = vi.spyOn(apiClient.notifications, 'markAsRead').mockResolvedValue();
    const { onClose } = setup();

    await fireEvent.click(await screen.findByText('標題 n1'));

    expect(goto).toHaveBeenCalledWith('/app/room/r1?message=m-n1');
    expect(onClose).toHaveBeenCalledOnce();
    await vi.waitFor(() => expect(unreadCount()).toBe(0));
    expect(markAsRead).toHaveBeenCalledWith('n1');
  });

  it('刪除單則通知不會觸發前往', async () => {
    serverList();
    const remove = vi.spyOn(apiClient.notifications, 'delete').mockResolvedValue();
    setup();

    const item = (await screen.findByText('標題 n1')).closest('[role="button"]') as HTMLElement;
    await fireEvent.click(within(item).getByRole('button', { name: '刪除' }));

    expect(remove).toHaveBeenCalledWith('n1');
    expect(goto).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(screen.queryByText('標題 n1')).toBeNull());
  });
});

describe('全部已讀與清除', () => {
  it('全部已讀立即反映在畫面上', async () => {
    serverList();
    vi.spyOn(apiClient.notifications, 'markAllAsRead').mockResolvedValue();
    setup();
    await screen.findByText('標題 n1');

    await fireEvent.click(screen.getByRole('button', { name: '全部已讀' }));

    expect(unreadCount()).toBe(0);
  });

  // 樂觀更新後 API 失敗：不能停在「已讀」，否則畫面與伺服器不一致，未讀數也被清掉
  it('全部已讀失敗時，回到伺服器上的狀態', async () => {
    const list = serverList();
    vi.spyOn(apiClient.notifications, 'markAllAsRead').mockRejectedValue(new Error('伺服器錯誤'));
    setup();
    await screen.findByText('標題 n1');

    await fireEvent.click(screen.getByRole('button', { name: '全部已讀' }));

    await vi.waitFor(() => expect(list).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(unreadCount()).toBe(1));
  });

  it('清除全部失敗時，重新載入伺服器上的通知', async () => {
    serverList();
    vi.spyOn(apiClient.notifications, 'clearAll').mockRejectedValue(new Error('伺服器錯誤'));
    setup();
    await screen.findByText('標題 n1');

    await fireEvent.click(screen.getByRole('button', { name: '清除全部' }));

    expect(await screen.findByText('標題 n1')).toBeTruthy();
    expect(notifications().map((n) => n.id)).toEqual(['n1', 'n2']);
  });
});
