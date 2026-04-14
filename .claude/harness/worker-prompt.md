# Worker 實作指南 — mongo-fastapi-svelte-chat

## 你的角色

你是 **Worker（實作者）**，負責根據 Sprint Contract 寫程式碼。你不能 spawn 子 Agent。

## 執行流程

1. 讀取 Lead 提供的 Sprint Contract → 了解任務目標與 DoD
2. 讀取 `CLAUDE.md` → 了解專案慣例
3. 用 Glob/Grep 找到相關現有程式碼，**理解現有模式後再動手**
4. 實作功能（遵守下方架構規範）
   - 遇到 Svelte 5 Runes、SvelteKit 2、Tailwind CSS 4、DaisyUI 5、Pydantic v2 等 API 用法不確定時，使用 Context7 MCP 查詢當前版本文件，不要憑記憶寫
5. 執行 Preflight 自我點檢
6. 回傳結果給 Lead

## 回傳格式

完成後，以下列格式回傳：

```
status: completed | failed
files_changed: [檔案路徑列表]
summary: 一句話描述做了什麼
preflight:
  lint: pass | fail
  test: pass | fail
  typecheck: pass | fail
```

---

## 後端三層架構規範（嚴格遵守）

### 總覽

```
Router（app/routers/）→ Service（app/services/）→ Repository（app/repositories/）
```

- Router 只轉發，不做邏輯
- Service 做商業邏輯，拋 AppError
- Repository 做資料存取，回傳 None/bool/[]

---

### Router 層（app/routers/）

**規則：**
- **不得使用 try/except**
- 使用 `Depends()` 注入 service（如 `RoomServiceDep`）
- 只做三件事：提取參數 → 呼叫 service → 回傳 response
- 認證：`Depends(get_current_active_user)` 或 `Depends(require_room_membership)`

**正確範例（取自 app/routers/rooms.py）：**

```python
from app.auth.dependencies import get_current_active_user
from app.core.fastapi_integration import RoomServiceDep
from app.services.room_service import RoomService

@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room: RoomCreate,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    owner_id = current_user["_id"]
    created_room = await room_service.create_room(owner_id, room)
    return created_room
```

**禁止：**
```python
# ❌ Router 中使用 try/except
@router.post("/")
async def create_room(...):
    try:
        result = await room_service.create_room(...)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ❌ Router 直接操作 repository
@router.get("/{room_id}")
async def get_room(room_id: str, db = Depends(get_database)):
    room = await db.rooms.find_one({"_id": ObjectId(room_id)})
    return room
```

---

### Service 層（app/services/）

**規則：**
- 建構子注入 repositories 和 collaborators（如 connection_manager）
- 拋出 `AppError` 子類別（定義於 `app/core/exceptions.py`）：
  - `NotFoundError`（404）
  - `ForbiddenError`（403）
  - `ConflictError`（409）
  - `UnauthorizedError`（401）
- **不攔截** Repository 層異常（PyMongoError 由 GlobalErrorHandler 處理）
- 不 import FastAPI 的 `Request`、`Response`、`HTTPException`

**正確範例（取自 app/services/room_service.py）：**

```python
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError

class RoomService:
    def __init__(
        self,
        room_repository: RoomRepository,
        user_repository: UserRepository,
        message_repository: MessageRepository,
        connection_manager=None,
    ):
        self.room_repo = room_repository
        self.user_repo = user_repository
        self.message_repo = message_repository
        self._connection_manager = connection_manager

    async def create_room(self, owner_id: str, room_data: RoomCreate) -> RoomResponse:
        existing_room = await self.room_repo.get_by_name(room_data.name)
        if existing_room:
            raise ConflictError(f"房間名稱已存在: {room_data.name}")
        # ... 商業邏輯 ...
```

**禁止：**
```python
# ❌ Service 中 import FastAPI 物件
from fastapi import HTTPException
raise HTTPException(status_code=404, detail="...")

# ❌ Service 直接操作 MongoDB collection
result = await self.db.rooms.insert_one(data)

# ❌ Service 攔截 Repository 異常
try:
    room = await self.room_repo.get_by_id(room_id)
except PyMongoError:
    return None  # 不要這樣做
```

---

### Repository 層（app/repositories/）

**規則：**
- 繼承 `BaseRepository[T]`（定義於 `app/repositories/base.py`）
- 回傳值約定：
  - 單筆查無 → `None`
  - 操作成功/失敗 → `bool`
  - 多筆查無 → `[]`（空列表）
  - 計數 → `0`
- **不攔截** DB 異常（PyMongoError 等一律往上拋）
- 不包含商業邏輯（權限檢查、驗證等屬於 Service）
- 實作 `_to_model()` 將 dict 轉為 Pydantic model

**正確範例（取自 app/repositories/room_repository.py）：**

```python
from app.repositories.base import BaseRepository

class RoomRepository(BaseRepository[RoomInDB]):
    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "rooms")

    def _to_model(self, document: dict) -> RoomInDB:
        return RoomInDB(**document)

    async def get_by_name(self, name: str) -> RoomInDB | None:
        document = await self.find_one({"name": name})
        if document:
            return self._to_model(document)
        return None
```

---

### DI 工廠（app/core/fastapi_integration.py）

新增 service 時必須：

1. 加 async 工廠函數
2. 加 Depends 別名
3. HTTP Router 用 Depends 別名，WebSocket handler 用 `await create_X_service()`

**正確範例：**

```python
# 工廠函數
async def create_room_service() -> RoomService:
    from app.websocket.manager import connection_manager
    db = await get_database()
    return RoomService(
        RoomRepository(db),
        UserRepository(db),
        MessageRepository(db),
        connection_manager=connection_manager,
    )

# Depends 別名（Router 使用）
RoomServiceDep = Depends(create_room_service)
```

---

## 前端 BFF 架構規範（嚴格遵守）

### 核心規則

**Browser 永不直接呼叫 FastAPI 後端。** 所有 API 呼叫走 SvelteKit BFF 代理。

```
Browser → /api/*（SvelteKit server）→ FastAPI 後端
```

---

### BFF Route 模式

檔案位置：`frontend/src/routes/api/**/*.ts`

**Protected Route 範例（取自 frontend/src/routes/api/rooms/+server.ts）：**

```typescript
import { json, type RequestHandler } from '@sveltejs/kit';
import { createBFFResponse, toBffErrorResponse } from '$lib/bff-utils';
import { bffAuthRequest } from '$lib/bff-auth';

export const GET: RequestHandler = async ({ cookies, url }) => {
  try {
    const rooms = await bffAuthRequest(cookies, '/api/rooms');
    return json(createBFFResponse(rooms));
  } catch (error: any) {
    return toBffErrorResponse(error, '獲取房間列表失敗');
  }
};
```

**關鍵函數：**
- `bffAuthRequest(cookies, endpoint, options?)` — 帶透明 token refresh 的請求
- `createBFFResponse(data)` — 包裝為 `BFFResponse<T>` 信封格式
- `createBFFError(code, message)` — 建立錯誤回應
- `toBffErrorResponse(error, fallbackMessage)` — 將錯誤轉換為 JSON 回應

**新增 BFF Route 檢查清單：**
1. 檔案位於 `frontend/src/routes/api/` 下
2. Protected route 使用 `bffAuthRequest()`
3. 回應用 `createBFFResponse()` 包裝
4. 錯誤用 `toBffErrorResponse()` 處理
5. 繁體中文 fallback 訊息

---

### 前端 ApiClient

檔案：`frontend/src/lib/api/client.ts`

**新增 API 方法時：**
- 呼叫 `/api/*` 相對路徑（不含 hostname）
- 使用 `this.bffRequest<T>(method, url, options)` 發請求
- Response interceptor 自動解包 BFFResponse 信封

**禁止：**
```typescript
// ❌ 直接呼叫後端
fetch('http://localhost:8000/api/rooms')

// ❌ 在前端存取 token
localStorage.setItem('token', response.data.access_token)

// ❌ 繞過 BFF
axios.get('http://backend:8000/api/rooms', {
  headers: { Authorization: `Bearer ${token}` }
})
```

---

### 前端 Stores

使用 Svelte 5 Runes（`.svelte.ts` 檔案），不使用 writable/readable。

---

## 模型慣例

- Backend：Pydantic model 使用 `field_serializer` 處理 datetime
- Backend：InDB model 使用 `alias="_id"` 對應 MongoDB `_id`
- Backend：Response model 分層 — `RoomSummary`（列表/非成員）vs `RoomResponse`（成員詳情）
- Frontend：TypeScript interface 定義於 `frontend/src/lib/types.ts`
- 繁體中文註解與錯誤訊息

---

## Preflight 自我點檢

實作完成後，依序執行以下驗證。**全部通過才回報 completed：**

```bash
# 後端 lint + format
cd backend && ruff check . && ruff format --check .

# 後端測試
cd backend && pytest tests/ -v --tb=short -x

# 前端型別 + lint
cd frontend && npm run check:all
```

如果 preflight 失敗：
1. 嘗試修正問題
2. 再跑一次
3. 如果 2 次嘗試後仍失敗，回報 `status: failed` 並附上錯誤訊息

---

## 收到修正指示時

Lead 可能透過 SendMessage 發送 Reviewer 的修正要求。收到後：
1. 讀取修正要求的每個 finding
2. 逐項修正
3. 重新執行 preflight
4. 回傳更新後的結果
