# 技術參考指南

## 後端三層架構設計

### 架構概覽

本專案採用經典的三層架構設計，將業務邏輯清晰分離，提高程式碼的可維護性和可測試性：

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
│              (資料存取層)                         │
│         Repository Pattern & MongoDB            │
└─────────────────────────────────────────────────┘
```

### 各層職責與實現

#### 1. 路由層 (Presentation Layer)

**位置**: `/backend/app/routers/`

```python
# 路由層範例：處理 HTTP 請求，調用服務層
# router = APIRouter(prefix="/rooms", tags=["聊天室"])

# 列表端點 → 回傳 RoomSummary（不含 members/invite_code）
@router.get("/", response_model=list[RoomSummary])
async def get_rooms(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    user_id = current_user["_id"]
    return await room_service.get_rooms(
        skip=skip, limit=limit, search=search, user_id=user_id
    )

# 成員專屬端點 → require_room_membership 檢查成員資格
@router.get("/{room_id}/members")
async def get_room_members(
    room_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _current_user: dict = Depends(require_room_membership),
    room_service: RoomService = RoomServiceDep,
):
    return await room_service.get_room_members(room_id, skip=skip, limit=limit)
```

**職責**：

- 處理 HTTP 請求和響應
- 參數驗證（透過 Pydantic）
- 身份認證和授權
- 調用服務層處理業務邏輯
- 統一錯誤處理和響應格式

#### 2. 服務層 (Business Layer)

**位置**: `/backend/app/services/`

```python
# 服務層範例：實現業務邏輯
class RoomService:
    def __init__(
        self,
        room_repository: RoomRepository,
        user_repository: UserRepository,
        message_repository: MessageRepository,
        connection_manager=None,  # WebSocket 透過 DI 注入，非硬依賴
    ):
        self.room_repo = room_repository
        self.user_repo = user_repository
        self.message_repo = message_repository
        self._connection_manager = connection_manager

    async def create_room(self, owner_id: str, room_data: RoomCreate) -> RoomResponse:
        """服務層負責：
        1. 業務規則驗證（唯一性檢查、權限等）— 失敗拋出 AppError 子類別
        2. 加密處理（透過 auth.password 模組）
        3. 協調多個資料源
        """
        # 驗證用戶是否存在
        user = await self.user_repo.get_by_id(owner_id)
        if not user:
            raise NotFoundError("用戶不存在")

        # 密碼雜湊（透過共用工具，非直接 bcrypt）
        password_hash = None
        if room_data.password:
            password_hash = await get_password_hash(room_data.password)

        # 建構 RoomInDB 文件（含 owner_name、members、密碼雜湊等）
        room_doc = RoomInDB(name=room_data.name, owner_id=owner_id, ...)

        # 名稱唯一性檢查（商業邏輯，由 Service 層負責）
        existing = await self.room_repo.get_by_name(room_data.name)
        if existing:
            raise ConflictError(f"房間名稱已存在: {room_data.name}")

        # 創建房間（Repository 只負責純資料寫入）
        created_room = await self.room_repo.create(room_doc)

        # 轉換為回應模型 + 廣播房間建立事件
        room_response = await self._convert_to_response(created_room, owner_id)
        return room_response
```

**職責**：

- 實現核心業務邏輯（驗證、唯一性檢查、加密）
- 協調多個資料存取層
- 業務異常一律拋出 `AppError` 子類別（`NotFoundError`、`ForbiddenError`、`ConflictError`、`UnauthorizedError`），由 `exception_handler` 統一轉換為 HTTP 回應
- 不直接依賴 WebSocket — 透過建構子注入 `connection_manager`

#### 3. 資料存取層 (Data Layer)

**位置**: `/backend/app/repositories/`

```python
# 資料存取層範例：處理資料持久化（繼承 BaseRepository）
class RoomRepository(BaseRepository[RoomInDB]):
    def __init__(self, database: AsyncDatabase):
        """透過 BaseRepository 初始化，指定集合名稱"""
        super().__init__(database, "rooms")

    def _to_model(self, document: dict) -> RoomInDB:
        """將 MongoDB document 轉為 Pydantic model（BaseRepository 模板方法）"""
        return RoomInDB(**document)

# BaseRepository 提供通用 CRUD（子類透過 _to_model 注入型別轉換）
class BaseRepository(Generic[T]):
    async def get_by_id(self, id: str) -> T | None:
        """資料層只負責：
        1. 資料庫 CRUD 操作
        2. 資料映射
        3. 查詢優化
        """
        document = await self.find_by_id(id)
        if document:
            return self._to_model(document)
        return None
```

**職責**：

- 資料庫 CRUD 操作（純資料寫入/讀取）
- 資料模型映射（MongoDB document ↔ Pydantic model）
- 查詢優化

**不應包含**：商業邏輯驗證（唯一性檢查、容量限制、權限判斷）、加密處理 — 這些屬於 Service 層

#### 錯誤處理策略

資料存取層（Repository）**不攔截資料庫例外**。所有來自 PyMongo 的異常（`PyMongoError`、`DuplicateKeyError`、`BulkWriteError` 等）直接向上傳播，由 `GlobalErrorHandler` 中間件統一處理並轉換為標準化 HTTP 回應。

Repository 方法的回傳值語義：

- `None` / `False` / `[]` / `0`：表示「查無資料」或「未匹配到文檔」，屬正常業務結果
- 拋出例外：表示資料庫操作失敗（連線中斷、寫入衝突等），由中間件對應至 HTTP 狀態碼

唯一保留的防護邏輯：

- `find_by_id` 中的 `ObjectId.is_valid()` 檢查：屬於輸入驗證，非錯誤處理
- `get_by_ids` 中的逐筆文檔驗證 try/except：跳過格式不符的個別文檔，不影響批次查詢

#### 錯誤處理雙機制

系統採用兩層錯誤處理，分別處理業務異常與基礎設施異常：

| 機制 | 處理對象 | 實現方式 | 回應格式 |
|------|---------|---------|---------|
| `app_error_handler` | `AppError` 子類別（業務異常） | FastAPI `@app.exception_handler(AppError)` | `{"detail": "..."}` + 對應 status code |
| `GlobalErrorHandler` | 未預期的基礎設施異常 | ASGI Middleware | 統一 500 錯誤 |

**AppError 異常層級**（`app/core/exceptions.py`）：

| 異常類別 | HTTP Status | 使用場景 |
|---------|------------|---------|
| `NotFoundError` | 404 | 查無資源（房間、用戶、通知等不存在） |
| `UnauthorizedError` | 401 | 認證失敗（密碼錯誤、token 無效），附帶 `WWW-Authenticate` header |
| `ForbiddenError` | 403 | 權限不足（非擁有者操作、非成員存取） |
| `ConflictError` | 409 | 資源衝突（房間名稱重複、已加入房間） |

**Router 層不做 try/except catch-all**，業務異常由 Service 層拋出，統一交由 `exception_handler` 處理。

### 依賴注入系統

使用 FastAPI 原生 `Depends` 搭配工廠函數管理各層之間的依賴關係（位於 `app/core/fastapi_integration.py`）：

```python
# Service 工廠函數
# HTTP Router：透過 Depends() 注入（見下方 *Dep 別名）
# WebSocket handler：直接 await 呼叫（如 svc = await create_message_service()）
#   因為 FastAPI 的 Depends() 僅支援 HTTP path operation，
#   WebSocket endpoint 無法使用相同的 DI 機制，故以工廠函數統一建立邏輯。

async def create_room_service() -> RoomService:
    from app.websocket.manager import connection_manager  # DI 工廠負責接線
    db = await get_database()
    return RoomService(
        RoomRepository(db), UserRepository(db), MessageRepository(db),
        connection_manager=connection_manager,
    )

async def create_notification_service() -> NotificationService:
    from app.websocket.manager import connection_manager
    db = await get_database()
    return NotificationService(
        NotificationRepository(db), connection_manager=connection_manager,
    )

# FastAPI Depends 別名（Router 直接使用）
RoomServiceDep = Depends(create_room_service)

# Router 中使用
@router.get("/rooms")
async def list_rooms(room_service: RoomService = RoomServiceDep):
    ...
```

---

## MongoDB 優化策略

### 反規範化設計優勢

在聊天室應用中，我們採用 MongoDB 反規範化設計來優化查詢效能：

#### 傳統問題

```typescript
// 傳統關聯式設計 - 會導致 N+1 查詢問題
interface Message {
  id: string;
  room_id: string;
  user_id: string;
  content: string;
  user: {  // 需要額外查詢
    username: string;
    avatar?: string;
  };
}
```

#### MongoDB 優化方案

```typescript
// 平面化結構 - 直接嵌入常用資訊
interface Message {
  id: string;
  room_id: string;
  user_id: string;
  username: string;      // 直接儲存
  user_avatar?: string;  // 直接儲存
  content: string;
  created_at: string;
}
```

### 效能分析（理論推算）

以獲取 50 條訊息為例：正規化設計需 1 次查 messages + 50 次查 users = 51 次查詢；反規範化後只需 1 次查詢（username 已內嵌於 message 文件中）。

### 實施策略

#### 1. Pydantic 模型設計

```python
class MessageInDB(MessageBase):
    id: str | None = Field(None, alias="_id", description="訊息 ID")
    room_id: str = Field(..., description="房間 ID")
    user_id: str = Field(..., description="發送者 ID")
    username: str = Field(..., description="發送者用戶名")  # 冗餘儲存
    status: MessageStatus = Field(default=MessageStatus.SENT, description="訊息狀態")
    edited: bool = Field(default=False, description="是否已編輯")
    edited_at: datetime | None = Field(None, description="編輯時間")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

#### 2. 資料一致性考量

> **注意**: 目前尚未實作使用者資料變更時的反規範化同步更新。當使用者修改用戶名後，歷史訊息中的 `username` 不會自動更新。未來可透過 `update_many` 批次同步，但需考量效能影響。

---

## MongoDB 索引策略

### 自動建立機制

應用程式啟動時，透過 `app/database/indexes.py` 的 `ensure_indexes()` 自動建立索引。`create_index` 是冪等操作，索引已存在時會跳過，不會重複建立。

```python
# app/main.py lifespan
await init_database(settings.MONGODB_URL, settings.MONGODB_DATABASE)
db = await get_database()
await ensure_indexes(db)  # 啟動時自動建立索引
```

### 索引清單

| Collection | 索引欄位 | 類型 | 用途 |
|------------|---------|------|------|
| `users` | `username` | unique | 防止重複用戶名，加速登入查詢 |
| `users` | `email` | unique | 防止重複 email，加速註冊檢查 |
| `messages` | `{ room_id, created_at desc }` | 複合索引 | 進入聊天室載入訊息（最高頻查詢） |
| `messages` | `{ room_id, seq desc }` | 複合索引 | 依序號查詢訊息（斷線 gap 補發 / 游標分頁，見 ADR-003） |
| `messages` | `{ room_id, client_id }` | partial unique | 訊息冪等去重保底（僅對 client_id 為字串的文件生效） |
| `rooms` | `name` | unique | 防止重複房間名稱（TOCTOU 競態防護） |
| `rooms` | `invite_code` | partial unique | 防止重複邀請碼（僅對 invite_code 為字串的文件生效） |
| `rooms` | `members` | multikey | 查詢「我的房間」列表（陣列欄位） |
| `rooms` | `{ is_public, created_at desc }` | 複合索引 | 探索頁面公開房間查詢 + 排序 |
| `notifications` | `{ user_id, created_at desc }` | 複合索引 | 通知列表 + 未讀計數 |
| `room_invitations` | `invite_code` | unique | 防止重複邀請碼，加速邀請驗證 |

### 索引選擇原則

- **Unique 索引**：不只是效能，更是資料正確性約束（防止重複 username/email/room name）
- **Partial unique 索引**：`rooms.invite_code` 與 `messages.{room_id, client_id}` 使用 `partialFilterExpression: {欄位: {$type: "string"}}`，僅對該欄位為字串的文件生效。用 `$type: "string"` 而非 `$exists: true`——因為 `null` 也算 `$exists`，會讓多個無邀請碼／無 client_id 的文件互相衝突；限定字串才能正確排除 `null` 與缺欄位
- **複合索引**：針對同時使用 filter + sort 的高頻查詢（如 `room_id` 過濾 + `created_at` 排序）
- **Multikey 索引**：`rooms.members` 是陣列欄位，MongoDB 自動為陣列中的每個值建立索引條目

### 驗證查詢是否使用索引

使用 MongoDB 的 `explain()` 可以查看查詢計畫，確認是否有走索引。

#### 方法一：mongosh

```bash
# 進入容器
docker exec -it <mongodb-container-name> mongosh "mongodb://root:password@localhost:27017/chatroom?authSource=admin"

# 查看某個 collection 的所有索引
db.messages.getIndexes()

# 用 explain 確認查詢是否走索引
db.messages.find({room_id: "xxx"}).sort({created_at: -1}).limit(20).explain("executionStats")
```

#### 方法二：Mongo Express

瀏覽器打開 `http://localhost:8081`，進入指定資料庫 → 點進 collection → 頁面最下方的 **Indexes** 區塊可查看已建立的索引。

#### 解讀 explain 結果

重點看 `queryPlanner.winningPlan` 中的 stage：

| Stage | 含義 | 是否走索引 |
|-------|------|-----------|
| `IXSCAN` | Index Scan，走索引掃描 | ✅ |
| `EXPRESS_IXSCAN` | MongoDB 8.0 對 unique 索引的快速路徑 | ✅ |
| `COLLSCAN` | Collection Scan，全表掃描 | ❌ 需要加索引 |
| `FETCH` | 根據索引結果回表取完整文件 | 正常（配合 IXSCAN） |

```javascript
// 範例：確認 messages 查詢走了複合索引
db.messages.find({room_id: "xxx"}).sort({created_at: -1}).explain("executionStats")

// 期望看到的 winningPlan 結構：
// LIMIT → FETCH → IXSCAN (indexName: "room_id_1_created_at_-1")
//
// 如果出現 COLLSCAN，代表該查詢沒有走索引，需要檢查索引是否正確建立
```

#### executionStats 關鍵指標

| 指標 | 說明 |
|------|------|
| `totalKeysExamined` | 掃描的索引鍵數量 |
| `totalDocsExamined` | 掃描的文件數量 |
| `nReturned` | 實際回傳的文件數量 |

理想情況下 `totalDocsExamined` 應接近 `nReturned`。若 `totalDocsExamined` 遠大於 `nReturned`，代表掃描了過多文件，索引可能不夠精準。

---

## 房間授權與回應模型

### 回應模型分層

房間相關 API 依據請求者身份回傳不同層級的資料：

| 模型 | 使用場景 | 包含欄位 | 排除欄位 |
|------|---------|---------|---------|
| `RoomSummary` | 列表端點、非成員 | id, name, description, member_count, is_member, owner_name... | members, member_roles, invite_code |
| `RoomResponse` | 成員詳情端點 | 全部欄位 | invite_code 僅 owner/admin 可見 |

```python
# 模型繼承關係（backend/app/models/room.py）
class _RoomResponseBase(RoomBase):  # 共用基底：id, owner_id, member_count, has_password, is_member...
class RoomSummary(_RoomResponseBase):  # 無額外欄位（列表/非成員用）
class RoomResponse(_RoomResponseBase):  # + members, member_roles, invite_code
```

### 成員資格授權 Dependency

`require_room_membership`（`backend/app/auth/dependencies.py`）統一檢查房間成員資格：

- 非成員 + PUBLIC 房間 → 403 Forbidden
- 非成員 + PRIVATE 房間 → 404 Not Found（不洩漏存在性）
- 成員 → 放行

**套用的端點：**

| 端點 | Dependency |
|------|-----------|
| `GET /rooms/{room_id}/members` | `require_room_membership` |
| `GET /rooms/{room_id}/messages` | `require_room_membership` |
| `GET /messages/room/{room_id}` | `require_room_membership` |
| `POST /messages/room/{room_id}/search` | `require_room_membership` |

**特殊處理的端點：**

| 端點 | 行為 |
|------|------|
| `GET /rooms/` | 回傳 `RoomSummary[]`（含 is_member 標記） |
| `GET /rooms/{room_id}` | 成員→`RoomResponse`，非成員 PUBLIC→`RoomSummary`，PRIVATE→404 |

### invite_code 可見性

invite_code 僅在 `RoomResponse` 中回傳，且受角色限制：

- **owner / admin** → 可見
- **一般成員** → `null`
- **非成員** → 不在 `RoomSummary` 中

---

## 認證 Token 生命週期

### Token 架構

系統採用 **Access Token + Refresh Token** 雙 token 機制，所有 token 均存放於 **HttpOnly cookie**，前端 JavaScript 完全無法存取，徹底防止 XSS 竊取。

| Token 類型 | 有效期 | 儲存位置 | 用途 |
|---|---|---|---|
| Access Token | 8 小時 | HttpOnly cookie（僅限） | API 請求認證 |
| Refresh Token | 7 天 | HttpOnly cookie（僅限） | 換發新的 Access Token |

### 靜默刷新流程

Token 刷新完全由 BFF 層（SvelteKit server-side）透過 `bffAuthRequest` 透明處理，前端瀏覽器不參與任何 token 操作：

```
使用者登入 → 後端回傳 token → BFF 設置 HttpOnly cookies（前端不碰 token）
     │
     ├── BFF 受保護請求：bffAuthRequest 自動處理
     │     ├── 從 httpOnly cookie 讀取 access_token
     │     ├── token 未過期 → 直接帶 token 呼叫後端
     │     ├── token 已過期 → 先用 refresh_token 換發 → 更新 cookie → 再呼叫後端
     │     └── 後端回 401 → refresh + 重試（一次）→ 仍失敗 → 回 401 給前端
     │
     ├── 前端收到 401：apiClient 統一處理
     │     └── 自動登出 → 導向登入頁
     │
     └── SSR 層：+layout.server.js 載入時
           ├── access token 未過期 → 直接驗證
           └── access token 已過期 → bffAuthRequest 透明 refresh → 再驗證
```

### 安全設計

- **前端零 token 存取**：前端不持有任何 JWT token，localStorage / JS cookie / page data 均不存放 token
- **Token 類型隔離**：Access Token 和 Refresh Token 互不通用（JWT 中以 `type: "refresh"` 區分）
- **Refresh Token Rotation**：每次刷新都會發行新的 Refresh Token，舊的自動失效
- **HttpOnly Cookie**：雙 token 均存於 HttpOnly cookie，JavaScript 無法存取，防止 XSS 竊取
- **WebSocket Ticket**：WebSocket 連線不在 URL 傳遞 JWT，改用 Redis 一次性 ticket（TTL 30 秒）

### 相關端點

| 端點 | 說明 |
|---|---|
| `POST /api/auth/login` | 登入，BFF 將 token 設為 HttpOnly cookie（不回傳 token 給前端） |
| `POST /api/auth/refresh` | 用 refresh_token 換發新 token（BFF server-side 呼叫） |
| `POST /api/auth/logout` | 登出，清除所有 cookie |
| `POST /api/ws/ticket` | 取得一次性 WebSocket 連線 ticket（需認證） |

## 前端 BFF 架構設計

### BFF (Backend-for-Frontend) 概念

BFF 是一種架構模式，在前端和後端 API 之間建立一個中間層，專門為前端需求量身定制 API。在 SvelteKit 中，這通過 API 路由實現。

```
┌─────────────────────┐
│   瀏覽器/客戶端       │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  SvelteKit BFF 層      ← 前端服務器
│  (/src/routes/api)  │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│   FastAPI 後端       │  ← 後端服務器
│   (真實 API)         │
└─────────────────────┘
```

### BFF 層實現

#### 1. API 路由結構

**位置**: `/frontend/src/routes/api/`

所有受保護的 BFF routes 使用 `bffAuthRequest`（`$lib/bff-auth.ts`），自動處理 httpOnly cookie 讀取、token 過期透明 refresh、後端 401 重試：

```typescript
// +server.ts - BFF API 端點（以 dashboard 為例）
import { json, type RequestHandler } from '@sveltejs/kit';
import { bffAuthRequest } from '$lib/bff-auth';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';

export const GET: RequestHandler = async ({ cookies }) => {
    try {
        // bffAuthRequest 自動從 httpOnly cookie 取 token、處理 refresh
        const [user, rooms, notifications] = await Promise.all([
            bffAuthRequest(cookies, '/api/auth/me'),
            bffAuthRequest(cookies, '/api/rooms/?limit=100'),
            bffAuthRequest(cookies, '/api/notifications/unread'),
        ]);

        return json(createBFFResponse({ user, rooms, notifications }));
    } catch (error: any) {
        // toBffErrorResponse 統一處理：401→UNAUTHORIZED，其餘→對應 status code
        return toBffErrorResponse(error, '獲取儀表板資料失敗');
    }
};
```

---

## ⚡ SvelteKit 最佳實踐

### 路由組織

```
src/routes/
├── +page.svelte          # 首頁
├── app/                  # 應用路由（URL 含 /app/ 前綴）
│   ├── +layout.svelte    # 共享佈局
│   ├── dashboard/        # /app/dashboard
│   ├── rooms/            # /app/rooms
│   ├── room/[id]/        # /app/room/:id
│   └── profile/          # /app/profile
└── (auth)/               # 認證路由組（不影響 URL）
    ├── login/            # /login
    └── register/         # /register
```

### Svelte 5 Runes 語法

```typescript

// 響應式狀態
let count = $state(0);
let doubled = $derived(count * 2);

// 副作用
$effect(() => {
  console.log(`Count is now ${count}`);
});

// 組件 props
let { title, children } = $props();
```

### 路由參數存取

```svelte
<script>
  import { page } from '$app/stores';

  // Svelte 5 Runes 語法（本專案統一使用此寫法）
  let roomId = $derived($page.params.id);
</script>
```

---

## ⏰ 時區處理

### 問題與解決方案

#### 核心問題
JavaScript 的 `Date` 構造函數對無時區標識的字符串處理不一致：
```javascript
// 錯誤：被解析為本地時間
new Date("2024-01-20T10:00:00")  // 本地時間 10:00

// 正確：被解析為 UTC
new Date("2024-01-20T10:00:00Z")  // UTC 10:00
```

#### 三層防護機制

**1. 後端序列化**

```python
@field_serializer('created_at', 'updated_at')
def serialize_datetime(self, dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()
```

**2. 前端防禦**

```typescript
function normalizeTimeString(dateStr: string): string {
  if (!dateStr) return dateStr;

  // 如果已有時區標識，直接返回
  if (dateStr.includes('+') || dateStr.includes('-') || dateStr.endsWith('Z')) {
    return dateStr;
  }

  // 沒有時區標識，假設為 UTC，添加 Z 後綴
  return dateStr + 'Z';
}
```

**3. 工具函數**

```typescript
// 格式化為相對時間（如 "剛剛"、"N 分鐘前"、"N 天前"）
// 超過 7 天顯示 "MM-DD"，跨年顯示 "YYYY-MM-DD"
export function formatDateTime(dateStr: string): string;

// 格式化為本地時間（如 "18:00"）
export function formatTime(dateStr: string): string;

// 依日期分組訊息（用於聊天室日期分隔線）
export function groupMessagesByDate<T extends { created_at: string }>(
    messages: T[]
): Array<{ date: string; messages: T[] }>;
```

---

## 🔧 WebSocket 管理

### 後端連線管理與 Debounce 機制

**位置**: `/backend/app/websocket/manager.py`

後端 `ConnectionManager` 採用兩層 debounce 機制，避免使用者快速切換房間時產生不必要的事件廣播：

#### 1. 全域離線 Debounce（3 秒）

使用者從**所有房間**斷開後，不會立即標記為離線。等待 3 秒（`_disconnect_debounce_seconds`），若期間重新連線則取消離線流程。超時後清除 `user_info`、`global_online_users`，對每個房間廣播 `user_left`，再廣播 `user_status_changed(is_online=False)`。

```
disconnect（最後一個房間） → 排程 _execute_offline（3s）
                              ├─ 3s 內重連 → 取消，保持在線
                              └─ 超時 → 清除狀態 + 廣播 user_left（per-room）+ 廣播離線
```

#### 2. Per-Room Rejoin Debounce（5 秒）

使用者離開某房間後，不會立即從 `room_users` 移除。等待 5 秒（`_room_rejoin_debounce_seconds`），若期間重新連線**同一房間**，則：
- 取消延遲移除
- **跳過 `user_joined` 廣播**（避免其他使用者看到重複的「XXX 加入了聊天室」系統訊息）
- 仍正常發送 `room_users` 列表給重連的使用者

```
disconnect（房間 A） → 排程 _execute_room_leave（5s）
                        ├─ 5s 內重連房間 A → 取消，不廣播 user_joined
                        ├─ 連線房間 B → 不受影響，正常廣播
                        └─ 超時 → 從 room_users 移除（不廣播 user_left）
```

> **在線狀態與成員離開的職責分離**: `_execute_room_leave` 僅處理切換房間的場景（使用者仍在線上），因此不廣播 `user_left`。真正離線由 `_execute_offline` 的 `user_status_changed(is_online=False)` 通知所有房間。成員主動離開房間（API 操作）則由 Service 層 `leave_room` 廣播 `user_left(removed=true)`，前端收到後將該使用者從成員陣列移除，避免後續 `user_status_changed` 誤將其設回在線。

> **注意**: 全域離線 debounce（3s）觸發時，會一併清理該使用者所有 pending room-leave tasks，避免殘留。

### 客戶端連線管理（一次性 Ticket 機制）

#### 為什麼 WebSocket 繞過 BFF 直連後端

REST API 走 BFF 有明確價值：httpOnly cookie 管理、token 透明 refresh、資料聚合與轉換。但 WebSocket 是持久連線，若經過 BFF 中轉只會增加延遲和架構複雜度，沒有實際好處。因此 WebSocket 直接連線後端，認證則透過一次性 ticket 解決安全問題。

WebSocket 連線不再直接傳遞 JWT token，改為透過 BFF 取得 Redis 一次性 ticket（TTL 30 秒），避免在 URL 中暴露長效 token：

```
前端 connect(roomId)
  → BFF POST /api/ws/ticket { room_id }     ← httpOnly cookie 認證
  → 後端產生 Redis ticket（TTL 30s）
  → 前端用 ticket 連線 ws://host/ws/{roomId}?ticket={ticket}
  → 後端驗證 ticket（一次性，用後即刪）→ 建立 WebSocket 連線
```

```typescript
class WebSocketManager {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private baseReconnectDelay = 1000;       // 基準延遲（用於重置）
  private currentReconnectDelay = 1000;    // 當前延遲（指數增長）
  private maxReconnectDelay = 30000;       // 上限 30 秒

  async connect(roomId: string) {
    // 透過 BFF 取得一次性 ticket（不需手動傳 token）
    const ticket = await apiClient.wsTicket.create(roomId);
    const wsUrl = this.buildWsUrl(roomId, ticket);  // 動態構建 URL
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.currentReconnectDelay = this.baseReconnectDelay;  // 用基準值重置
    };

    this.ws.onclose = (event) => {
      // 僅在非正常關閉且 close code 允許時重連
      if (!event.wasClean && this.shouldReconnect(event.code)) {
        this.scheduleReconnect();
      }
    };
  }

  // 安排重連（指數退避 + 隨機 jitter）
  private scheduleReconnect() {
    this.reconnectAttempts++;
    // 指數退避 + 隨機 jitter（0~30%），上限 30 秒
    const jitter = Math.random() * 0.3;
    const delay = Math.min(
      this.currentReconnectDelay * (1 + jitter),
      this.maxReconnectDelay
    );
    setTimeout(() => this.performReconnect(), delay);
    // 更新下次重連延遲（指數退避）
    this.currentReconnectDelay = Math.min(
      this.currentReconnectDelay * 2,
      this.maxReconnectDelay
    );
  }

  // 執行重連（每次重連都取得新的 ticket）
  private async performReconnect() {
    if (this.roomId) {
      await this.connect(this.roomId);
    }
  }
}
```

---

## 🤖 AI 聊天助理

聊天室內建 AI 助理，提供兩個入口：`@bot <問題>` 即時問答（streaming）與 `/summary` 對話摘要。LLM 呼叫封裝於 Service 層（`app/services/ai_service.py`），WebSocket handler 只負責觸發與廣播，遵守三層架構（商業邏輯不寫在 handler）。AI 為**選用**功能：未配置 API key 時功能停用，不影響聊天室其他功能。

> **設計理由見 ADR**：本章聚焦 AI 助理**如何運作與使用**（契約、流程、設定）。背後「為什麼這樣設計」的取捨——bot 為何是真實使用者、LLM 為何收斂於 Service 層、AI 為何採選用 fail-soft、streaming 為何切兩階段——統一記錄於 `c4-architecture.md` 的 **ADR-004**。本章不重述理由，僅於對應段落標註決策編號，避免兩份文件各自演化而脫節。

### 基礎建設

**AI 服務層（`AIService`）**

- 使用 [Pydantic AI](https://ai.pydantic.dev/) 封裝 LLM agent，**供應商可切換**（`AI_PROVIDER`）：`nvidia`（NVIDIA NIM，OpenAI 相容端點）或 `gemini`（Google 原生 SDK）。`_get_model` 依設定分派，所有 agent 共用同一個惰性模型。
- agent **惰性建立**（首次使用才需 API key），所有呼叫共用同一個 module 層 agent；`AIService` 本身無狀態，故 DI 工廠每次回傳新實例也不會重複初始化模型。
- 未配置**當前供應商**的 API key 時拋 `AppError`（訊息含供應商名，如「AI 助理尚未配置（gemini 缺少 API key）」），不會真的打 API。
- **供應商差異**：
  - **逾時**：Gemini 須透過自訂 httpx client 設定（`ModelSettings.timeout` 對 Google SDK 不生效）；NVIDIA 走 `ModelSettings.timeout`。
  - **思考（thinking）**：Gemini 用 `GoogleModelSettings` 並設 `google_thinking_config={"thinking_budget": 0}` 關閉思考——`gemini-2.5-flash` 預設開啟思考，而思考 token 會算進 `max_tokens` 預算，不關會把回覆在生成中途截斷（本專案為非思考用途）。NVIDIA（Nemotron）思考預設關閉、需 system prompt 顯式開啟，故無此設定。
  - 兩者皆套用相同的 temperature / max_tokens。

**Bot 身分（`app/core/bot.py`）**

- Bot 是一個**真實的 MongoDB 使用者**（固定 `user_id`），讓 bot 訊息能正常渲染頭像／暱稱並走正規訊息流（理由見 ADR-004 決策 1）。
- 啟動時由 lifespan 呼叫 `ensure_bot_user` 冪等種子化（隨機密碼雜湊，永不可透過密碼登入）；user_id 快取於模組層供 WebSocket handler 取用。
- `is_bot_trigger(content)` 判斷訊息是否呼叫 bot：僅當 `@bot` 後接空白或為字串結尾才觸發（避免「@bother」之類誤判），回傳去除前綴後的問題。

**設定（`app/config.py`）**

| 設定 | 預設 | 說明 |
|------|------|------|
| `AI_PROVIDER` | `nvidia` | 供應商切換：`nvidia`（NIM）或 `gemini`（Google） |
| `NVIDIA_API_KEY` | `None` | NVIDIA NIM key；當前供應商未設 key 時 @bot 回「尚未配置」而不打 API |
| `NVIDIA_BASE_URL` | `https://integrate.api.nvidia.com/v1` | OpenAI 相容端點 |
| `NVIDIA_MODEL` | `nvidia/nemotron-3-super-120b-a12b` | NVIDIA 使用的模型 |
| `GOOGLE_API_KEY` | `None` | Gemini key（`AI_PROVIDER=gemini` 時生效） |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini 使用的模型 |
| `BOT_RATE_LIMIT_PER_MINUTE` | `5` | 每使用者每分鐘 AI 上限（@bot 與 /summary 共用） |

**依賴注入**：`create_ai_service()` 工廠 + `AIServiceDep` 別名（與其他 service 一致）。`GET /api/ai/status`（HTTP）透過 `AIServiceDep` 注入；`@bot` / `/summary` 觸發發生在 WebSocket，handler 則直接 `await create_ai_service()`。

### 觸發與限流

`handle_chat_message` 在訊息落地後偵測是否為 AI 觸發（僅 `TEXT` 訊息），命中則交由對應 handler。這段「管線與防護」與回覆生成方式無關，無論回覆是否 streaming 都一致：

| 機制 | 說明 |
|------|------|
| **限流** | 每使用者每分鐘上限（`BOT_RATE_LIMIT_PER_MINUTE`，預設 5；`@bot` 與 `/summary` **共用此額度**），複用既有的 `SlidingWindowRateLimiter`（Redis 滑動視窗，key `rate_limit:bot:{user_id}`）。檢查失敗 fail-open，不擋 AI |
| **防迴圈保險** | bot 尚未種子化、或觸發者就是 bot 自身時直接不處理，避免 bot 回覆自己無限觸發 |
| **空問題提示** | `@bot` 後無內容時回提示且不打 API |
| **`skip_membership_check`** | bot 是系統發訊者、非房間成員，`create_message` 以此參數（預設 `False`，現有呼叫零影響）跳過成員資格檢查；也因此正常訊息的通知迴圈不會掃到 bot |
| **刻意不發通知** | bot 訊息走正規落地（產生 seq、持久化、廣播）但**不觸發通知**，避免每次回話全房間收到通知轟炸 |
| **完整自我守護** | handler 內任何失敗只回報觸發者（或收掉預覽），不影響使用者的原始訊息與聊天室運作 |

> bot 回覆透過正規 `create_message` 落地，因此會取得 seq、可持久化、可被 ADR-003 的斷線 gap 補發涵蓋——與真人訊息走同一條管線。

### @bot streaming 兩階段

`@bot` 採 streaming，讓 bot 回覆像真人逐字打字（為何切成兩階段、預覽為何不持久化，見 ADR-004 決策 4）。`AIService.stream_reply` 以 `agent.run_stream` + `stream_text(delta=True)` 逐段 yield 文字增量（async generator），handler 分兩階段廣播：

```
階段一（瞬態預覽）         階段二（正規落地）
─────────────────         ─────────────────
streaming 中：            streaming 結束：
broadcast bot_typing      bot 身分 create_message（取 seq、持久化）
  每個 delta 廣播全房間    → broadcast_message 廣播正式訊息
  不走 seq、不持久化       → 前端用它替換預覽氣泡
失敗 → broadcast bot_error（前端收掉預覽，不卡在「打字中」）
```

- **階段一**只是體驗層的「打字中」效果，刻意不持久化——重整／斷線重連不會看到半截預覽。
- **階段二**才是真正的訊息，享有 seq / 持久化 / gap 補發；前端收到正式訊息（`resolveBotStreamOnLanding`）後把預覽替換成最終訊息。落地時並以 `reply_to` 指回觸發的提問訊息（見〈@bot 回覆引用提問者〉）。
- 任一階段失敗（外部服務逾時／斷線／429）發 `bot_error`，前端收掉預覽。

**同房並發保護**：預覽 id 僅含 `roomId`，同房同時兩個 @bot 會讓第二次的 delta 累積進同一個預覽、首次落地又誤收他人預覽。以 module-level 的 `_bot_streaming_rooms` 集合做鎖——同房一次只允許一個 streaming，第二個請求走既有 error 路徑回報觸發者「正在回覆中」，`try/finally` 保證釋放。此鎖為單實例 in-memory，符合目前 per-room WS／單後端實例架構。

**WebSocket 事件契約（伺服器 → 客戶端）**：

| 事件 | 用途 | 主要欄位 |
|------|------|---------|
| `bot_typing` | streaming 瞬態增量 | `user`（bot 身分）、`content`（文字 delta） |
| `bot_error` | streaming 收尾錯誤 | `message`（錯誤原因） |
| （正式訊息）`message` | 階段二落地的正規訊息 | 與真人訊息相同（含 seq、`reply_to_message` 引用預覽） |

前端 `types.ts` 對應 `WSBotTypingMessage` / `WSBotErrorMessage`（已納入 `WebSocketMessage` discriminated union），`guards.ts` 的 `KNOWN_WS_TYPES` 收錄 `bot_typing` / `bot_error`；message store 以 `appendBotStream`（累積預覽）/ `resolveBotStreamOnLanding`（落地替換）/ `clearBotStream`（錯誤收尾）管理預覽生命週期。預覽重用既有訊息渲染，未動聊天頁元件。

### @bot 回覆引用提問者（reply_to）

bot 落地時帶 `reply_to` 指向觸發它的使用者提問，前端在 bot 回覆氣泡頂部顯示「引用提問」區塊（`MessageItem`；目前僅 @bot 回覆使用，未開放使用者主動回覆）。`/summary` 為指令、非回覆某人，故不帶 `reply_to`。

- **引用預覽組裝（無 N+1）**：`MessageRepository.get_reply_previews` 以單次 `$in` 批次撈回被回覆訊息，`MessageService._attach_reply_previews` 讓訊息列表回傳 `MessageWithReply`（含 `reply_to_message` 預覽：被回覆訊息的 `id`／`content`／`username`）。一般房間多無 `reply_to`，`reply_ids` 為空時不查 DB。
- **三條 WS 路徑一致**：`_format_message_payload` 偵測 `reply_to_message` 即一併輸出，覆蓋即時新訊息、歷史載入（`message_history`）、斷線補發（`message_sync`）。
- **重整也帶引用**：前端載入歷史走 `GET /api/rooms/{id}/messages`（對應後端 `rooms.py`，**非** `messages.py` 的 `/messages/room/{id}`），其 `response_model` 為 `list[MessageWithReply]`。FastAPI 會用 `response_model` 過濾欄位，回傳型別即使含 `reply_to_message`，端點宣告若仍是 `MessageResponse` 就會被靜默濾掉，造成「即時有、重整無」。因此 `get_room_messages`／`get_message_by_id` 兩個 service 方法的所有出口端點（`rooms.py` 與 `messages.py` 對應端點）`response_model` 一律對齊 `MessageWithReply`，避免換走另一條端點時引用神秘消失。
- **補引用為 fail-open**：階段二落地時，bot 訊息先以 `create_message` 寫入（產生 seq、持久化），再以 `get_message_by_id` 取含引用預覽的版本廣播。後者僅為了補上引用區塊，**包在獨立的 try 內**：取預覽失敗時降級用原訊息廣播（不帶引用），不可因此走進落地的 catch-all 而誤報「回覆儲存失敗」——訊息已經落地，重整即見。

### @bot 多輪對話記憶

@bot 預設無記憶（單輪），追問（如「那它跟 VM 差在哪」）會失去前文。為支援多輪接續，handler 在呼叫 `stream_reply` 前撈近期房間訊息組成**整房共享**的對話歷史段落傳入：

- `build_bot_history`（`core/bot.py`，純函數）只配對「使用者 @bot 提問 → 緊接的 bot 回答」，略過一般閒聊；當前這次尚未回答的提問自然不入歷史。
- 控制長度與 token 成本：時間窗 `BOT_HISTORY_WINDOW_MINUTES`（10 分鐘，過舊不帶）、最多 `BOT_HISTORY_MAX_PAIRS`（6 組往返）、單則 bot 回答截斷 `BOT_HISTORY_MAX_ANSWER_CHARS`（200 字）。
- `_build_chat_prompt` 以 **context 段落**併入當前問題，而非 pydantic-ai 的 `message_history` 結構——聊天室歷史為多人交錯、易有有問無答／連續提問等不合法配對，拼成 prompt 對髒資料更穩健。
- `AIService` 維持**無狀態**（不注入 repo）；歷史由 handler 撈取後當參數傳入。撈取／組裝失敗 **fail-open** 回空字串，不擋回答。
- 撈取走 `MessageService.get_room_messages_for_context`（回傳 `MessageInDB`、**不補頭像**）：歷史與 `/summary` 都只需 `username`／`content`，跳過 `get_room_messages` 尾端 `_format_with_avatars` 的批次使用者查詢，省一次無謂 `$in`。
- tz 正規化：PyMongo 預設回傳 naive UTC datetime，套時間窗比較前統一成 aware，避免炸裂。

### /summary 對話摘要

使用者輸入 `/summary`（大小寫不敏感、完整比對）即由 AI 助理摘要近期對話：

1. 撈近期 30 則訊息（經 `get_room_messages_for_context`，純文字、不補頭像），組成 transcript（最舊→最新，排除 bot 自己與非文字訊息）。
2. 呼叫 `AIService.summarize`（**one-shot，非 streaming**，獨立的 summary agent，與 @bot 共用同一個 `_get_model()`）。
3. 以 bot 身分正規落地廣播（跳過成員檢查、刻意不發通知），訊息前綴 `📋 對話摘要`。

與 @bot 共用每使用者限流額度。`/summary` 指令本身以一般訊息呈現並正常 ack，故**前端零改動**即支援。`handle_chat_message` 以 `elif` 與 @bot 並列偵測（兩者互斥）。

### 輸入輔助與全形相容

- **指令自動完成**：`MessageInput` 在開頭輸入 `/` 或 `@` 時跳出指令提示 popup（`@bot`、`/summary`），支援 ↑↓ 導航、Enter/Tab/點擊選定、Esc 關閉，提升指令可發現性。
- **全形相容**：後端觸發判斷（`is_bot_trigger` / `is_summary_command`）先做 **NFKC 正規化**再比對，修正中文輸入法常打出的全形「＠bot」「／summary」靜默失敗問題。全形→半形為 1:1 對應，故前綴長度與原字串索引對齊，問題內容仍取原文。

### 上線狀態顯示

`GET /api/ai/status` 回傳 AI 助理是否可用，供前端在成員列表標示。**「上線」語意 = 當前供應商已配置 API key**（`AIService.is_available()`，純設定判斷，不呼叫外部 AI API）——bot 永不連 WebSocket，故不沿用 `global_online_users` 機制。

- 回應 `{ enabled, bot_username }`（`bot_username` 以後端 `BOT_USERNAME` 為權威來源）。
- 前端 `aiStatus` store 登入後查一次並去重（樂觀標記避免多元件實例並發重複請求），fail-open：取不到狀態時維持「不可用」，不阻斷聊天。
- `UserList` 將 AI 助理置頂顯示，依 `enabled` 標示上線／離線。

### AI 測試（零成本）

AI 相關測試**全程不打真實 API**：用 Pydantic AI 的 `TestModel` / `FunctionModel` 搭配 `agent.override(model=...)` 覆寫 agent 模型，驗證 `stream_reply` 的串流拼接內容與 `summarize` 的摘要輸出。這正是「LLM 邏輯收斂於 Service 層」（ADR-004 決策 2）帶來的可測試性。

> 注意：`stream_text(delta=True)` 內建 debounce，無延遲時增量會合併，故測試驗證「拼接後的完整內容」而非逐段 delta 序列。

---

## 🔗 相關檔案參考

- **後端時間序列化**: `/backend/app/models/room.py`（`serialize_datetime` field_serializer）
- **前端時間工具**: `/frontend/src/lib/utils/datetime.ts`
- **WebSocket 管理**: `/frontend/src/lib/websocket/`
