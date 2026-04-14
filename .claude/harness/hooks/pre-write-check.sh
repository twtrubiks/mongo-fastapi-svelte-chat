#!/usr/bin/env bash
# PreToolUse hook — 寫入/編輯前的安全檢查
# Claude Code 會透過 stdin 傳入 tool_input JSON
# 輸出至 stderr 的文字會顯示給使用者
# exit 2 = 攔截（block），exit 0 = 放行

set -euo pipefail

# 從 stdin 讀取 tool input JSON
INPUT=$(cat)

# 提取 file_path（簡易 grep，不依賴 jq）
FILE_PATH=$(echo "$INPUT" | grep -oP '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')

if [ -z "$FILE_PATH" ]; then
  # 無法解析 file_path，放行
  exit 0
fi

# --- 規則 1：禁止寫入 .env 檔案 ---
if echo "$FILE_PATH" | grep -qE '\.env$|\.env\.' ; then
  echo "BLOCKED: 禁止直接寫入 .env 檔案 ($FILE_PATH)" >&2
  exit 2
fi

# --- 規則 2：禁止寫入 node_modules ---
if echo "$FILE_PATH" | grep -q 'node_modules' ; then
  echo "BLOCKED: 禁止寫入 node_modules ($FILE_PATH)" >&2
  exit 2
fi

# --- 規則 3：禁止寫入 .git 目錄 ---
if echo "$FILE_PATH" | grep -q '\.git/' ; then
  echo "BLOCKED: 禁止寫入 .git 目錄 ($FILE_PATH)" >&2
  exit 2
fi

# --- 規則 4：掃描疑似硬編碼 secrets ---
# 提取 content 或 new_string 欄位來檢查
CONTENT=$(echo "$INPUT" | grep -oP '"(?:content|new_string)"\s*:\s*"[^"]*"' | head -1 || true)

if [ -n "$CONTENT" ]; then
  # AWS Access Key
  if echo "$CONTENT" | grep -qE 'AKIA[A-Z0-9]{16}' ; then
    echo "BLOCKED: 偵測到疑似 AWS Access Key" >&2
    exit 2
  fi
  # OpenAI / Anthropic API Key
  if echo "$CONTENT" | grep -qE 'sk-[a-zA-Z0-9]{20,}' ; then
    echo "BLOCKED: 偵測到疑似 API Key (sk-...)" >&2
    exit 2
  fi
  # 明文密碼賦值
  if echo "$CONTENT" | grep -qiE 'password\s*=\s*"[^"]{8,}"' ; then
    echo "BLOCKED: 偵測到疑似硬編碼密碼" >&2
    exit 2
  fi
fi

# 所有檢查通過，放行
exit 0
