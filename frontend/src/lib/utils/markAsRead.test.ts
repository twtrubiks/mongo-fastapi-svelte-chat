// 房間已讀：進房與收到新訊息時標記通知已讀
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { apiClient } from '$lib/api/client';
import { notificationStore } from '$lib/stores/notification.svelte';
import type { Notification } from '$lib/types';
import { wsManager } from '$lib/websocket/manager';
import { createMarkAsReadTracker, executeMarkAsRead } from './markAsRead';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

function notification(id: string, roomId: string, status: Notification['status'] = 'UNREAD'): Notification {
  return {
    id, user_id: 'u1', type: 'MESSAGE', status, title: '新訊息', message: '嗨', room_id: roomId,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
  };
}

let list: MockInstance<typeof apiClient.notifications.list>;
let markApi: MockInstance<typeof apiClient.notifications.markAsRead>;
let wsRead: MockInstance<ReturnType<typeof wsManager.getInstance>['markRoomMessagesRead']>;

beforeEach(() => {
  vi.useFakeTimers();
  vi.spyOn(console, 'error').mockImplementation(() => {});
  notificationStore.clearAll();
  list = vi.spyOn(apiClient.notifications, 'list').mockResolvedValue({
    notifications: [notification('a1', 'A'), notification('a2', 'A', 'READ'), notification('b1', 'B')],
    unread_count: 2,
  });
  markApi = vi.spyOn(apiClient.notifications, 'markAsRead').mockResolvedValue();
  wsRead = vi.spyOn(wsManager.getInstance(), 'markRoomMessagesRead').mockReturnValue(true);
});

afterEach(() => {
  wsManager.destroy();
  vi.useRealTimers();
});

const status = (id: string) => notificationStore.notifications.find((n) => n.id === id)?.status;

describe('executeMarkAsRead', () => {
  it('透過 WebSocket 標記房間已讀，並逐一標記該房間的未讀通知', async () => {
    const done = executeMarkAsRead('A');
    await vi.runAllTimersAsync();
    await done;

    expect(wsRead).toHaveBeenCalledWith('A');
    expect(markApi.mock.calls).toEqual([['a1']]);
    expect(status('a1')).toBe('READ');
    expect(status('b1')).toBe('UNREAD');
  });

  it('其中一則標記失敗時，其餘照常標記', async () => {
    list.mockResolvedValue({ notifications: [notification('a1', 'A'), notification('a2', 'A')], unread_count: 2 });
    markApi.mockRejectedValueOnce(new Error('網路錯誤'));

    const done = executeMarkAsRead('A');
    await vi.runAllTimersAsync();
    await done;

    expect(markApi.mock.calls).toEqual([['a1'], ['a2']]);
    expect(status('a1')).toBe('UNREAD');
    expect(status('a2')).toBe('READ');
  });

  it('forceRefresh 時，標記完 1 秒後重新載入通知', async () => {
    const done = executeMarkAsRead('A', { forceRefresh: true });
    // 每標記一則等 50ms，之後再等 1 秒
    await vi.advanceTimersByTimeAsync(1049);
    expect(list).toHaveBeenCalledTimes(1);

    list.mockResolvedValue({ notifications: [notification('c1', 'C')], unread_count: 1 });
    await vi.advanceTimersByTimeAsync(1);
    await done;

    expect(list).toHaveBeenCalledTimes(2);
    expect(notificationStore.notifications.map((n) => n.id)).toEqual(['c1']);
  });

  it('載入通知失敗時不拋出錯誤', async () => {
    list.mockRejectedValue(new Error('網路錯誤'));

    await expect(executeMarkAsRead('A')).resolves.toBeUndefined();
    expect(wsRead).toHaveBeenCalledWith('A');
  });
});

describe('createMarkAsReadTracker', () => {
  it('進房 500ms 後標記已讀；同一個房間不重複標記', async () => {
    const tracker = createMarkAsReadTracker();

    expect(tracker.onRoomEnter('A', 3)).toBeTypeOf('function');
    await vi.advanceTimersByTimeAsync(499);
    expect(wsRead).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    await vi.runAllTimersAsync();
    expect(wsRead).toHaveBeenCalledTimes(1);

    expect(tracker.onRoomEnter('A', 3)).toBeUndefined();
    await vi.runAllTimersAsync();
    expect(wsRead).toHaveBeenCalledTimes(1);
  });

  it('500ms 內離開房間（cleanup）就不標記；之後換到別的房間照常標記', async () => {
    const tracker = createMarkAsReadTracker();

    const cleanup = tracker.onRoomEnter('A', 3)!;
    await vi.advanceTimersByTimeAsync(300);
    cleanup();
    tracker.onRoomEnter('B', 1);
    await vi.runAllTimersAsync();

    expect(wsRead.mock.calls).toEqual([['B']]);
  });

  it('訊息數增加時，3 秒內只標記一次', async () => {
    const tracker = createMarkAsReadTracker();
    tracker.initMessageCount(3);

    tracker.onNewMessage('A', 4);
    await vi.advanceTimersByTimeAsync(2000);
    tracker.onNewMessage('A', 5);
    await vi.advanceTimersByTimeAsync(2999);
    expect(wsRead).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    await vi.runAllTimersAsync();
    expect(wsRead.mock.calls).toEqual([['A']]);
  });

  it('訊息數沒有增加或尚未初始化時不標記', async () => {
    const tracker = createMarkAsReadTracker();

    tracker.onNewMessage('A', 3); // 尚未初始化：只記下數量
    tracker.onNewMessage('A', 3);
    tracker.onNewMessage('A', 2); // 例如訊息被刪除
    await vi.runAllTimersAsync();

    expect(wsRead).not.toHaveBeenCalled();
  });

  it('destroy 取消尚未執行的標記', async () => {
    const tracker = createMarkAsReadTracker();
    tracker.initMessageCount(0);

    tracker.onRoomEnter('A', 0);
    tracker.onNewMessage('A', 1);
    tracker.destroy();
    await vi.runAllTimersAsync();

    expect(wsRead).not.toHaveBeenCalled();
  });
});
