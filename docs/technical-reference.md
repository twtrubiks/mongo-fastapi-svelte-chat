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
| `rooms` | `name` | unique | 防止重複房間名稱（TOCTOU 競態防護） |
| `rooms` | `invite_code` | partial unique | 防止重複邀請碼（僅對有 invite_code 的文件生效） |
| `rooms` | `members` | multikey | 查詢「我的房間」列表（陣列欄位） |
| `rooms` | `{ is_public, created_at desc }` | 複合索引 | 探索頁面公開房間查詢 + 排序 |
| `notifications` | `{ user_id, created_at desc }` | 複合索引 | 通知列表 + 未讀計數 |
| `room_invitations` | `invite_code` | unique | 防止重複邀請碼，加速邀請驗證 |

### 索引選擇原則

- **Unique 索引**：不只是效能，更是資料正確性約束（防止重複 username/email/room name）
- **Partial unique 索引**：`rooms.invite_code` 使用 `partialFilterExpression: {invite_code: {$exists: true}}`，僅對有該欄位的文件生效，避免無邀請碼的房間因 `null` 衝突
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

## 🔗 相關檔案參考

- **主專案**: [README.md](../README.md)
- **後端時間序列化**: `/backend/app/models/room.py:78-83`
- **前端時間工具**: `/frontend/src/lib/utils/datetime.ts`
- **WebSocket 管理**: `/frontend/src/lib/websocket/`