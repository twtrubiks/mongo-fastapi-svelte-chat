import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../api/client';
import type { Room, RoomSummary, User } from '../types';
import { roomStore } from './room.svelte';
import { deferred } from '../../tests/deferred';

function summary(id: string, extra: Partial<RoomSummary> = {}): RoomSummary {
  return {
    id,
    name: `房間 ${id}`,
    description: '',
    owner_id: 'owner',
    member_count: 1,
    is_member: false,
    is_public: true,
    created_at: '2026-01-01T00:00:00Z',
    ...extra,
  };
}

function room(id: string): Room {
  return { ...summary(id, { is_member: true }), members: ['me'] } as unknown as Room;
}

function user(id: string, is_active = true): User {
  return { id, username: `user-${id}`, is_active } as User;
}

/**
 * 依後端語意模擬探索列表：排除已加入的公開房間後以 offset/limit 分頁，
 * 讓測試能觀察本地列表與後端分頁位移是否一致
 */
function fakeExplore(total: number) {
  const all = Array.from({ length: total }, (_, i) => summary(`r${i}`));
  const joined = new Set<string>();
  const deleted = new Set<string>();
  const visible = () => all.filter((r) => !joined.has(r.id) && !deleted.has(r.id));
  vi.spyOn(apiClient.rooms, 'list').mockImplementation(async (options = {}) => {
    const offset = options.offset ?? 0;
    return visible().slice(offset, offset + (options.limit ?? 50));
  });
  return { joined, deleted, visible };
}

beforeEach(() => {
  Object.assign(roomStore.state, {
    currentRoom: null,
    rooms: [],
    myRooms: [],
    activeTab: 'joined',
    searchQuery: '',
    users: [],
    loading: false,
    hasMoreRooms: true,
    roomsOffset: 0,
    loadingMoreRooms: false,
    hasMoreMyRooms: true,
    myRoomsOffset: 0,
    loadingMoreMyRooms: false,
    hasMoreMembers: true,
    membersOffset: 0,
    loadingMoreMembers: false,
  });
});

const roomIds = (list: RoomSummary[]) => list.map((r) => r.id);

describe('探索列表分頁', () => {
  it('第一頁 25 筆，排除已加入並帶搜尋字詞', async () => {
    const list = vi.spyOn(apiClient.rooms, 'list').mockResolvedValue([summary('a')]);
    roomStore.state.searchQuery = '  大廳 ';

    await roomStore.loadRooms(true);

    expect(list).toHaveBeenCalledWith({ limit: 25, offset: 0, search: '大廳', exclude_joined: true });
    expect(roomIds(roomStore.rooms)).toEqual(['a']);
    expect(roomStore.hasMoreRooms).toBe(false);
  });

  it('載入更多時接續 offset 並去重', async () => {
    fakeExplore(30);

    await roomStore.loadRooms(true);
    await roomStore.loadMoreRooms();

    expect(roomStore.rooms).toHaveLength(30);
    expect(roomStore.hasMoreRooms).toBe(false);
  });

  // 加入後該房間從後端探索結果消失，後面的房間往前移一格
  it('從探索加入房間後，下一頁不會漏掉房間', async () => {
    const backend = fakeExplore(30);
    vi.spyOn(apiClient.rooms, 'join').mockImplementation(async (id) => {
      backend.joined.add(id);
    });
    vi.spyOn(apiClient.rooms, 'get').mockResolvedValue(room('r3'));
    vi.spyOn(apiClient.rooms, 'getMembers').mockResolvedValue([]);

    await roomStore.loadRooms(true);
    await roomStore.joinRoom('r3');
    await roomStore.loadMoreRooms();

    expect(roomIds(roomStore.rooms).sort()).toEqual(roomIds(backend.visible()).sort());
    expect(roomIds(roomStore.myRooms)).toEqual(['r3']);
  });

  it('探索列表中的房間被刪除後，下一頁不會漏掉房間', async () => {
    const backend = fakeExplore(30);

    await roomStore.loadRooms(true);
    backend.deleted.add('r5');
    roomStore.removeRoom('r5');
    await roomStore.loadMoreRooms();

    expect(roomIds(roomStore.rooms).sort()).toEqual(roomIds(backend.visible()).sort());
  });

  it('不在已載入列表的房間被刪除時 offset 不變', async () => {
    const backend = fakeExplore(30);

    await roomStore.loadRooms(true);
    backend.deleted.add('r28');
    roomStore.removeRoom('r28');
    await roomStore.loadMoreRooms();

    expect(roomIds(roomStore.rooms).sort()).toEqual(roomIds(backend.visible()).sort());
  });

  it('沒有更多或正在載入時不重複請求', async () => {
    const list = vi.spyOn(apiClient.rooms, 'list');
    roomStore.state.hasMoreRooms = false;

    await roomStore.loadMoreRooms();

    expect(list).not.toHaveBeenCalled();
  });
});

describe('已加入列表與分頁籤', () => {
  it('載入已加入的房間', async () => {
    const myRooms = vi.spyOn(apiClient.rooms, 'myRooms').mockResolvedValue([summary('m1', { is_member: true })]);

    await roomStore.loadMyRooms(true);

    expect(myRooms).toHaveBeenCalledWith({ limit: 25, offset: 0 });
    expect(roomIds(roomStore.myRooms)).toEqual(['m1']);
    expect(roomStore.hasMoreMyRooms).toBe(false);
  });

  it('切到探索時清除已加入分頁的搜尋字詞並載入', async () => {
    const list = vi.spyOn(apiClient.rooms, 'list').mockResolvedValue([]);
    roomStore.state.searchQuery = '舊搜尋';

    await roomStore.switchTab('explore');

    expect(roomStore.activeTab).toBe('explore');
    expect(roomStore.searchQuery).toBe('');
    expect(list).toHaveBeenCalledWith({ limit: 25, offset: 0, exclude_joined: true });
  });

  it('從探索搜尋切回時清掉過期的搜尋結果', async () => {
    vi.spyOn(apiClient.rooms, 'myRooms').mockResolvedValue([]);
    Object.assign(roomStore.state, { activeTab: 'explore', searchQuery: 'x', rooms: [summary('hit')] });

    await roomStore.switchTab('joined');

    expect(roomStore.rooms).toEqual([]);
  });

  it('已載入的分頁籤不重複請求', async () => {
    const myRooms = vi.spyOn(apiClient.rooms, 'myRooms');
    Object.assign(roomStore.state, { activeTab: 'explore', myRooms: [summary('m1')] });

    await roomStore.switchTab('joined');

    expect(myRooms).not.toHaveBeenCalled();
  });
});

describe('房間與成員', () => {
  it('載入房間時成員預設離線（API 的 is_active 是帳號啟用，不是在線）', async () => {
    vi.spyOn(apiClient.rooms, 'get').mockResolvedValue(room('r1'));
    vi.spyOn(apiClient.rooms, 'getMembers').mockResolvedValue([user('u1', true), user('u2', true)]);

    await roomStore.loadRoom('r1');

    expect(roomStore.currentRoom?.id).toBe('r1');
    expect(roomStore.users.map((u) => u.is_active)).toEqual([false, false]);
    expect(roomStore.hasMoreMembers).toBe(false);
  });

  // 快速切換房間：A 的回應比 B 晚回來
  it('較早發出、較晚回來的房間不覆蓋目前房間與成員', async () => {
    const roomA = deferred<Room>();
    vi.spyOn(apiClient.rooms, 'get').mockImplementation((id) => (id === 'A' ? roomA.promise : Promise.resolve(room('B'))));
    vi.spyOn(apiClient.rooms, 'getMembers').mockImplementation(async (id) => [user(`${id}-member`)]);

    const loadA = roomStore.loadRoom('A');
    await roomStore.loadRoom('B');
    roomA.resolve(room('A'));
    await loadA;

    expect(roomStore.currentRoom?.id).toBe('B');
    expect(roomStore.users.map((u) => u.id)).toEqual(['B-member']);
    expect(roomStore.loading).toBe(false);
  });

  it('載入更多成員時去重並保留已知在線狀態', async () => {
    Object.assign(roomStore.state, { users: [user('u1', true)], membersOffset: 1 });
    const getMembers = vi
      .spyOn(apiClient.rooms, 'getMembers')
      .mockResolvedValue([user('u1', false), user('u2', true)]);

    await roomStore.loadMoreMembers('r1');

    expect(getMembers).toHaveBeenCalledWith('r1', { limit: 50, offset: 1 });
    expect(roomStore.users.map((u) => [u.id, u.is_active])).toEqual([
      ['u1', true],
      ['u2', false],
    ]);
  });

  it('建立房間只放進已加入列表', async () => {
    vi.spyOn(apiClient.rooms, 'create').mockResolvedValue(room('new'));

    await roomStore.createRoom({ name: '新房間' } as never);

    expect(roomIds(roomStore.myRooms)).toEqual(['new']);
    expect(roomStore.rooms).toEqual([]);
  });

  it('離開房間：移出已加入列表、清掉目前房間並重新整理探索列表', async () => {
    vi.spyOn(apiClient.rooms, 'leave').mockResolvedValue();
    const list = vi.spyOn(apiClient.rooms, 'list').mockResolvedValue([summary('r1')]);
    Object.assign(roomStore.state, { myRooms: [summary('r1')], currentRoom: room('r1'), users: [user('u1')] });

    await roomStore.leaveRoom('r1');

    expect(roomStore.myRooms).toEqual([]);
    expect(roomStore.currentRoom).toBeNull();
    expect(roomStore.users).toEqual([]);
    expect(list).toHaveBeenCalled();
  });

  // 自己離開時，WS 的 user_left 與 HTTP 回應都會呼叫 forgetMembership
  it('同一個房間的成員資格只清一次，探索列表只重新整理一次', () => {
    const list = vi.spyOn(apiClient.rooms, 'list').mockResolvedValue([]);
    Object.assign(roomStore.state, { myRooms: [summary('r1')], currentRoom: room('r1') });

    roomStore.forgetMembership('r1');
    roomStore.forgetMembership('r1');

    expect(roomStore.myRooms).toEqual([]);
    expect(list).toHaveBeenCalledOnce();
  });
});

describe('封鎖', () => {
  // 成員列表平常由 user_left 事件同步；房主的 WS 剛好斷線時，被封鎖的人會留在可移出的列表
  it('以名稱封鎖到目前成員時，立即從成員列表移除', async () => {
    vi.spyOn(apiClient.rooms, 'banUser').mockResolvedValue(user('u2'));
    roomStore.setUsers([user('u1', true), user('u2', true)]);

    const banned = await roomStore.banUser('r1', 'user-u2');

    expect(banned.id).toBe('u2');
    expect(roomStore.users.map((u) => u.id)).toEqual(['u1']);
  });
});

describe('即時房間事件', () => {
  it('新房間加到探索列表最前面且不重複', () => {
    Object.assign(roomStore.state, { rooms: [summary('a')] });

    roomStore.addNewRoom(summary('b'));
    roomStore.addNewRoom(summary('b'));

    expect(roomIds(roomStore.rooms)).toEqual(['b', 'a']);
  });

  it('刪除房間時從兩個列表移除，並清掉目前房間', () => {
    Object.assign(roomStore.state, {
      rooms: [summary('a')],
      myRooms: [summary('a')],
      currentRoom: room('a'),
      users: [user('u1')],
    });

    roomStore.removeRoom('a');

    expect(roomStore.state).toMatchObject({ rooms: [], myRooms: [], currentRoom: null, users: [] });
  });

  it('更新事件不會把已加入的房間塞回探索列表', () => {
    Object.assign(roomStore.state, { myRooms: [summary('a')], currentRoom: room('a') });

    roomStore.updateRoomRealtime(summary('a', { name: '新名稱' }));

    expect(roomStore.rooms).toEqual([]);
    expect(roomStore.myRooms[0]!.name).toBe('新名稱');
    expect(roomStore.currentRoom).toMatchObject({ name: '新名稱', members: ['me'] });
  });
});
