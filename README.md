# 多人即時聊天室應用

一個基於 **FastAPI + MongoDB + SvelteKit 2.22 (Svelte 5)** 的現代化即時聊天室應用程式，採用三層架構設計和 BFF 模式，具備完整的前後端實現。

本專案使用 AI 完成, 不少部份屬於 MVP 階段, 但我盡力作到最好.

## 特色功能

- **即時通訊**: WebSocket 實現低延遲雙向通訊，自動重連機制
- **多房間支援**: 獨立的聊天室管理，房間權限控制
- **完整用戶系統**: JWT 認證、個人資料管理、頭像上傳
- **豐富檔案支援**: 圖片、文件上傳，自動縮圖生成，多媒體預覽
- **智能通知系統**: 瀏覽器通知、音效提醒、已讀狀態同步
- **現代化界面**: Tailwind CSS + DaisyUI

## 📸 畫面截圖

### 聊天室主畫面

*登入畫面*

![img](https://cdn.imgpile.com/f/7JBjUi0_xl.png)

*聊天界面*

![img](https://cdn.imgpile.com/f/9PlwtZM_xl.png)

*聊天室種類以及是否設定密碼*

![img](https://cdn.imgpile.com/f/wm6SP0C_xl.png)

*邀請碼房間*

![img](https://cdn.imgpile.com/f/2KLzlT5_xl.png)

*自動產生邀請碼token*

![img](https://cdn.imgpile.com/f/8nmbmw1_xl.png)

*小鈴鐺通知訊息*

![img](https://cdn.imgpile.com/f/8rAozbm_xl.png)

*自動轉跳到對應聊天室*

![img](https://cdn.imgpile.com/f/dDg8rja_xl.png)

*可上傳圖片或影片支援線上播放*

![img](https://cdn.imgpile.com/f/bPoL7Eu_xl.png)

*可在聊天室搜尋訊息*

![img](https://cdn.imgpile.com/f/rcmXyCk_xl.png)

*訊息通知聲音以及瀏覽器推播*

![img](https://cdn.imgpile.com/f/oVM0brR_xl.png)

*簡易儀表板*

![img](https://cdn.imgpile.com/f/fIRQc16_xl.png)

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
- **架構模式**: 三層架構 + 依賴注入 (Singleton/Scoped/Transient)
- **檔案處理**: 支援多種格式，自動圖片處理和縮圖

**三層架構優勢**：

- 關注點分離：每層職責明確，修改互不影響
- 高可測試性：易於單元測試和 Mock
- 程式碼重用：業務邏輯集中管理
- 靈活擴展：支援多種客戶端和技術替換
- 團隊協作：統一結構降低學習成本

### 前端架構 SvelteKit 2.22 (Svelte 5)

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

- **框架**: SvelteKit 2.22 (Svelte 5) + TypeScript
- **樣式**: Tailwind CSS + DaisyUI
- **狀態管理**: Svelte 5 Runes 響應式系統
- **API 架構**: BFF 模式
- **即時通訊**: WebSocket 客戶端，心跳檢測，狀態管理

**BFF 架構優勢**：

- API 聚合：減少請求次數，提升性能
- 數據轉換：為前端提供友好的數據格式
- 認證管理：集中處理 JWT Token
- 錯誤處理：統一的錯誤格式和用戶友好訊息
- 快取策略：智能快取提升響應速度

## 🚀 快速開始

### 環境需求

- Python 3.13+
- Node.js
- MongoDB
- Redis

### 1. 啟動基礎服務 (MongoDB + Redis + mongo-express)

```bash
docker-compose up -d
```

mongo-express 是查看 MongoDB GUI 的工具,

可直接訪問 [http://0.0.0.0:8081/](http://0.0.0.0:8081/)

### 2. 啟動後端

```bash
# 安裝相關套件
pip install -r requirements.txt

# 切換到後端目錄
cd backend

# 使用指定的 Python 環境
fastapi dev main.py
```

API 文檔 [http://0.0.0.0:8000/docs](http://0.0.0.0:8000/docs)

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

複製環境變數範例並設定後端 API 地址：

```bash
cd frontend
cp .env.example .env
```

#### 前端可用腳本

- `npm run dev` - 啟動開發伺服器
- `npm run build` - 建構生產版本
- `npm run check` - 檢查 TypeScript 和 Svelte 程式碼

## 📁 專案結構

```cmd
├── backend/                    # FastAPI 後端
│   ├── app/
│   │   ├── auth/              # JWT 認證系統
│   │   ├── cache/             # Redis 快取管理
│   │   ├── core/              # 依賴注入容器
│   │   ├── database/          # MongoDB 連線管理
│   │   ├── middleware/        # 中間件 (錯誤處理、安全)
│   │   ├── models/            # Pydantic 資料模型
│   │   ├── repositories/      # 資料存取層
│   │   ├── routers/           # API 路由端點 (路由層)
│   │   ├── services/          # 業務邏輯層 (服務層)
│   │   ├── utils/             # 工具函數
│   │   └── websocket/         # WebSocket 管理
│   └── tests/                 # 70+ 測試檔案
├── frontend/                   # SvelteKit 前端
│   ├── src/
│   │   ├── lib/               # 核心功能庫
│   │   │   ├── api/           # API 客戶端
│   │   │   ├── components/    # UI 組件
│   │   │   ├── stores/        # Svelte 狀態管理
│   │   │   ├── websocket/     # WebSocket 客戶端
│   │   │   └── utils/         # 前端工具
│   │   └── routes/            # SvelteKit 路由
│   │       ├── (app)/         # 應用頁面
│   │       ├── (auth)/        # 認證頁面
│   │       └── api/           # BFF API 路由
└── docs/                       # 專案文檔
    └── technical-reference.md  # 技術參考
```

## 🧪 測試

### 後端測試

```bash
# 安裝相關套件
pip install -r requirements-test.txt

# 切換到後端目錄
cd backend

pytest tests/ -v --cov=app --cov-report=html
```

- **測試覆蓋**: 70+ 測試檔案，涵蓋 API、認證、服務、WebSocket 等
- **測試類型**: 單元測試、整合測試、併發測試

## 📚 核心文檔

- 🛠️ **[技術參考](docs/technical-reference.md)** - 三層架構、BFF 架構、MongoDB 優化、SvelteKit、時區處理

### 文檔重點內容

- **[後端三層架構設計](docs/technical-reference.md#後端三層架構設計)** - 路由層、服務層、資料層的職責和實現
- **[前端 BFF 架構設計](docs/technical-reference.md#前端-bff-架構設計)** - API 聚合、數據轉換、認證管理
- **[MongoDB 優化策略](docs/technical-reference.md#mongodb-優化策略)** - 反規範化設計實現 51x 查詢效能

## 🔧 核心 API 端點

### 認證系統

- `POST /api/auth/register` - 用戶註冊
- `POST /api/auth/login` - 用戶登入
- `GET /api/auth/me` - 獲取用戶資訊

### 聊天室管理

- `GET /api/rooms/` - 獲取房間列表
- `POST /api/rooms/` - 創建房間
- `POST /api/rooms/{id}/join` - 加入房間
- `GET /api/rooms/{id}/members` - 獲取房間成員

### 訊息系統

- `GET /api/messages/room/{room_id}` - 獲取房間訊息
- `POST /api/messages/` - 發送訊息
- `POST /api/messages/room/{room_id}/search` - 搜尋訊息

### 檔案上傳

- `POST /api/files/upload` - 檔案上傳
- `POST /api/files/upload/image` - 圖片上傳
- `GET /api/files/thumbnail/{filename}` - 獲取縮圖

### WebSocket

- `WS /ws/{room_id}` - 房間即時通訊連線

## 🏆 架構亮點

### 後端架構特色

1. **三層架構設計**: 清晰的職責分離，高可維護性和可測試性
2. **依賴注入系統**: 支援 Singleton、Scoped、Transient 三種生命週期
3. **MongoDB 效能優化**: 反規範化設計，實現 51x 查詢效能提升
4. **完整中間件系統**: 錯誤處理、速率限制、安全標頭保護
5. **WebSocket 管理**: 自動重連、心跳檢測、房間隔離機制

### 前端架構特色

1. **BFF 架構模式**: 前端友善的 API 聚合層，減少請求次數
2. **現代化前端**: Svelte 5 Runes、TypeScript、響應式設計
3. **智能數據處理**: 統一錯誤處理、數據轉換、快取策略
4. **即時通訊**: WebSocket 自動重連、狀態同步、訊息佇列

### 效能優化亮點

- **MongoDB 反規範化**: 從 51 次查詢優化到 1 次，回應時間從 200-500ms 降至 10-20ms
- **BFF API 聚合**: 減少前後端通訊次數，提升頁面載入速度
- **智能快取策略**: 多層快取機制，減少資料庫負擔
- **並行處理**: 充分利用異步特性，提升系統吞吐量

## 📄 授權

MIT License - 開源且免費使用

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

---

⭐ **如果這個專案對您有幫助，請給一個 Star！** ⭐
