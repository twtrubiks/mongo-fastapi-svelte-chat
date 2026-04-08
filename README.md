# 多人即時聊天室應用

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green.svg)](https://fastapi.tiangolo.com/)
[![PyMongo](https://img.shields.io/badge/PyMongo-4.16-green.svg)](https://pymongo.readthedocs.io/)
[![SvelteKit](https://img.shields.io/badge/SvelteKit-2.56-orange.svg)](https://svelte.dev/)
[![Svelte](https://img.shields.io/badge/Svelte-5-red.svg)](https://svelte.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-blue.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-blue.svg)](https://tailwindcss.com/)
[![DaisyUI](https://img.shields.io/badge/DaisyUI-5-purple.svg)](https://daisyui.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-8.0-green.svg)](https://www.mongodb.com/)
[![Redis](https://img.shields.io/badge/Redis-8-red.svg)](https://redis.io/)
[![WebSocket](https://img.shields.io/badge/WebSocket-Real--time-orange.svg)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)

一個基於 **FastAPI + MongoDB + SvelteKit 2 (Svelte 5)** 的現代化即時聊天室應用程式，

採用三層架構設計和 BFF 模式，具備完整的前後端實現。

本專案使用 Claude Code 完成 + Codex Review, 不少部份屬於 MVP 階段.

## 特色功能

- **即時通訊**: WebSocket 實現低延遲雙向通訊，自動重連機制
- **多房間支援**: 獨立的聊天室管理，房間權限控制，房間搜尋
- **完整用戶系統**: JWT 認證（HttpOnly cookie + BFF 透明 refresh）、個人資料管理、頭像上傳
- **豐富檔案支援**: 圖片、文件上傳，自動縮圖生成，多媒體預覽
- **通知系統**: 瀏覽器通知、音效提醒、已讀狀態同步
- **現代化界面**: Tailwind CSS 4 + DaisyUI 5

## 📸 畫面截圖

### 聊天室主畫面

*聊天界面*

![img](https://cdn.imgpile.com/f/qG4es09_xl.png)

*聊天室種類以及是否設定密碼*

![img](https://cdn.imgpile.com/f/wm6SP0C_xl.png)

*邀請碼房間*

![img](https://cdn.imgpile.com/f/2KLzlT5_xl.png)

*自動產生邀請碼token*

![img](https://cdn.imgpile.com/f/8nmbmw1_xl.png)

*小鈴鐺通知訊息*

![img](https://cdn.imgpile.com/f/edjjY6r_xl.png)

*自動轉跳到對應聊天室*

![img](https://cdn.imgpile.com/f/dDg8rja_xl.png)

*瀏覽器通知*

![img](https://cdn.imgpile.com/f/aLqiunO_xl.png)

*可上傳圖片或影片支援線上播放*

![img](https://cdn.imgpile.com/f/bPoL7Eu_xl.png)

*可在聊天室搜尋訊息*

![img](https://cdn.imgpile.com/f/rcmXyCk_xl.png)

*訊息通知聲音以及瀏覽器推播*

![img](https://cdn.imgpile.com/f/oVM0brR_xl.png)

*簡易儀表板*

![img](https://cdn.imgpile.com/f/fIRQc16_xl.png)

*手機板UI*

![img](https://cdn.imgpile.com/f/uiAp5oP_xl.png)

![img](https://cdn.imgpile.com/f/VpuUKZa_xl.png)

## 🏗️ 技術架構

### 後端架構 (FastAPI + MongoDB)

#### 三層架構設計

```markdown
┌─────────────────────────────────────────────────┐
│              Presentation Layer                 │
│                 (路由層)                         │
│         FastAPI Routers & WebSocket             │
├─────────────────────────────────────────────────┤
│               Business Layer                    │
│                (服務層)                          │
│          Business Logic & Rules                 │
├─────────────────────────────────────────────────┤
│                Data Layer                       │
│                (資料存取層)
│         Repository Pattern & MongoDB            │
└─────────────────────────────────────────────────┘
```

> 📖 詳細架構說明請參閱 [technical-reference.md](docs/technical-reference.md#🏗️-後端三層架構設計)

**核心技術**：

- **框架**: FastAPI
- **資料庫**: MongoDB (PyMongo 異步)
- **快取**: Redis
- **認證**: JWT Token 系統
- **架構模式**: 三層架構 + 依賴注入 (FastAPI Depends)
- **檔案處理**: 支援多種格式，自動圖片處理和縮圖

**三層架構優勢**：

- 關注點分離：每層職責明確，修改互不影響
- 高可測試性：易於單元測試和 Mock
- 程式碼重用：業務邏輯集中管理
- 靈活擴展：分層設計便於替換各層實現
- 團隊協作：統一結構降低學習成本

### 前端架構 SvelteKit 2 (Svelte 5)

#### BFF (Backend-for-Frontend) 架構

```markdown
┌─────────────────────┐
│   瀏覽器/客戶端       │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  SvelteKit BFF 層     ← 前端服務器
│  (/src/routes/api)  │
└──────────┬──────────┘
           │
┌──────────▼──────────
│   FastAPI 後端      │  ← 後端服務器
│   (真實 API)        │
└─────────────────────
```

> 📖 詳細 BFF 架構說明請參閱 [technical-reference.md](docs/technical-reference.md#🌐-前端-bff-架構設計)

**核心技術**：

- **框架**: SvelteKit 2 (Svelte 5) + TypeScript
- **樣式**: Tailwind CSS 4 + DaisyUI 5
- **建構工具**: Vite 8
- **狀態管理**: Svelte 5 Runes 響應式系統
- **API 架構**: BFF 模式
- **即時通訊**: WebSocket 客戶端，心跳檢測，狀態管理

**BFF 架構優勢**：

- API 聚合：Dashboard 等端點合併多個後端請求
- 數據轉換：為前端提供友好的數據格式
- 認證管理：HttpOnly cookie + bffAuthRequest 透明 refresh，前端零 token 存取
- 錯誤處理：統一的錯誤格式和用戶友好訊息

## 🚀 快速開始

### 環境需求

- Python 3.13+
- Node.js 24+
- MongoDB
- Redis

### 1. 啟動基礎服務 (MongoDB + Redis + mongo-express)

```bash
docker-compose up -d
```

mongo-express 是查看 MongoDB GUI 的工具,

可直接訪問 [http://localhost:8081/](http://localhost:8081/)

### 2. 啟動後端

```bash
# 切換到後端目錄
cd backend

# 複製環境變數範例（JWT_SECRET 為必填，未設定會啟動失敗）
cp .env.example .env

# 建立你自己的環境 python3.13

# 安裝相關套件
pip install -r requirements.txt

# 使用指定的 Python 環境
fastapi dev app/main.py
```

API 文檔 [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. 啟動前端

```bash
# 切換到後端目錄
cd frontend

# 安裝相關套件
npm install

# 執行
npm run dev
```

前端將運行在 [http://localhost:5173](http://localhost:5173)

#### 前端環境設定

這邊可不做, 用預設的也可以

複製環境變數範例並設定後端 WebSocket 地址：

```bash
cd frontend
cp .env.example .env
```

#### 前端可用腳本

- `npm run dev` - 啟動開發伺服器
- `npm run build` - 建構生產版本
- `npm run check` - TypeScript + Svelte 型別檢查
- `npm run lint` - ESLint 檢查
- `npm run check:all` - 型別檢查 + ESLint + 命名衝突檢查

## 📁 專案結構

```cmd
├── backend/                    # FastAPI 後端
│   ├── app/
│   │   ├── auth/              # JWT 認證系統
│   │   ├── core/              # 依賴注入工廠函數 (FastAPI Depends)
│   │   ├── database/          # MongoDB 連線管理
│   │   ├── middleware/        # 中間件 (錯誤處理、安全)
│   │   ├── models/            # Pydantic 資料模型
│   │   ├── repositories/      # 資料存取層
│   │   ├── routers/           # API 路由端點 (路由層)
│   │   ├── services/          # 業務邏輯層 (服務層)
│   │   ├── utils/             # 工具函數
│   │   ├── websocket/         # WebSocket 管理
│   │   ├── config.py          # 應用程式設定
│   │   ├── security_config.py # 安全設定
│   │   └── main.py            # FastAPI 進入點
│   └── tests/                 # pytest 測試
├── frontend/                   # SvelteKit 前端
│   ├── src/
│   │   ├── lib/               # 核心功能庫
│   │   │   ├── api/           # API 客戶端
│   │   │   ├── components/    # UI 組件
│   │   │   ├── stores/        # Svelte 狀態管理
│   │   │   ├── websocket/     # WebSocket 客戶端
│   │   │   ├── styles/        # Tailwind CSS 設定
│   │   │   ├── utils/         # 前端工具
│   │   │   ├── bff-api-client.ts  # BFF API 客戶端
│   │   │   ├── bff-auth.ts        # BFF 認證邏輯
│   │   │   ├── bff-client.ts      # BFF 基礎客戶端
│   │   │   ├── bff-cookie.ts      # BFF Cookie 處理
│   │   │   ├── bff-types.ts       # BFF 型別定義
│   │   │   ├── bff-utils.ts       # BFF 工具函數
│   │   │   └── types.ts           # 共用型別定義
│   │   └── routes/            # SvelteKit 路由
│   │       ├── app/           # 應用頁面
│   │       ├── (auth)/        # 認證頁面
│   │       └── api/           # BFF API 路由
└── docs/                       # 專案文檔
    ├── c4-architecture.md      # C4 架構文檔
    └── technical-reference.md  # 技術參考
```

## 手機測試

確保手機和電腦在同一 WiFi 網路，後端加 `--host 0.0.0.0`，前端已預設監聽所有介面。

```bash
# 後端
fastapi dev app/main.py --host 0.0.0.0

# 前端（直接 npm run dev 即可）
npm run dev
```

手機瀏覽器輸入 `http://{電腦區網IP}:5173`（例如 `http://192.168.1.100:5173`）。

## 🧪 測試

### 後端測試

測試依賴 MongoDB 和 Redis，執行前請先啟動 Docker 容器：

```bash
docker-compose up -d
```

```bash
# 切換到後端目錄
cd backend

# 安裝相關套件
pip install -r requirements-test.txt

pytest tests/ -v --cov=app --cov-report=html
```

- **測試覆蓋**: 涵蓋 API、認證、服務、WebSocket 等
- **測試類型**: 單元測試、整合測試、併發測試

## 📚 核心文檔

- 🛠️ **[技術參考](docs/technical-reference.md)** - 三層架構、BFF 架構、MongoDB 優化、SvelteKit、時區處理
- 📐 **[C4 架構文檔](docs/c4-architecture.md)** - 系統架構的完整 C4 模型視圖（Context、Container、Component、Code）

### 文檔重點內容

- **[後端三層架構設計](docs/technical-reference.md#後端三層架構設計)** - 路由層、服務層、資料層的職責和實現
- **[前端 BFF 架構設計](docs/technical-reference.md#前端-bff-架構設計)** - API 聚合、數據轉換、認證管理
- **[MongoDB 優化策略](docs/technical-reference.md#mongodb-優化策略)** - 反規範化設計減少查詢次數
- **[MongoDB 索引策略](docs/technical-reference.md#mongodb-索引策略)** - 啟動時自動建立索引，unique 約束 + 複合索引
- **[C4 系統架構](docs/c4-architecture.md)** - 完整的系統架構視圖（Context、Container、Component、Code）、WebSocket 即時通訊設計、依賴注入設計

## 🔧 API 端點

完整 API 文檔請參閱 Swagger UI：啟動後端後訪問 [http://localhost:8000/docs](http://localhost:8000/docs)

主要模組：

| 模組 | 前綴 | 說明 |
|------|------|------|
| 認證 | `/api/auth` | 註冊、登入、Token 刷新、個人資料、頭像 |
| 聊天室 | `/api/rooms` | CRUD、加入/離開、成員管理、搜尋 |
| 訊息 | `/api/messages` | 發送、歷史記錄、搜尋 |
| 檔案 | `/api/files` | 上傳、縮圖、多媒體存取 |
| 通知 | `/api/notifications` | 通知列表、已讀、統計、清除全部 |
| 邀請 | `/api/invitations` | 邀請碼、加入申請、審核 |
| WS Ticket | `/api/ws` | 一次性 WebSocket 連線 ticket（Redis TTL 30s） |
| WebSocket | `WS /ws/{room_id}` | 房間即時通訊（ticket 認證） |

## 🏆 架構亮點

### 後端架構特色

1. **三層架構設計**: 清晰的職責分離，高可維護性和可測試性
2. **依賴注入系統**: FastAPI 原生 Depends，工廠函數模式
3. **MongoDB 效能優化**: 反規範化設計 + 啟動時自動建立索引（unique 約束 + 複合索引）
4. **完整中間件系統**: 錯誤處理、速率限制、安全標頭保護
5. **WebSocket 管理**: 連線 debounce、心跳檢測、房間隔離機制、一次性 ticket 認證

### 前端架構特色

1. **BFF 架構模式**: 前端友善的 API 聚合層，減少請求次數
2. **現代化前端**: Svelte 5 Runes、TypeScript、響應式設計
3. **數據處理**: 統一錯誤處理、BFF 數據轉換與聚合
4. **安全認證**: HttpOnly cookie 全鏈路，前端不持有 token，WebSocket 一次性 ticket 認證
5. **即時通訊**: WebSocket 自動重連、狀態同步、連線狀態管理

### 效能優化亮點

- **MongoDB 反規範化**: 內嵌常用欄位避免 N+1 查詢，例如取 50 條訊息只需 1 次查詢而非 51 次
- **BFF API 聚合**: 減少前後端通訊次數，提升頁面載入速度
- **Redis 快取**: 使用者資料快取（fail-open），減少資料庫負擔
- **異步處理**: FastAPI + PyMongo 異步驅動，非阻塞 I/O

## 📄 授權

MIT License - 開源且免費使用

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

---

⭐ **如果這個專案對您有幫助，請給一個 Star！** ⭐
