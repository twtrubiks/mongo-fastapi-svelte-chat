import { browser } from '$app/environment';
import { apiClient } from '../api/client';
import type { AIStatus } from '../types';

/**
 * AI 助理可用狀態（全域設定，登入後查一次）
 *
 * 「上線」語意 = 後端當前供應商已配置 API key（非 WebSocket 連線）。
 * bot 永不連 WebSocket，故不沿用 global_online_users 機制。
 * 失敗時 fail-open 維持「不可用」，不阻斷聊天室功能。
 */
let aiState = $state<{ enabled: boolean; botUsername: string; loaded: boolean }>({
  enabled: false,
  botUsername: 'AI 助理',
  loaded: false,
});

// 載入一次（去重）；非瀏覽器或已載入則略過
export async function loadAIStatus(): Promise<void> {
  if (!browser || aiState.loaded) return;
  aiState.loaded = true; // 樂觀標記，避免多個元件實例並發重複請求
  try {
    const status: AIStatus = await apiClient.ai.getStatus();
    aiState.enabled = status.enabled;
    aiState.botUsername = status.bot_username;
  } catch {
    // fail-open：取不到狀態時維持「不可用」
    aiState.enabled = false;
  }
}

export const aiStatus = () => aiState;
