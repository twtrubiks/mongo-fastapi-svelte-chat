// 經由 BFF 建立測試資料；名稱加上隨機後綴，可重複對同一個資料庫執行
import type { APIRequestContext } from '@playwright/test';

export const PASSWORD = 'password123';

export interface TestUser {
  id: string;
  username: string;
}

export interface TestRoom {
  id: string;
  name: string;
  invite_code?: string;
}

export const uniqueSuffix = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

async function data<T>(response: Awaited<ReturnType<APIRequestContext['get']>>, action: string): Promise<T> {
  if (!response.ok()) {
    throw new Error(`${action}失敗：${response.status()} ${await response.text()}`);
  }
  return ((await response.json()) as { data: T }).data;
}

// 註冊後 api 會帶著登入 cookie
export async function registerUser(api: APIRequestContext, prefix: string): Promise<TestUser> {
  const username = `${prefix}${uniqueSuffix()}`;
  const response = await api.post('/api/auth/register', {
    data: { username, email: `${username}@example.com`, password: PASSWORD },
  });
  return (await data<{ user: TestUser }>(response, '註冊')).user;
}

export async function createRoom(
  api: APIRequestContext,
  name: string,
  settings: Record<string, unknown> = { room_type: 'public', join_policy: 'direct' },
): Promise<TestRoom> {
  const response = await api.post('/api/rooms', { data: { name, ...settings } });
  const room = await data<{ id: string; invite_code?: string }>(response, '建立房間');
  return { id: room.id, name, ...(room.invite_code ? { invite_code: room.invite_code } : {}) };
}

export async function postMessage(api: APIRequestContext, roomId: string, content: string) {
  const response = await api.post(`/api/rooms/${roomId}/messages`, {
    data: { content, message_type: 'text' },
  });
  await data(response, '送出訊息');
}

export async function messageContents(api: APIRequestContext, roomId: string): Promise<string[]> {
  const messages = await data<Array<{ content: string }>>(await api.get(`/api/rooms/${roomId}/messages`), '讀取訊息');
  return messages.map((message) => message.content);
}
