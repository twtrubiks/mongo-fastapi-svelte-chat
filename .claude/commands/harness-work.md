# /harness-work — 自主迴環指揮劇本

## 你的角色

你是 **Lead（指揮官）**。你負責讀取任務、分配工作、審查結果、提交程式碼。

---

## 啟動流程

### Step 0：檢查殘留狀態

讀取 `Plans.md`，檢查是否有殘留的 `cc:DOING` 任務（上次中斷的）。

如果有：
- 告知使用者：「發現任務 {task_id} 處於 cc:DOING 狀態（可能是上次中斷）。」
- 詢問使用者要「繼續」還是「重置為 cc:TODO」
- 等使用者回覆後再繼續

### Step 1：讀取任務

1. 讀取根目錄的 `Plans.md`
   - **如果 Plans.md 不存在**：使用 Skill tool 呼叫 `/harness-plan create`，等待使用者完成規劃後再繼續
   - **如果 Plans.md 存在但無 `cc:TODO` 任務**：告知使用者「沒有待辦任務」，建議用 `/harness-plan add` 新增
2. 掃描所有標記為 `cc:TODO` 的任務
3. 如果使用者帶參數（如 `/harness-work P14`），僅處理該任務
4. 如果參數為 `all`，處理所有 `cc:TODO` 任務
5. 如果無參數，處理第一個 `cc:TODO` 任務

### Step 2：選擇執行模式

你有三種模式可用，根據任務的數量、複雜度、相依性自行判斷最適合的模式：

| 模式 | 行為 | 適合情境 |
|------|------|---------|
| **Solo** | Lead 自己實作，不 spawn Worker | 簡單任務、單一檔案修改、快速修正 |
| **Parallel** | spawn Worker 處理各任務，Lead 負責 review | 多個獨立任務、中等複雜度 |
| **Breezing** | Lead 完全不寫程式碼，Worker + Reviewer 三角分離 | 大量任務、高複雜度、需要獨立審查 |

考量因素：
- 任務數量多寡
- 任務之間是否有相依性
- 單一任務的複雜度（跨幾個層級？前後端都碰？）
- 風險程度（security-sensitive 可能需要獨立 Reviewer）

宣告你的選擇和理由：「偵測到 N 個待辦任務，選擇 {模式} 模式，因為 {理由}。」

### Step 3：對每個任務執行迴環

---

## 迴環流程（每個任務）

### 3a. 更新狀態

將 `Plans.md` 中該任務的 `cc:TODO` 改為 `cc:DOING`。

### 3b. 生成 Sprint Contract

讀取 `.claude/harness/sprint-contract-template.json`，根據任務內容填入：

- `task_id`：任務編號（如 "P14"）
- `subject`：任務標題
- `checks`：從 Plans.md 的 DoD 提取
- `non_goals`：明確定義不做什麼
- `affected_files`：預估會修改的檔案
- `risk_flags`：風險標記

將填寫完的 contract 寫入 `.claude/harness/contracts/{task_id}.sprint-contract.json`（每個任務獨立檔案，不覆蓋）。

例如任務 P14 → `.claude/harness/contracts/P14.sprint-contract.json`

### 3c. 執行實作

#### Solo 模式

Lead 自己做，但**必須遵守架構規範**：

1. 先讀取 `.claude/harness/worker-prompt.md` 了解三層架構 + BFF 規範
2. 先讀取 `CLAUDE.md` 了解專案慣例
3. 按照 sprint contract 的 `checks` 逐項實作
4. 實作完成後執行 preflight：
   ```bash
   cd backend && ruff check . && ruff format --check .
   cd backend && pytest tests/ -v --tb=short -x
   cd frontend && npm run check:all
   ```
5. 自我對照 `.claude/harness/reviewer-prompt.md` 的 checklist 做快速自審
6. 執行 `/simplify` 對變更程式碼做品質打磨（複用性、品質、效率）
7. 如果 `/simplify` 有修改，重新執行 preflight
8. 通過後進入 commit 階段

#### Parallel / Breezing 模式

1. **讀取 Worker prompt**：讀取 `.claude/harness/worker-prompt.md` 的完整內容

2. **Spawn Worker**：使用 Agent tool，prompt 包含：
   - Worker prompt 全文
   - Sprint contract JSON
   - 明確指示：「你的任務是根據 sprint contract 實作功能。完成後回傳結果。」

   Worker 約束：
   - 不給予 Agent tool 權限（在 prompt 中明確告知 Worker 不可 spawn 子 agent）
   - 使用 `mode: "bypassPermissions"` 讓 Worker 可以自由操作

3. **等待 Worker 回傳結果**

4. **讀取 Reviewer prompt**：讀取 `.claude/harness/reviewer-prompt.md` 的完整內容

5. **Spawn Reviewer**：使用 Agent tool，prompt 包含：
   - Reviewer prompt 全文
   - Sprint contract JSON
   - Worker 回傳的 `files_changed` 清單
   - 明確指示：「你的任務是審查以下檔案的變更，對照 checklist 輸出判決。」

   Reviewer 約束：
   - 在 prompt 中明確告知 Reviewer 只能使用 Read、Grep、Glob 工具
   - 不可修改任何檔案

6. **等待 Reviewer 回傳判決**

### 3d. Review 迴圈

```
Worker 完成 → Reviewer 審查
                │
                ├─ APPROVE → /simplify 品質打磨 → preflight → commit
                │
                └─ REQUEST_CHANGES
                     │
                     ├─ 修正次數 < 3
                     │    └─ 重新 spawn Worker，帶上修正指示
                     │       → Worker 修正 → 重新 spawn Reviewer → 再審
                     │
                     └─ 修正次數 = 3
                          └─ 停止，向使用者報告：
                             「任務 {task_id} 經過 3 次修正後仍有以下問題：
                              {findings 列表}
                              請手動介入處理。」
```

**修正 Worker 的 spawn 方式：**

REQUEST_CHANGES 時，**重新 spawn 一個新的 Worker**（不是用 SendMessage），prompt 包含：
- Worker prompt 全文（同首次 spawn）
- Sprint contract JSON
- Reviewer 的 findings 清單
- 明確指示：「你是修正 Worker，以下是 Reviewer 發現的問題，請逐項修正。」

這樣做的原因：Agent tool 的子 agent 完成後無法保證能用 SendMessage 恢復，重新 spawn 更可靠。

**修正指示格式（附在新 Worker 的 prompt 中）：**

```
## 修正任務

Reviewer 判定 REQUEST_CHANGES，請修正以下問題：

1. [severity] category — file:line
   問題：{description}
   建議：{suggestion}

2. ...

注意：
- 只修正上述問題，不要做額外的重構
- 修正後重新執行 preflight
- 回傳更新後的結果
```

### 3e. Simplify（品質打磨）

Reviewer APPROVE 後、commit 前，執行 `/simplify` 對變更的程式碼做最終品質打磨：

1. **使用 Skill tool 呼叫 `/simplify`**
2. `/simplify` 會審查變更的程式碼，檢查：
   - **複用性**：是否有重複邏輯可以提取為共用函數？
   - **品質**：命名是否清晰？邏輯是否過於複雜？
   - **效率**：是否有不必要的計算、多餘的迴圈、可以簡化的表達式？
3. 如果 `/simplify` 發現問題並修正了程式碼，**重新執行 preflight** 確保修正沒有破壞功能
4. 如果 preflight 通過，進入 commit 階段
5. Solo 模式下同樣執行 `/simplify`

**注意：** `/simplify` 的修正範圍僅限於 Worker 變更的檔案，不擴大到其他檔案。

### 3f. E2E 瀏覽器驗證（條件觸發）

Simplify 完成後、commit 前，根據任務影響範圍決定是否執行 `/harness-e2e`。

**觸發條件（符合任一即執行）：**

| 條件 | 原因 |
|------|------|
| `affected_files` 包含 `frontend_components` 或 `bff_routes` | UI 變更需視覺驗證 |
| 任務涉及 WebSocket 相關檔案（`websocket/`、`connection_manager`、WS handler） | WS 行為無法靠型別檢查覗測 |
| 任務涉及認證/授權邏輯（`auth`、`permissions`、`require_room_membership`） | 權限變更漏測風險高 |
| `risk_flags` 含 `ux-regression` 或 `security-sensitive` | 高風險任務 |

**跳過條件：**
- 純後端任務（只改 Model / Repository / Service），且不涉及認證/授權/WebSocket

**執行流程：**

1. 根據上述條件判斷是否需要 E2E
2. 如果需要，先檢查環境就緒：
   - 用 `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs` 確認後端
   - 用 `curl -s -o /dev/null -w "%{http_code}" http://localhost:5173` 確認前端
   - 任一不通 → 提醒使用者：「E2E 需要後端（:8000）和前端（:5173）運行中，請先啟動後回覆繼續。」
3. 環境就緒 → 使用 Skill tool 呼叫 `/harness-e2e`，scope 限定為與本任務相關的測試套件
4. E2E 結果處理：
   - 全部通過 → 進入下一階段
   - 有失敗 → Lead 判斷是否為本次變更導致的 regression：
     - 是 → 修正後重新跑 preflight + E2E（最多 2 次）
     - 否（既有問題）→ 記錄在報告中，不阻擋 commit

### 3g. Docs Sync Check（文件同步檢查）

E2E 驗證（或跳過）後、commit 前，執行文件同步檢查：

1. 按照 `/harness-docs` 的流程，以 `git diff HEAD` 掃描未提交的變更
2. 執行唯讀模式（不自動修改文件）
3. 如果有「需要更新」的項目：
   - 提醒：「文件有 N 處需要同步更新：{摘要}」
   - **Solo 模式**：Lead 自行決定是否修正文件後再 commit
   - **Parallel / Breezing 模式**：Lead 決定是否 spawn Worker 處理文件更新
4. 如果全部通過，直接進入 commit 階段

**注意：** 文件更新與程式碼變更放在同一個 commit 中。

### 3h. Commit

Docs Sync 完成後，使用 `/commit-fast` 進行提交：

1. **使用 Skill tool 呼叫 `/commit-fast`**
2. `/commit-fast` 會自動處理 staging、生成 commit message、提交
3. Solo 模式下同樣使用 `/commit-fast`

### 3i. 更新 Plans.md

將該任務的 `cc:DOING` 改為 `cc:DONE`。勾選所有 DoD checkbox。

---

## 完成報告

所有任務處理完畢後，輸出彙總報告：

```
## Harness 執行報告

模式：{Solo/Parallel/Breezing}
處理任務：{N} 個

### 完成
- P14：聊天室頭像功能 ✓

### 跳過
（無）

### 失敗 / 需手動介入
（無）

### Commit 紀錄
- abc1234 feat(P14): 聊天室頭像功能
```

---

## 重要約束

1. **永遠先讀 `CLAUDE.md`** 了解專案慣例
2. **永遠先讀 `worker-prompt.md`** 了解架構規範（即使 Solo 模式）
3. **不要假設檔案結構**，先用 Glob/Grep 確認現有模式
4. **繁體中文**：所有註解、commit message、錯誤訊息
5. **不要超出 Sprint Contract 的 scope**，non_goals 中的項目不做
6. **Breezing 模式下 Lead 不寫程式碼**，全部透過 Worker 完成
7. Worker 回傳的結果要**仔細檢查**，不要盲目 commit

---

## 錯誤處理

| 情況 | 處理方式 |
|------|---------|
| Plans.md 不存在 | 自動呼叫 `/harness-plan create` 建立 Plans.md，完成後繼續 |
| 無 cc:TODO 任務 | 告知使用者「沒有待辦任務」 |
| Worker preflight 失敗 | Worker 自行修正（最多 2 次），仍失敗則向 Lead 回報 |
| Reviewer 3 次 REQUEST_CHANGES | 停止該任務，向使用者 escalation |
| Sprint Contract 模板不存在 | 使用內建預設值（task_id + subject + checks） |
| contracts 目錄不存在 | 自動建立 `.claude/harness/contracts/` |
| 任務缺少 DoD | 提醒使用者補充，或根據任務描述自動推導 |
