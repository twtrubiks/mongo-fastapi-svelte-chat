# /harness-review — 品質審查（合併 audit + contract）

## 你的角色

你是 **Reviewer（審查官）**，對現有程式碼做品質審查。

---

## 模式

| 參數 | 模式 | 說明 |
|------|------|------|
| 無 flag | **唯讀** | 靜態審查，不修改任何檔案 |
| `--fix` | **修正** | 靜態審查 + `/simplify` + 自動修正 critical/major（原 `/harness-audit`） |
| `--deep` | **深度** | 靜態審查 + `svelte-check` / `ruff check` 工具驗證 + WS 事件契約交叉比對 + `any` 滲透掃描（原 `/harness-contract`） |
| `--fix --deep` | **完整** | 以上全部 |

模式可與範圍參數組合，例如：`/harness-review backend --fix`

---

## 啟動流程

### Step 1：判定審查範圍

根據使用者參數決定掃描範圍：

| 參數 | 範圍 |
|------|------|
| 無參數 | 全專案（backend + frontend） |
| `backend` | 只掃 `backend/app/` |
| `frontend` | 只掃 `frontend/src/` |
| 指定路徑（如 `backend/app/routers/rooms.py`） | 只掃該檔案 |
| `ws` | 只跑 WS 事件契約比對（需搭配 `--deep`） |
| `any` | 只跑 `any` 滲透掃描（需搭配 `--deep`） |

宣告：「開始審查 {範圍}，模式：{唯讀 / 修正 / 深度 / 完整}。」

### Step 2：讀取審查規範

1. 讀取 `CLAUDE.md` 了解專案慣例
2. 讀取 `.claude/harness/reviewer-prompt.md` 取得完整 checklist
3. `--fix` 模式額外讀取 `.claude/harness/worker-prompt.md` 了解架構規範（修正時需遵守）

---

## Phase 1：靜態審查（所有模式都執行）

依照 `reviewer-prompt.md` 的 checklist，逐項掃描範圍內的程式碼。

### 後端審查（當範圍包含 backend）

用 Grep/Read 檢查以下違規：

**三層架構：**
- 掃描 `backend/app/routers/` — 有無 try/except、直接操作 DB、商業邏輯
- 掃描 `backend/app/services/` — 有無 import HTTPException/Request、直接操作 collection、未用建構子注入
- 掃描 `backend/app/repositories/` — 有無 try/except 攔截 DB 異常、商業邏輯、未繼承 BaseRepository
- 檢查 `backend/app/core/fastapi_integration.py` — 所有 service 是否都有工廠函數 + Depends 別名

**安全：**
- Grep 硬編碼 secrets 模式（`sk-`、`AKIA`、`password =`）
- Grep 未經 ObjectId 驗證的 user input 進 query
- Grep `$regex` / `re.compile` / `re.search` — 檢查使用者輸入是否經過 `re.escape()` 再進入正則表達式，未 escape → critical（Regex injection / ReDoS）

**授權一致性：**
- 比對 `backend/app/websocket/auth.py` 與 `backend/app/services/` — WebSocket 入口的授權邏輯是否與 HTTP 路徑使用相同的 Service 方法，而非自行實作判斷
- 掃描 `backend/app/websocket/auth.py` — 驗證函式是否包含寫入操作（如 `join_room`、`add_member`），名為 verify/check 的函式不應有副作用
- 檢查授權判斷使用的欄位 — 是否依賴遺留欄位（如 `is_public`）而非正式的權限欄位（如 `join_policy` + `room_type`）

**業務規則一致性：**
- 掃描 `backend/app/services/` — 有無定義 `validate_*` / `check_*` 方法但同類別的 `create_*` / `update_*` 未呼叫
- 比對 `backend/app/models/` 的 Pydantic 約束（`max_length`、`ge`、`le`）與 `backend/app/services/` 的業務常數 — 數值是否一致
- 比對 `backend/app/websocket/handlers.py` 與 `backend/app/routers/` — 同一業務操作的兩條入口是否套用相同的驗證規則
- Grep `frontend/src/lib/components/` 和 `frontend/src/routes/app/` 所有 `maxlength`、`maxLength` 屬性，逐一比對後端 Pydantic model 的 `max_length` 或 Service 層業務常數是否對齊（全查，非抽查）
- Grep `backend/app/` 的 `broadcast_to_room` / `send_personal_message` 呼叫 — 若 payload 有新增/移除欄位，交叉檢查前端 `frontend/src/lib/types.ts` 的 `WebSocketMessage` 型別是否涵蓋（發現不同步 → 標記 major，建議加 `--deep` 做完整契約驗證）

**資料一致性：**
- 掃描 `backend/app/services/` — 有無先查後寫的 TOCTOU 模式（如 `get_by_name` → `create`），對照 `backend/app/database/indexes.py` 是否有 unique index 保底
- 掃描 `backend/app/repositories/` — 有無分兩步的關聯寫入（如 `$addToSet` + `$set`）應合併為單次 `update_one`
- 掃描 `backend/app/repositories/` — 同一 document 中互相依賴的欄位（如 `members` ↔ `member_roles`），`$pull` / `$addToSet` 其中一方時是否在同一次 `update_one` 中同步操作另一方
- 對照 `backend/app/database/indexes.py` — 業務邏輯假設的唯一性約束是否都有對應 unique index

### 前端審查（當範圍包含 frontend）

**BFF 架構：**
- Grep `frontend/src/lib/` 和 `frontend/src/routes/app/` — 有無直接呼叫 `localhost:8000` 或後端 URL
- 掃描 `frontend/src/routes/api/` — BFF route 是否使用 `bffAuthRequest`、`createBFFResponse`、`toBffErrorResponse`
- Grep token 洩漏（`localStorage`、`sessionStorage`、`document.cookie` 存取 token）

**前端慣例：**
- 掃描 stores 是否使用 Svelte 5 Runes（`$state`、`$derived`）而非 `writable`/`readable`

**信任邊界 Runtime 安全（前端）：**
- 掃描 `frontend/src/lib/websocket/` — `JSON.parse(event.data)` 的結果是否經過 runtime type guard 驗證，而非直接 `as Type` 強制轉型
- 掃描 `frontend/src/lib/bff-*.ts` 和 `frontend/src/lib/api/` — API response / interceptor 的回傳資料是否有結構驗證
- 掃描 `frontend/src/lib/stores/` 和 `frontend/src/lib/utils/` — 從後端收到的通知或事件資料在 transform 階段是否檢查必填欄位

### 簡潔性（/simplify 維度）

- 掃描明顯的重複邏輯
- 檢查過長函數（超過 50 行）
- 未使用的 import

---

## Phase 2：工具驗證 + 契約比對（僅 `--deep` 模式）

### 2a. Tool Gate（工具驗證）

直接用工具抓型別錯誤，不靠人眼：

```bash
# 前端型別檢查
cd frontend && npx svelte-check --output human

# 後端 lint
cd backend && ruff check .
```

記錄結果：

```
tool_gate:
  svelte-check: pass（0 errors）| fail（N errors，列出每個 error）
  ruff: pass | fail（N errors）
```

**svelte-check 有 error → critical**（代表型別契約已經漂移）
**ruff 有 error → major**

### 2b. WS 事件契約交叉比對

**目標：** 比對後端實際發送的 WS 事件 payload 與前端型別定義，找出不同步的欄位。

**Step 1 — 收集後端 WS 事件清單**

Grep 以下模式收集所有 WS 事件發送點：

- `backend/app/` 下的 `broadcast_to_room(`
- `backend/app/` 下的 `send_personal_message(`
- `backend/app/websocket/` 下直接 `send(json.dumps(`

對每個發送點，記錄：
- 檔案位置（file:line）
- 事件 `type` 值（如 `user_left`、`room_updated`）
- payload 包含的所有欄位名稱

**Step 2 — 收集前端型別定義**

讀取 `frontend/src/lib/types.ts`，提取 `WebSocketMessage` 的完整定義（或 discriminated union 的各子型別）。

**Step 3 — 交叉比對**

逐一比對每種事件：

| 檢查項 | 判定 |
|--------|------|
| 後端發送的欄位在前端型別中不存在 | **major** — 契約漂移 |
| 前端型別有 `payload?: any` 或 `data?: any` 作為逃生艙口 | **minor** — 型別未精確化 |
| 後端有事件 type 但前端 `WebSocketMessage.type` union 未包含 | **major** — 事件類型缺失 |

### 2c. `any` 滲透掃描

Grep `frontend/src/lib/` 下所有 `.ts` 和 `.svelte` 檔案中的 `any` 使用，分三個風險層級：

**高風險（WS handler 層）：**
- 掃描 `frontend/src/lib/websocket/` — handler 函式參數中的 `data: any`
- 掃描 `frontend/src/lib/types.ts` — `WebSocketMessage` 內的 `any` 欄位

**中風險（BFF / API 層）：**
- 掃描 `frontend/src/lib/bff-*.ts` — `BFFResponse<any>`、`catch (error: any)`
- 掃描 `frontend/src/lib/api/` — client 內的 `any`

**低風險（元件 / 工具層）：**
- 掃描 `frontend/src/lib/stores/` — store 內的 `any`
- 掃描 `frontend/src/lib/utils/` — 工具函式的 `any`
- 掃描 `frontend/src/routes/` — 元件 ref 的 `any`

高/中風險標記 major，低風險標記 minor。

---

## Phase 3：Preflight + 修正（僅 `--fix` 模式）

### 3a. Preflight（自動化驗證）

依序執行，記錄各項結果：

```bash
# 後端 lint + format（當範圍包含 backend）
cd backend && ruff check . && ruff format --check .

# 後端測試（當範圍包含 backend）
cd backend && pytest tests/ -v --tb=short -x

# 前端型別 + lint（當範圍包含 frontend）
cd frontend && npm run check:all
```

**如果 Preflight 有失敗項目：**
- 先嘗試修正 lint/format 問題（`ruff check --fix`、`ruff format`）
- 重新執行 Preflight 確認修正成功
- 測試失敗不自動修正，記錄到報告中

### 3b. /simplify 品質打磨

1. **使用 Skill tool 呼叫 `/simplify`** 對範圍內的程式碼做品質打磨
2. `/simplify` 會處理：重複邏輯提取、冗餘程式碼移除、低效表達簡化、未使用的 import 清理
3. `/simplify` 修正後，**重新執行 Preflight** 確認沒有破壞功能

### 3c. 修正 critical/major 問題

對 Phase 1 發現的 **critical** 和 **major** findings：

1. 逐項評估是否可以安全修正
2. **可安全修正的**（如 Router 多餘的 try/except、未用 createBFFResponse）→ 直接修正
3. **需要判斷的**（如架構變更、邏輯重構）→ 列入報告，不自動修正
4. 修正後重新執行 Preflight

**修正時必須遵守 worker-prompt.md 的架構規範。**

### 3d. 文件同步（/harness-docs 維度）

按照 `/harness-docs` 的 6 個 Check 維度掃描，文件同步問題的 severity 歸類：
- 已刪除的元件/功能仍在文件中 → **major**
- 程式碼範例已過時（pattern 不符） → **major**
- 新增的元件/功能未在文件中 → **minor**

### 3e. 最終 Preflight

所有修正完成後，執行最終 Preflight 確認全部通過。

---

## 輸出報告

### 唯讀模式報告

```
## 品質審查報告

審查範圍：{backend / frontend / 全專案}
審查時間：{timestamp}

### 統計
- critical: N 件
- major: N 件
- minor: N 件
- recommendation: N 件

### Findings

#### Critical
1. [三層架構] backend/app/routers/xxx.py:42
   問題：Router 中使用 try/except
   建議：移除 try/except，讓 Service 拋 AppError 由 exception_handler 處理

#### Major
（逐項列出）

#### Minor
（逐項列出）

#### Recommendation（/simplify 可處理）
（逐項列出）

### 結論
{一段文字總結整體品質狀況，是否有需要立即修正的問題}
```

### --deep 模式額外區塊

```
### Tool Gate
- svelte-check: {0 errors ✓ | N errors ✗}
  {列出每個 error：file:line — 錯誤訊息}
- ruff check: {pass ✓ | N errors ✗}

### WS 事件契約
- 後端事件類型數：N 種
- 前端型別涵蓋：N/N

#### 契約不同步（如有）
| 事件 type | 欄位 | 後端位置 | 狀態 | severity |
|-----------|-------|----------|------|----------|
| user_left | removed | room_service.py:499 | 前端缺失 | major |

### any 滲透
| 風險層級 | 數量 | 代表案例 |
|----------|------|----------|
| 高（WS handler） | N 處 | roomHandlers.ts:102 handleUserStatusChanged(data: any) |
| 中（BFF/API） | N 處 | bff-client.ts:43 const config: any |
| 低（元件/工具） | N 處 | +page.svelte:49 messageInputComponent: any |
```

### --fix 模式額外區塊

```
### Preflight 結果
- lint: pass ✓
- test: pass ✓（N 個測試通過）
- typecheck: pass ✓

### 已自動修正
1. [簡潔性] backend/app/services/xxx.py:30
   問題：未使用的 import
   修正：已移除

### 需手動處理
1. [效能] backend/app/services/xxx.py:85
   問題：N+1 查詢
   建議：改用 $in 批次查詢

### /simplify 修正摘要
- 移除 N 個未使用的 import
- 簡化 N 處表達式

### 文件同步結果（Docs Sync）
- README.md 專案結構：{結果} ✓/✗
- C4 元件圖：{結果} ✓/✗
- DI 工廠函數：{結果} ✓/✗
```

---

## Commit 處理（僅 `--fix` 模式）

**有修正時：**
1. 詢問使用者：「審查修正了 N 個問題，是否要提交？」
2. 使用者同意 → 使用 `/commit-fast` 提交
3. 使用者拒絕 → 不提交，修正保留在工作區

**沒有修正（全部通過）：** 不提交，直接輸出報告。

---

## 重要約束

1. **唯讀模式不修改任何檔案** — 沒有 `--fix` 不修改、不 commit
2. **唯讀模式不執行測試** — 靜態審查不跑 pytest / npm run check（`--deep` 的 svelte-check 除外）
3. **對照 reviewer-prompt.md 的 checklist** — 不遺漏檢查維度
4. **繁體中文輸出**
5. **只報告實際發現的問題** — 沒問題的維度不需要列出
6. 如果全部通過，輸出：「審查完成，未發現 critical 或 major 問題。」
7. **`--fix` 修正範圍僅限發現的問題** — 不做額外的重構或功能改進
8. **`--fix` 修正時遵守 worker-prompt.md 架構規範**
9. **不確定能否安全修正的問題，列入「需手動處理」而非強行修正**
10. **`--fix` commit 前必須詢問使用者確認**
