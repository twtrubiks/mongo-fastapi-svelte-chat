// WebSocket 事件進入前端狀態的入口：訊息驗證、通知、已讀同步、訊息與成員事件
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '$lib/api/client';
import { messageStore } from '$lib/stores/message.svelte';
import { messageStatusStore } from '$lib/stores/messageStatus.svelte';
import { notificationStore, soundNotificationManager } from '$lib/stores/notification.svelte';
import { roomStore } from '$lib/stores/room.svelte';
import { typingIndicatorStore } from '$lib/stores/typingIndicator.svelte';
import { authStore } from '$lib/stores/auth.svelte';
import type { Message, Notification, User, WSRoomUsersMessage, WSUserLeftMessage } from '$lib/types';
import { isValidWSMessage } from './guards';
import type { HandlerContext } from './handlers';
import { dispatchNotification, handleNotificationStatusChanged, cancelPendingNotificationRefresh } from './notificationHandlers';
import { handleAck, handleError, handleMessageDeleted, handleMessageHistory, handleTypingIndicator } from './messageHandlers';
import { handleRoomUsers, handleUserJoined, handleUserLeft, resetLastRoomUsersTime } from './roomHandlers';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

// 後端 NotificationService.send_real_time_notification 推送的格式
const PUSHED = {
  id: 'n1',
  user_id: 'u1',
  type: 'message',
  status: 'unread',
  title: '新訊息',
  message: 'bob: 嗨',
  content: 'bob: 嗨',
  data: { room_id: 'r1' },
  metadata: { room_id: 'r1' },
  room_id: 'r1',
  sender_id: 'u2',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function ctx(roomId: string | null = 'r1') {
  return { roomId, emit: vi.fn<HandlerContext['emit']>() };
}

function notification(id: string, status: Notification['status'] = 'UNREAD'): Notification {
  return { ...PUSHED, id, type: 'MESSAGE', status } as Notification;
}

function user(id: string, is_active = false): User {
  return { id, username: `user-${id}`, is_active } as User;
}

beforeEach(() => {
  notificationStore.clearAll();
  notificationStore.updateSettings({ sound: true, browserNotifications: true });
  messageStore.clearMessages();
  messageStatusStore.clearAll();
  typingIndicatorStore.clearAll();
  roomStore.setUsers([]);
  resetLastRoomUsersTime();
});

afterEach(() => {
  cancelPendingNotificationRefresh();
  vi.useRealTimers();
});

describe('isValidWSMessage', () => {
  it.each([
    [{ type: 'message' }, true],
    [{ type: 'notification', data: {} }, true],
    [{ type: 'unknown_event' }, false],
    [{ type: 1 }, false],
    [{ data: {} }, false],
    [null, false],
    ['message', false],
  ])('%o → %s', (data, expected) => {
    expect(isValidWSMessage(data)).toBe(expected);
  });
});

describe('dispatchNotification', () => {
  it('後端推送的通知轉成前端格式加入 store，新的未讀通知播放音效', () => {
    const sound = vi.spyOn(soundNotificationManager, 'playNotificationSound').mockImplementation(() => {});

    dispatchNotification({ type: 'notification', data: PUSHED, timestamp: 't' }, ctx());

    expect(notificationStore.notifications).toEqual([
      expect.objectContaining({ id: 'n1', type: 'MESSAGE', status: 'UNREAD', message: 'bob: 嗨' }),
    ]);
    expect(notificationStore.stats).toMatchObject({ total: 1, unread: 1 });
    expect(sound).toHaveBeenCalledOnce();
  });

  it('重複推送不重複加入也不再播放音效', () => {
    const sound = vi.spyOn(soundNotificationManager, 'playNotificationSound').mockImplementation(() => {});

    dispatchNotification({ type: 'notification', data: PUSHED, timestamp: 't' }, ctx());
    dispatchNotification({ type: 'notification', data: PUSHED, timestamp: 't' }, ctx());

    expect(notificationStore.notifications).toHaveLength(1);
    expect(sound).toHaveBeenCalledOnce();
  });

  it('關閉音效時不播放', () => {
    const sound = vi.spyOn(soundNotificationManager, 'playNotificationSound').mockImplementation(() => {});
    notificationStore.updateSettings({ sound: false });

    dispatchNotification({ type: 'notification', data: PUSHED, timestamp: 't' }, ctx());

    expect(sound).not.toHaveBeenCalled();
  });

  it('結構不完整的通知被丟棄', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});

    dispatchNotification({ type: 'notification', data: { id: 'x', title: 't' }, timestamp: 't' }, ctx());

    expect(notificationStore.notifications).toEqual([]);
  });

  it('包在通知內的房間建立事件轉發為 room_created', () => {
    const context = ctx();
    const data = { type: 'room_created', room: { id: 'r9' } };

    dispatchNotification({ type: 'notification', data, timestamp: 't' }, context);

    expect(context.emit).toHaveBeenCalledWith('room_created', data);
    expect(notificationStore.notifications).toEqual([]);
  });
});

describe('notificationStore', () => {
  it('標記已讀只減少一次未讀數', () => {
    notificationStore.addNotification(notification('a'));
    notificationStore.addNotification(notification('b'));

    notificationStore.markAsRead('a');
    notificationStore.markAsRead('a');

    expect(notificationStore.notifications.find((n) => n.id === 'a')!.status).toBe('READ');
    expect(notificationStore.stats).toMatchObject({ total: 2, unread: 1 });
  });

  it('全部標記已讀', () => {
    notificationStore.addNotification(notification('a'));
    notificationStore.addNotification(notification('b', 'READ'));

    notificationStore.markAllAsRead();

    expect(notificationStore.notifications.every((n) => n.status === 'READ')).toBe(true);
    expect(notificationStore.stats.unread).toBe(0);
  });

  it('刪除未讀通知時同步調整統計', () => {
    notificationStore.addNotification(notification('a'));
    notificationStore.addNotification(notification('b', 'READ'));

    notificationStore.removeNotification('a');
    notificationStore.removeNotification('missing');

    expect(notificationStore.notifications.map((n) => n.id)).toEqual(['b']);
    expect(notificationStore.stats).toMatchObject({ total: 1, unread: 0 });
  });
});

describe('handleNotificationStatusChanged', () => {
  it('單筆已讀', () => {
    notificationStore.addNotification(notification('a'));
    const context = ctx();
    const data = { read_type: 'notification', id: 'a', status: 'read', timestamp: 't' };

    handleNotificationStatusChanged(data, context);

    expect(notificationStore.notifications[0]!.status).toBe('READ');
    expect(context.emit).toHaveBeenCalledWith('read_status_updated', data);
  });

  it('全部已讀', () => {
    notificationStore.addNotification(notification('a'));
    notificationStore.addNotification(notification('b'));

    handleNotificationStatusChanged({ read_type: 'all', id: '', status: 'read', timestamp: 't' }, ctx());

    expect(notificationStore.stats.unread).toBe(0);
  });

  it('房間已讀：延遲後重新抓通知列表，連續事件只抓一次', async () => {
    vi.useFakeTimers();
    notificationStore.addNotification(notification('a'));
    const list = vi
      .spyOn(apiClient.notifications, 'list')
      .mockResolvedValue({ notifications: [notification('a', 'READ')], unread_count: 0 });
    const event = { read_type: 'room', id: 'r1', status: 'read', timestamp: 't' };

    handleNotificationStatusChanged(event, ctx());
    await vi.advanceTimersByTimeAsync(300);
    handleNotificationStatusChanged(event, ctx());
    await vi.advanceTimersByTimeAsync(500);

    expect(list).toHaveBeenCalledOnce();
    expect(notificationStore.notifications[0]!.status).toBe('READ');
  });
});

describe('訊息事件', () => {
  function msg(id: string, extra: Partial<Message> = {}): Message {
    return {
      id,
      room_id: 'r1',
      user_id: 'u1',
      content: id,
      message_type: 'text',
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      ...extra,
    };
  }

  it('歷史訊息略過系統訊息', () => {
    handleMessageHistory({
      type: 'message_history',
      messages: [msg('a'), msg('sys', { message_type: 'system' })],
    } as never);

    expect(messageStore.messages.map((m) => m.id)).toEqual(['a']);
  });

  it('ack 確認樂觀訊息並標記已送達', async () => {
    messageStore.addPendingMessage(msg('tmp', { client_id: 'c1' }));
    messageStatusStore.setSending('c1');

    handleAck({ type: 'ack', client_id: 'c1', message_id: 'm1', seq: 3, room_id: 'r1', timestamp: 't' });
    await vi.waitFor(() => expect(messageStatusStore.getStatus('c1')?.status).toBe('sent'));

    expect(messageStore.messages[0]).toMatchObject({ id: 'm1', seq: 3, pending: false });
  });

  it('刪除事件移除訊息', () => {
    messageStore.addMessage(msg('a'));

    handleMessageDeleted({ type: 'message_deleted', message_id: 'a', room_id: 'r1' } as never);

    expect(messageStore.messages).toEqual([]);
  });

  it('錯誤帶 temp_id 時標記該訊息失敗並轉發事件', () => {
    const context = ctx();
    const data = { type: 'error', message: '內容過長', temp_id: 'c1' } as never;

    handleError(data, context);

    expect(messageStatusStore.getStatus('c1')).toMatchObject({ status: 'failed', error: '內容過長', retryCount: 1 });
    expect(context.emit).toHaveBeenCalledWith('message_error', data);
  });

  it('打字指示器：開始、停止與 5 秒自動過期', () => {
    vi.useFakeTimers();
    const typing = (is_typing: boolean) =>
      handleTypingIndicator(
        { type: 'typing', user: { id: 'u2', username: 'bob' }, is_typing, room_id: 'r1' } as never,
        ctx()
      );

    typing(true);
    expect(typingIndicatorStore.getTypingUsers('r1')).toEqual([{ userId: 'u2', username: 'bob', avatar: undefined }]);
    typing(false);
    expect(typingIndicatorStore.getTypingUsers('r1')).toEqual([]);

    typing(true);
    vi.advanceTimersByTime(5000);
    expect(typingIndicatorStore.getTypingUsers('r1')).toEqual([]);
  });
});

describe('成員事件', () => {
  beforeEach(() => {
    authStore.setAuthState({ user: { id: 'me', username: 'me' } as User });
  });

  it('room_users 以全域在線名單設定所有成員的在線狀態', () => {
    roomStore.setUsers([user('u1', true), user('u2', false)]);
    const data: WSRoomUsersMessage = {
      type: 'room_users',
      users: [user('u3')],
      global_online_user_ids: ['u2', 'u3'],
      timestamp: 't',
      room_id: 'r1',
    };

    handleRoomUsers(data);

    expect(roomStore.users.map((u) => [u.id, u.is_active])).toEqual([
      ['u1', false],
      ['u2', true],
      ['u3', true],
    ]);
  });

  it('沒有全域名單時以本房在線者為準', () => {
    roomStore.setUsers([user('u1', true)]);

    handleRoomUsers({ type: 'room_users', users: [user('u2')], timestamp: 't', room_id: 'r1' });

    expect(roomStore.users.map((u) => [u.id, u.is_active])).toEqual([
      ['u1', false],
      ['u2', true],
    ]);
  });

  it('新成員加入：加入列表並產生系統訊息；自己加入則略過', () => {
    handleUserJoined(user('me'), '2026-01-01T00:00:00Z', ctx());
    handleUserJoined(user('u2'), '2026-01-01T00:00:00Z', ctx());

    expect(roomStore.users.map((u) => u.id)).toEqual(['u2']);
    expect(messageStore.messages.map((m) => m.content)).toEqual(['user-u2 加入了聊天室']);
  });

  function userLeft(id: string, extra: Partial<WSUserLeftMessage> = {}): WSUserLeftMessage {
    return { type: 'user_left', user: user(id), timestamp: '', room_id: 'r1', ...extra };
  }

  it('離線與退出房間的差別', () => {
    roomStore.setUsers([user('u1', true), user('u2', true)]);

    handleUserLeft(userLeft('u1'), ctx());
    handleUserLeft(userLeft('u2', { removed: true }), ctx());

    expect(roomStore.users.map((u) => [u.id, u.is_active])).toEqual([['u1', false]]);
    expect(messageStore.messages).toEqual([]);
  });

  it('其他成員被房主移出：從列表移除，系統訊息寫明被移出', () => {
    roomStore.setUsers([user('u2', true)]);

    handleUserLeft(userLeft('u2', { removed: true, kicked: true, timestamp: '2026-01-01T00:00:00Z' }), ctx());

    expect(roomStore.users).toEqual([]);
    expect(messageStore.messages.map((m) => m.content)).toEqual(['user-u2 已被移出聊天室']);
  });

  it.each([
    ['被房主移出', true, false],
    ['被房主移出並封鎖', true, true],
    ['在其他分頁離開', false, false],
  ])('自己%s：不再是成員，通知頁面離開房間', (_, kicked, banned) => {
    const forgetMembership = vi.spyOn(roomStore, 'forgetMembership').mockImplementation(() => {});
    const context = ctx();

    handleUserLeft(userLeft('me', { removed: true, kicked, banned, timestamp: '2026-01-01T00:00:00Z' }), context);

    expect(forgetMembership).toHaveBeenCalledWith('r1');
    expect(context.emit).toHaveBeenCalledWith('removed_from_room', { room_id: 'r1', kicked, banned });
    expect(messageStore.messages).toEqual([]);
  });

  it('事件沒有名稱時用成員列表裡的名稱，都查不到就不產生系統訊息', () => {
    roomStore.setUsers([user('u2', true)]);

    handleUserLeft(userLeft('u2', { removed: true, kicked: true, timestamp: '2026-01-01T00:00:00Z', user: { id: 'u2' } as User }), ctx());
    handleUserLeft(userLeft('u9', { removed: true, kicked: true, timestamp: '2026-01-01T00:00:01Z', user: { id: 'u9' } as User }), ctx());

    expect(messageStore.messages.map((m) => m.content)).toEqual(['user-u2 已被移出聊天室']);
  });

  it('自己只是斷線（沒有移除成員資格）時不離開房間', () => {
    const context = ctx();

    handleUserLeft(userLeft('me'), context);

    expect(context.emit).not.toHaveBeenCalled();
  });
});
