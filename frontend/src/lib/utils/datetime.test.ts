import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';
import { formatDateTime, formatTime, groupMessagesByDate } from './datetime';

// 以台灣時區（UTC+8）驗證「本地時間」的行為；Node 允許執行期切換 TZ
const originalTz = process.env['TZ'];
beforeAll(() => {
  process.env['TZ'] = 'Asia/Taipei';
});
afterAll(() => {
  process.env['TZ'] = originalTz;
});

describe('formatTime', () => {
  it.each([
    ['2026-01-01T23:30:00Z', '07:30'],
    ['2026-01-01T23:30:00+00:00', '07:30'],
    ['2026-01-01T23:30:00.123456Z', '07:30'],
  ])('%s 顯示為本地時間 %s', (input, expected) => {
    expect(formatTime(input)).toBe(expected);
  });

  it('缺少時區標識時視為 UTC', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    expect(formatTime('2026-01-01T23:30:00')).toBe('07:30');
  });
});

describe('formatDateTime', () => {
  it.each([
    [30 * 1000, '剛剛'],
    [5 * 60 * 1000, '5 分鐘前'],
    [3 * 60 * 60 * 1000, '3 小時前'],
    [2 * 24 * 60 * 60 * 1000, '2 天前'],
  ])('%i 毫秒前 → %s', (ago, expected) => {
    expect(formatDateTime(new Date(Date.now() - ago).toISOString())).toBe(expected);
  });

  it('超過 7 天顯示本地日期', () => {
    vi.useFakeTimers({ now: new Date('2026-06-01T00:00:00Z') });
    try {
      expect(formatDateTime('2026-01-01T23:30:00Z')).toBe('01-02');
      expect(formatDateTime('2025-12-31T23:30:00Z')).toBe('01-01');
      expect(formatDateTime('2025-12-30T00:00:00Z')).toBe('2025-12-30');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('groupMessagesByDate', () => {
  const msg = (id: string, created_at: string) => ({ id, created_at });

  it('以本地日期分組（UTC 跨日但本地同一天的訊息在同一組）', () => {
    const groups = groupMessagesByDate([
      msg('morning', '2026-01-01T23:30:00Z'), // 台灣 1/2 07:30
      msg('noon', '2026-01-02T04:00:00Z'), // 台灣 1/2 12:00
      msg('night', '2026-01-01T15:00:00Z'), // 台灣 1/1 23:00
    ]);

    expect(groups.map((g) => [g.date, g.messages.map((m) => m.id)])).toEqual([
      ['2026-01-01', ['night']],
      ['2026-01-02', ['morning', 'noon']],
    ]);
  });

  it('同一天內由舊到新排序，略過缺少時間的訊息', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});

    const groups = groupMessagesByDate([
      msg('b', '2026-01-02T03:00:00Z'),
      msg('a', '2026-01-02T01:00:00Z'),
      msg('x', ''),
    ]);

    expect(groups).toEqual([{ date: '2026-01-02', messages: [msg('a', '2026-01-02T01:00:00Z'), msg('b', '2026-01-02T03:00:00Z')] }]);
  });
});
