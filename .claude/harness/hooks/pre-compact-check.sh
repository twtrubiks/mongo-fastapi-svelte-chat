#!/usr/bin/env bash
# PreCompact hook — context 壓縮前檢查是否有進行中的任務
set -euo pipefail

PLANS="Plans.md"

if [ ! -f "$PLANS" ]; then
  exit 0
fi

WIP_TASKS=$(grep -n 'cc:DOING' "$PLANS" || true)

if [ -n "$WIP_TASKS" ]; then
  echo "⚠️ Context 即將壓縮，以下任務仍在進行中（cc:DOING）："
  echo "$WIP_TASKS"
  echo "壓縮後可能遺失這些任務的工作上下文，建議先完成或記錄當前進度。"
fi

exit 0
