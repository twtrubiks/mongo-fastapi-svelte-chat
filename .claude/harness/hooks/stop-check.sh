#!/usr/bin/env bash
# Stop hook — session 結束前檢查是否有進行中的任務
set -euo pipefail

PLANS="Plans.md"

if [ ! -f "$PLANS" ]; then
  exit 0
fi

WIP_TASKS=$(grep -n 'cc:DOING' "$PLANS" || true)

if [ -n "$WIP_TASKS" ]; then
  echo "⚠️ Session 即將結束，以下任務仍在進行中（cc:DOING）："
  echo "$WIP_TASKS"
  echo "建議先完成任務或將狀態改回 cc:TODO 再結束。"
fi

exit 0
