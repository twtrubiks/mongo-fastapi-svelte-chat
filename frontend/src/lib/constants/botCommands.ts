/**
 * AI 助理（@bot / 斜線指令）的可用清單 —— 單一事實來源。
 *
 * 同時供兩處使用，避免兩邊各寫一份導致新增指令時不同步：
 *  - MessageInput：輸入框開頭打 "@" 或 "/" 時的自動完成提示
 *  - UserList：點擊右側「AI 助理」彈出的用法小卡
 *
 * 對應後端 app/core/bot.py 的觸發判斷；新增指令時同步維護此清單。
 */
export interface BotCommand {
  insert: string; // 選定後填入輸入框的文字
  label: string; // 顯示主文字
  description: string; // 顯示說明
}

// "@" 觸發：提及 AI 助理（insert 帶尾空白，游標停在後面接著打問題）
export const MENTION_SUGGESTIONS: BotCommand[] = [
  { insert: '@bot ', label: '@bot', description: '向 AI 助理提問' },
];

// "/" 觸發：斜線指令（/summary 為完整指令，選定後可直接送出）
export const COMMAND_SUGGESTIONS: BotCommand[] = [
  { insert: '/summary', label: '/summary', description: '摘要近期對話' },
];

// 用法小卡：把提及與指令合併呈現，讓使用者一次看到所有用法
export const BOT_COMMANDS: BotCommand[] = [...MENTION_SUGGESTIONS, ...COMMAND_SUGGESTIONS];
