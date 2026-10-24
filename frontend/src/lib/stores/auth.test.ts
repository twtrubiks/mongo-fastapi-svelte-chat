import { beforeEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { apiClient } from '../api/client';
import { wsManager } from '../websocket/manager';
import { authStore } from './auth.svelte';

vi.mock('$app/navigation', () => ({ goto: vi.fn(async () => {}) }));

const USER = { id: 'u1', username: 'alice', email: 'alice@example.com' } as const;

beforeEach(() => {
  vi.mocked(goto).mockClear();
  authStore.setAuthState({ user: { ...USER } as never });
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
