# CLAUDE.md

## Project Overview

MongoDB + FastAPI + SvelteKit 全端即時聊天應用程式。支援即時通訊（WebSocket）、多聊天室、檔案分享、通知系統。

## Tech Stack

- **Backend:** Python 3.13+, FastAPI, PyMongo (async), Redis, JWT auth, bcrypt, Pydantic v2
- **Frontend:** SvelteKit 2, Svelte 5 (Runes), TypeScript 6 (strict), Tailwind CSS 4 + DaisyUI 5, Vite 8
- **Database:** MongoDB 8.0, Redis 8
- **Infra:** Docker Compose (mongodb:27017, redis:6379, mongo-express:8081)

## Architecture

- **Backend:** 三層架構 — Routers (Presentation) → Services (Business) → Repositories (Data)
- **Frontend:** BFF 模式 — Browser → SvelteKit API routes (`/src/routes/api/`) → FastAPI backend
- **DI:** FastAPI Depends 工廠函數 (`app/core/fastapi_integration.py`)

架構規範與實作細節：
@.claude/harness/worker-prompt.md
審查標準：
@.claude/harness/reviewer-prompt.md

## Common Commands

```bash
# Infrastructure
docker-compose up -d                          # Start MongoDB + Redis + mongo-express

# Backend (from /backend)
pyenv activate fastapi-chat                   # Activate pyenv virtualenv
fastapi dev app/main.py                       # Dev server on :8000
pytest tests/ -v --cov=app --cov-report=html  # Run tests
ruff check . && ruff format .                 # Lint + Format

# Frontend (from /frontend)
npm run dev                                   # Dev server on :5173
npm run check:all                             # Type check + lint + naming check
```

## Conventions

- Backend 使用繁體中文註解
- MongoDB 使用反正規化（denormalization）優化查詢效能；索引在啟動時自動建立（`app/database/indexes.py`）
- Redis 用途：Rate Limiting（滑動視窗）+ 使用者資料快取（TTL 5 分鐘，fail-open）
- Frontend stores 使用 Svelte 5 Runes（`.svelte.ts` 檔案），不使用 writable/readable
- Tailwind CSS 4 設定集中於 `src/lib/styles/tailwind.css`；Svelte 元件中 `@apply` 需搭配 `@reference "$lib/styles/tailwind.css"`
- Pre-commit hooks 自動執行 ruff lint + format（限 `backend/`）
- 遇到 Svelte 5 / SvelteKit 2 / Tailwind CSS 4 / DaisyUI 5 / Pydantic v2 等版本敏感的 API 用法不確定時，優先使用 Context7 MCP 查詢當前版本的官方文件，不要憑記憶猜測
