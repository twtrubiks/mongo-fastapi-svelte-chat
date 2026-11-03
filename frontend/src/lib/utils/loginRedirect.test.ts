import { describe, expect, it } from 'vitest';
import { loginUrl, safeReturnPath } from './loginRedirect';

describe('safeReturnPath', () => {
  it.each([
    ['/app', '/app'],
    ['/app/room/abc', '/app/room/abc'],
    ['/app/rooms?tab=all#top', '/app/rooms?tab=all#top'],
  ])('接受站內 /app 路徑：%s', (raw, expected) => {
    expect(safeReturnPath(raw)).toBe(expected);
  });

  it.each([
    [null],
    [undefined],
    [''],
    ['app/room/abc'],
    ['https://evil.com/app'],
    ['//evil.com/app'],
    ['/\\evil.com/app'],
    ['javascript:alert(1)'],
    ['/login'],
    ['/application'],
    ['/app/../login'],
  ])('拒絕外站、非 /app 或繞路的路徑：%s', (raw) => {
    expect(safeReturnPath(raw)).toBeNull();
  });
});

describe('loginUrl', () => {
  it('帶上要回到的頁面', () => {
    expect(loginUrl('/app/room/abc?x=1')).toBe('/login?redirect=%2Fapp%2Froom%2Fabc%3Fx%3D1');
  });

  it('不是 /app 底下的頁面就不帶 redirect', () => {
    expect(loginUrl('/')).toBe('/login');
    expect(loginUrl('/login')).toBe('/login');
  });
});
