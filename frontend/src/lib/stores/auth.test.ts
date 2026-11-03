import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { apiClient } from '../api/client';
import { wsManager } from '../websocket/manager';
import { authStore } from './auth.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn(async () => {}) }));

const USER = { id: 'u1', username: 'alice', email: 'alice@example.com' } as const;

// server 測試環境沒有 window；handleAuthFailure 會讀目前網址
function setLocation(path: string) {
  vi.stubGlobal('window', { location: new URL(path, 'http://localhost') });
}

beforeEach(() => {
  vi.mocked(goto).mockClear();
  authStore.setAuthState({ user: { ...USER } as never });
  setLocation('/');
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('authStore 登入失效處理', () => {
  it('BFF 換發也失敗時登出並回到登入頁', async () => {
    const logout = vi.spyOn(apiClient.auth, 'logout').mockResolvedValue();
    const destroy = vi.spyOn(wsManager, 'destroy').mockImplementation(() => {});
    authStore.init();

    await apiClient.onAuthFailure?.();

    expect(logout).toHaveBeenCalledOnce();
    expect(destroy).toHaveBeenCalledOnce();
    expect(authStore.user).toBeNull();
    expect(goto).toHaveBeenCalledWith('/login');
  });

  it('在 /app 底下失效時，登入頁帶上目前頁面以便登入後回來', async () => {
    vi.spyOn(apiClient.auth, 'logout').mockResolvedValue();
    vi.spyOn(wsManager, 'destroy').mockImplementation(() => {});
    authStore.init();
    setLocation('/app/room/r1');

    await apiClient.onAuthFailure?.();

    expect(goto).toHaveBeenCalledWith('/login?redirect=%2Fapp%2Froom%2Fr1');
  });

  it('多個請求同時 401 只處理一次', async () => {
    let finishLogout!: () => void;
    const logout = vi
      .spyOn(apiClient.auth, 'logout')
      .mockImplementation(() => new Promise<void>((resolve) => (finishLogout = resolve)));
    vi.spyOn(wsManager, 'destroy').mockImplementation(() => {});
    authStore.init();

    const first = apiClient.onAuthFailure?.();
    const second = apiClient.onAuthFailure?.();
    finishLogout();
    await Promise.all([first, second]);

    expect(logout).toHaveBeenCalledOnce();
    expect(goto).toHaveBeenCalledOnce();
  });

  it('處理完後下一次失效仍會處理', async () => {
    const logout = vi.spyOn(apiClient.auth, 'logout').mockResolvedValue();
    vi.spyOn(wsManager, 'destroy').mockImplementation(() => {});
    authStore.init();

    await apiClient.onAuthFailure?.();
    await apiClient.onAuthFailure?.();

    expect(logout).toHaveBeenCalledTimes(2);
  });
});
