import type { User } from '$lib/types';

/**
 * 用戶 ID 標準化工具
 * 處理不同格式的用戶 ID 字段
 */

/**
 * 從用戶對象中提取標準化的用戶 ID
 * @param user 用戶對象
 * @returns 標準化的用戶 ID，如果找不到則返回 null
 */
export function extractUserId(user: User | any): string | null {
  if (!user || typeof user !== 'object') {
    return null;
  }

  // 嘗試不同的 ID 字段格式
  const possibleIdFields = ['id', '_id', 'user_id', 'userId'];
  
  for (const field of possibleIdFields) {
    const id = user[field];
    if (id && typeof id === 'string') {
      return id;
    }
  }

  return null;
}

/**
 * 標準化用戶對象，確保有 id 字段
 * @param user 原始用戶對象
 * @returns 標準化的用戶對象
 */
export function normalizeUser(user: User | any): User {
  if (!user || typeof user !== 'object') {
    throw new Error('Invalid user object');
  }

  const userId = extractUserId(user);
  
  if (!userId) {
    console.warn('User object missing valid ID field:', user);
    // 生成一個臨時 ID
    const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    return {
      ...user,
      id: tempId,
    };
  }

  return {
    ...user,
    id: userId,
  };
}

/**
 * 標準化用戶列表
 * @param users 用戶列表
 * @returns 標準化的用戶列表
 */
export function normalizeUserList(users: (User | any)[]): User[] {
  if (!Array.isArray(users)) {
    console.warn('Expected array of users, got:', typeof users);
    return [];
  }

  return users.map(user => {
    try {
      return normalizeUser(user);
    } catch (error) {
      console.error('Failed to normalize user:', error, user);
      return null;
    }
  }).filter(Boolean) as User[];
}

/**
 * 在用戶列表中查找用戶
 * @param users 用戶列表
 * @param targetUser 目標用戶或用戶ID
 * @returns 找到的用戶索引，找不到返回 -1
 */
function findUserIndex(users: User[], targetUser: User | string): number {
  const targetId = typeof targetUser === 'string' 
    ? targetUser 
    : extractUserId(targetUser);
    
  if (!targetId) {
    return -1;
  }
  
  return users.findIndex(user => extractUserId(user) === targetId);
}

/**
 * 向用戶列表中添加用戶（避免重複）
 * @param users 現有用戶列表
 * @param newUser 要添加的新用戶
 * @returns 添加用戶後的新列表
 */
export function addUserToList(users: User[], newUser: User): User[] {
  const normalizedUser = normalizeUser(newUser);
  const existingIndex = findUserIndex(users, normalizedUser);
  
  if (existingIndex >= 0) {
    // 用戶已存在，更新用戶信息
    const updatedUsers = [...users];
    updatedUsers[existingIndex] = normalizedUser;
    return updatedUsers;
  }
  
  // 用戶不存在，添加到列表
  return [...users, normalizedUser];
}