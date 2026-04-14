# /harness-e2e — 瀏覽器端對端驗證

## 你的角色

你是 **E2E 測試員**，透過 Chrome DevTools MCP 操作真實瀏覽器，驗證功能的完整流程。

---

## 前置條件

執行前確認以下服務已啟動：

1. **基礎設施**：`docker-compose up -d`（MongoDB + Redis）
2. **後端**：`cd backend && fastapi dev app/main.py`（port 8000）
3. **前端**：`cd frontend && npm run dev`（port 5173）

如果服務未啟動，提醒使用者：「請先啟動 dev server，E2E 測試需要完整的執行環境。」

---

## 啟動流程

### Step 1：判定測試範圍

根據使用者參數選擇測試套件：

| 參數 | 測試範圍 |
|------|---------|
| 無參數 | 執行全部測試套件 |
| `auth` | 只測認證流程 |
| `chat` | 只測即時聊天（WebSocket） |
| `room` | 只測房間管理 |
| `file` | 只測檔案上傳/下載 |
| `notification` | 只測通知系統 |
| 指定功能描述 | 根據描述判斷測試內容 |

### Step 2：環境健康檢查

測試開始前先驗證環境：

1. `navigate_page` 到 `http://localhost:5173` → 確認前端可達
2. `evaluate_script` 呼叫 `fetch('/api/auth/me')` → 確認 BFF 可達
3. `list_console_messages({ types: ["error"] })` → 確認無啟動錯誤

如果環境不健康，停止並報告問題。

---

## 測試套件

### Suite 1：認證流程（Auth）

```
Step 1: navigate_page → 登入頁面
Step 2: take_snapshot → 取得表單元素 uid
Step 3: fill_form → 填入測試帳號密碼
Step 4: click → 登入按鈕
Step 5: wait_for → 等待進入首頁/dashboard
Step 6: take_screenshot → 截圖驗證登入成功
Step 7: list_console_messages({ types: ["error"] }) → 無 error
```

**驗證項目：**
- [ ] 登入成功後導向正確頁面
- [ ] 無 console error
- [ ] Cookie 已設定（透過 evaluate_script 確認 fetch 帶 credentials 正常）

---

### Suite 2：即時聊天（Chat）— WebSocket 核心測試

這是最重要的測試套件，需要**兩個獨立使用者**。

```
=== 準備：建立兩個隔離的 browser context ===

Tab 1 (User A):
  new_page({ url: "http://localhost:5173", isolatedContext: "user-a" })
  → 註冊/登入 User A

Tab 2 (User B):
  new_page({ url: "http://localhost:5173", isolatedContext: "user-b" })
  → 註冊/登入 User B

=== 測試 1：建立房間 + 加入 ===

Tab 1: User A 建立房間 "test-room"
Tab 1: 取得房間的 invite code 或直接進入房間
Tab 2: User B 加入 "test-room"

=== 測試 2：驗證 WebSocket 連線 ===

⚠️ BFF ticket 機制下 list_network_requests 找不到 WS，改用間接驗證：

Tab 1:
  select_page → 切換到 Tab 1
  take_snapshot → 確認頁面顯示「N 人在線」（N >= 1）
  → 在線狀態即時更新 = WS 連線正常

Tab 2:
  select_page → 切換到 Tab 2
  take_snapshot → 確認「N 人在線」且雙方都出現在成員列表

=== 測試 3：即時訊息傳遞（核心） ===

⚠️ 訊息輸入框是 div > textarea，必須用 evaluate_script（見「已知 UI 互動模式」）

Tab 1:
  select_page → 切換到 Tab 1
  evaluate_script → 找到 textarea.message-textarea，設值 "e2e-test-hello"
  press_key Enter → 送出訊息
  wait_for({ text: ["e2e-test-hello"] }) → 確認自己畫面有顯示

Tab 2:
  select_page → 切換到 Tab 2
  wait_for({ text: ["e2e-test-hello"], timeout: 5000 })
  → 訊息是否即時出現？
  take_screenshot → 截圖留證

=== 測試 4：反向訊息 ===

Tab 2: 用同樣的 evaluate_script 方式發送 "e2e-test-reply"
Tab 1: wait_for({ text: ["e2e-test-reply"] }) → 驗證 User A 收到

=== 測試 5：切換房間（WS 斷舊連新） ===

前置：User A 再建立第二個房間 "e2e-room-2"

Tab 1 (User A):
  → 目前在 "e2e-room-1"
  → 點擊 "e2e-room-2" 切換房間
  → wait_for → 等待 "e2e-room-2" 的聊天介面載入
  → 確認 URL 已變更（room_id 不同）= WS 已重連到新房間

Tab 2 (User B):
  → 確認 User A 離開 "e2e-room-1" 後，成員列表 / 在線狀態正確更新

Tab 1:
  → 在 "e2e-room-2" 發送 "e2e-test-room2-msg"
  → 確認訊息出現在 "e2e-room-2" 而非 "e2e-room-1"

=== 測試 6：退出房間（成員數即時更新） ===

前置：User A 和 User B 都在 "e2e-room-1"

Tab 1 (User A):
  → take_snapshot → 記錄目前房間的成員數量
  → 確認成員列表包含 User A 和 User B

Tab 2 (User B):
  → 點擊「更多選項」→「離開聊天室」
  → ⚠️ 立即呼叫 handle_dialog({ action: "accept" })（會觸發 window.confirm）
  → wait_for → 等待導向其他房間或房間列表
  → 確認 User B 已離開

Tab 1 (User A):
  → wait_for → 等待成員列表更新（或系統通知 "User B 離開了"）
  → take_snapshot → 確認成員列表不再包含 User B
  → 驗證成員數量 = 原本 - 1
  → take_screenshot → 截圖留證

=== 測試 7：重新加入房間（成員數恢復） ===

Tab 2 (User B):
  → 重新加入 "e2e-room-1"
  → 進入房間

Tab 1 (User A):
  → wait_for → 等待成員列表更新（或系統通知 "User B 加入了"）
  → take_snapshot → 確認成員列表包含 User B
  → 驗證成員數量 = 恢復原本數量

=== 測試 8：Console 錯誤檢查 ===

Tab 1: list_console_messages({ types: ["error"] }) → 應為空
Tab 2: list_console_messages({ types: ["error"] }) → 應為空
```

**驗證項目：**
- [ ] 兩個使用者都能建立 WebSocket 連線
- [ ] User A 發送的訊息 User B 即時收到
- [ ] User B 發送的訊息 User A 即時收到
- [ ] 切換房間時舊 WS 關閉、新 WS 建立
- [ ] 切換房間後訊息只出現在當前房間
- [ ] 退出房間後成員列表即時更新（其他人看到的）
- [ ] 退出房間後成員數量正確減少
- [ ] 重新加入後成員列表和數量恢復
- [ ] 無 console error
- [ ] 訊息內容正確顯示（未被截斷或亂碼）

---

### Suite 3：房間管理（Room）

```
=== 測試 1：建立房間 + 設定修改 ===

Tab 1 (User A):
  → 建立新房間（填名稱、選類型）
  → 確認房間出現在列表中
  → 進入房間設定
  → 修改房間名稱
  → 確認名稱更新

Tab 2 (User B):
  → 確認房間列表中的房間名稱也已更新（如果 User B 也在該房間）
  
Tab 1 (User A):
  → 離開房間（或刪除房間）

Tab 2 (User B):
  → 確認房間從列表中消失（如果被刪除）或成員數更新

=== 測試 2：探索 ↔ 已加入 列表顯示邏輯 ===

目標：驗證兩個 tab 的列表內容互斥且正確反映加入狀態。

前置：
  Tab 1 (User A): 已登入
  Tab 2 (User B): 已登入，建立一個公開房間 "e2e-explore-room"
  → User A 尚未加入 "e2e-explore-room"

Step 1：已加入 tab — 確認不含未加入的房間
  Tab 1 (User A):
    → 進入 /app/rooms
    → take_snapshot → 確認預設在「已加入」tab（按鈕有 tab-active）
    → 確認列表中**不包含** "e2e-explore-room"

Step 2：探索 tab — 確認包含未加入的房間
  Tab 1 (User A):
    → click「探索」tab 按鈕
    → wait_for → 等待列表內容更新
    → take_snapshot → 確認「探索」按鈕變成 tab-active
    → 確認列表中**包含** "e2e-explore-room"

Step 3：從探索列表加入房間
  Tab 1 (User A):
    → 在探索列表中找到 "e2e-explore-room"，點擊加入
    → wait_for → 等待加入成功（進入房間或顯示成功提示）

Step 4：加入後 — 探索 tab 不再顯示該房間
  Tab 1 (User A):
    → 回到 /app/rooms
    → click「探索」tab
    → wait_for → 等待列表載入
    → 確認 "e2e-explore-room" **不再出現**在探索列表

Step 5：加入後 — 已加入 tab 顯示該房間
  Tab 1 (User A):
    → click「已加入」tab
    → wait_for → 等待列表載入
    → 確認 "e2e-explore-room" **出現**在已加入列表
    → take_screenshot → 截圖留證

Step 6：退出後 — 房間回到探索列表
  Tab 1 (User A):
    → 進入 "e2e-explore-room"，點擊離開房間
    → handle_dialog({ action: "accept" })
    → 回到 /app/rooms
    → click「已加入」tab
    → 確認 "e2e-explore-room" **不在**已加入列表
    → click「探索」tab
    → 確認 "e2e-explore-room" **重新出現**在探索列表
    → take_screenshot → 截圖留證
```

**驗證項目：**
- [ ] 建立房間成功
- [ ] 房間列表正確顯示
- [ ] 房間設定可修改
- [ ] 修改後其他成員看到的資訊也同步更新
- [ ] 離開/刪除房間後列表更新
- [ ] 刪除房間後其他成員的列表也同步更新
- [ ] 「已加入」tab 只顯示已加入的房間
- [ ] 「探索」tab 只顯示未加入的房間
- [ ] 從探索加入後，房間從探索消失、出現在已加入
- [ ] 退出房間後，房間從已加入消失、回到探索

---

### Suite 4：檔案上傳（File）

```
Tab 1:
  → 進入聊天室
  → take_snapshot → 找到檔案上傳按鈕 uid
  → upload_file({ uid: "...", filePath: "上傳測試檔案路徑" })
  → wait_for → 等待上傳完成提示
  → take_screenshot → 確認檔案訊息顯示
```

**驗證項目：**
- [ ] 檔案上傳成功
- [ ] 檔案訊息在聊天中正確顯示
- [ ] 檔案可點擊下載

---

### Suite 5：通知系統（Notification）

```
Tab 1 (User A): 在房間中
Tab 2 (User B): 在房間中發送訊息

Tab 1:
  → 離開房間回到列表
  → 確認有未讀通知標記
  → 點擊通知
  → 確認通知已讀
```

**驗證項目：**
- [ ] 收到通知
- [ ] 未讀標記正確
- [ ] 點擊後標記為已讀

---

## 進階驗證（可選）

根據情境判斷是否需要執行：

### Lighthouse 審計

```
lighthouse_audit({ device: "desktop", mode: "navigation" })
→ 檢查 accessibility、SEO、best practices 分數
```

### 效能追蹤

```
performance_start_trace({ reload: true })
→ 等待頁面載入完成
performance_stop_trace()
→ 分析 LCP、INP、CLS
```

### 離線模式

```
emulate({ networkConditions: "Offline" })
→ 嘗試發送訊息
→ 確認 UI 有適當的錯誤提示
emulate({})  → 恢復網路
```

---

## 測試資料管理

### 測試帳號命名規則

使用明確的測試帳號，避免污染真實資料。**用戶名上限 20 字元**，使用底線（`_`）而非連字號（`-`）：

- User A：`e2e_a_{timestamp}` / 密碼：`E2eTestPass123!` / 信箱：`e2e_a_{timestamp}@test.com`
- User B：`e2e_b_{timestamp}` / 密碼：`E2eTestPass123!` / 信箱：`e2e_b_{timestamp}@test.com`
- 房間名：`e2e-room-{timestamp}`（房間名無長度限制，可用連字號）
- 訊息前綴：`e2e-test-`

### 清理

測試完成後：
- 不主動清理測試資料（避免誤刪）
- 在報告中列出建立的測試資料，讓使用者決定是否清理

---

## 輸出報告

```
## E2E 測試報告

測試時間：{timestamp}
測試範圍：{全部 / auth / chat / ...}
環境：localhost:5173 → localhost:8000

### 結果總覽
- 通過：N / M
- 失敗：N / M

### 詳細結果

#### ✓ Suite 1：認證流程
- [x] 登入成功後導向正確頁面
- [x] 無 console error

#### ✓ Suite 2：即時聊天
- [x] WebSocket 連線建立
- [x] User A → User B 即時送達
- [x] User B → User A 即時送達
- [x] 無 console error

#### ✗ Suite 4：檔案上傳
- [x] 檔案上傳成功
- [ ] 檔案訊息顯示 ← 失敗：上傳後訊息未出現
  截圖：{screenshot 路徑}

### Console 錯誤（如有）
- Tab 1: （無）
- Tab 2: TypeError: Cannot read property 'x' of undefined (chat.svelte:142)

### 截圖
- 登入成功：/tmp/e2e-login.png
- 聊天驗證：/tmp/e2e-chat.png
- 失敗畫面：/tmp/e2e-file-fail.png

### 建立的測試資料
- 帳號：e2e-user-a-1712836800, e2e-user-b-1712836800
- 房間：e2e-room-1712836800
```

---

## 與其他 Harness 指令的整合

`/harness-e2e` 是獨立指令，但其他指令可以在適當時機建議執行：

### `/harness-work` 完成任務後

當 Worker 完成的任務涉及以下範圍時，Lead 應在 commit 前建議執行 E2E：

- **WebSocket 相關**：訊息收發、連線管理、房間事件
- **認證相關**：登入、登出、token refresh
- **BFF Route 變更**：新增或修改 `/routes/api/` 下的檔案
- **前端元件變更**：聊天介面、房間列表、通知 UI

建議格式：「此任務涉及 {範圍}，建議執行 `/harness-e2e {suite}` 驗證全流程。」

**注意：這是建議，不是強制。** Lead 根據變更的影響範圍自行判斷是否建議。

### `/harness-review --fix` 驗證時

`/harness-review --fix` 專注於靜態分析和程式碼品質，不包含 E2E。
但如果修正了 BFF 或 WebSocket 相關的問題，可以在報告最後建議：
「修正了 BFF/WebSocket 相關問題，建議執行 `/harness-e2e` 確認功能正常。」

---

## 已知 UI 互動模式（必讀）

以下是經實測驗證的互動模式，**跳過偵查直接套用**可省下大量操作輪次：

### 1. 發送訊息（聊天輸入框）

訊息輸入區域是 `<div role="textbox">` 包著 `<textarea class="message-textarea">`。
`fill()` 對此元素**無效**，必須用以下流程：

```javascript
// Step 1: evaluate_script 設值
() => {
  const textarea = document.querySelector('textarea.message-textarea');
  textarea.focus();
  const setter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, 'value'
  ).set;
  setter.call(textarea, '你的訊息內容');
  textarea.dispatchEvent(new Event('input', { bubbles: true }));
  return { success: true };
}

// Step 2: press_key Enter 送出
```

### 2. 離開 / 刪除房間（confirm 對話框）

「離開聊天室」和「刪除聊天室」都會觸發 `window.confirm()`，**阻塞所有 DevTools 操作**。
用 `evaluate_script` 點擊按鈕（`click(uid)` 會 timeout），然後 `evaluate_script` 本身也會因 `confirm()` 而 timeout，
但 dialog 已經觸發，**直接呼叫 `handle_dialog`** 即可解除阻塞：

```javascript
// Step 1: evaluate_script 點擊（會 timeout，這是正常的）
evaluate_script(() => {
  const btn = Array.from(document.querySelectorAll('button'))
    .find(b => b.textContent.trim() === '離開聊天室');
  if (btn) btn.click();
})
// → 預期會 timeout（因為 confirm() 阻塞了 JS）

// Step 2: 立即呼叫（不管 Step 1 是否 timeout）
handle_dialog({ action: "accept" })
```

### 3. 檔案上傳

`upload_file` 工具對此應用的 file input **不可靠**（檔案不會被保留）。
改用 **DataTransfer API** 直接在瀏覽器端建立檔案並觸發上傳：

⚠️ **必須分成兩個獨立的 evaluate_script 呼叫**，不可合併。第一步讓面板完全 render，第二步再注入檔案。

```javascript
// Step 1: 第一個 evaluate_script — 開啟上傳面板
() => {
  const btn = document.querySelector('button[aria-label="上傳檔案"]');
  if (btn) btn.click();
  return { clicked: !!btn };
}

// Step 2: 第二個 evaluate_script — 用 DataTransfer API 注入檔案
() => {
  const panel = document.querySelector('.file-upload-panel');
  const fileInput = (panel?.querySelector('input[type="file"]')) ||
                    document.querySelector('input[type="file"]');
  if (!fileInput) return { error: 'file input not found' };
  const dt = new DataTransfer();
  const file = new File(['檔案內容'], 'test.txt', { type: 'text/plain' });
  dt.items.add(file);
  Object.defineProperty(fileInput, 'files', { value: dt.files, configurable: true });
  fileInput.dispatchEvent(new Event('change', { bubbles: true }));
  return { success: true };
}
// → 面板自動關閉，檔案訊息出現在聊天中，不需要另外點「發送」
```

### 4. WebSocket 連線驗證

BFF ticket 機制下 `list_network_requests({ resourceTypes: ["websocket"] })` **找不到 WS**。
改用**間接驗證**：檢查頁面上的「N 人在線」文字是否正確反映連線狀態。

### 5. 表單填寫

登入/註冊頁面的標準 `<input>` 和 `<textarea>` 可正常使用 `fill()` / `fill_form()`。
只有聊天訊息框需要特殊處理（見上方第 1 點）。

### 6. 導航到房間

`/app/rooms` 列表頁**經常**卡在「正在載入聊天室...」（非偶爾）。**永遠不要**依賴 `/app/rooms` 獨立頁面。
正確做法：直接 `navigate_page` 到具體房間 URL，側邊欄會自動載入房間列表和 tab：

```
navigate_page({ url: "http://localhost:5173/app/room/{room_id}", type: "url" })
```

### 7. click(uid) 經常失敗的元素（通用 fallback 模式）

以下元素用 `click(uid)` 經常 timeout，**一律用 `evaluate_script` 點擊**：

- **側邊欄房間按鈕**：`buttons.find(b => b.textContent.includes('房間名'))`
- **「更多選項」按鈕**：`document.querySelector('button[aria-label="更多選項"]')`
- **下拉選單項目**（聊天室設定、成員列表、離開聊天室）：`buttons.find(b => b.textContent.trim() === '項目名')`
- **通知按鈕**：`document.querySelector('button[aria-label*="通知"]')`
- **上傳按鈕**：`document.querySelector('button[aria-label="上傳檔案"]')`
- **「滾動到底部」按鈕**：同上模式

**規則：只有登入/註冊表單、建立房間對話框的按鈕（如「創建」「取消」）可用 `click(uid)`。其餘一律用 `evaluate_script`。**

### 8. Modal 對話框內的 input 元素

房間設定等 modal 內的 `<input>` 元素，`fill(uid)` **經常 timeout**。
改用 `evaluate_script` + id 或 placeholder 選擇器：

```javascript
// 建立/修改房間名稱：優先用 id（更快更穩定）
() => {
  const input = document.querySelector('#room-name');  // ← 優先用這個
  if (!input) return { found: false };
  input.focus();
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(input, '新名稱');
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  return { success: true };
}

// 其他 modal input：用 placeholder fallback
() => {
  const input = document.querySelector('input[placeholder="請輸入房間名稱"]');
  input.focus();
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(input, '新名稱');
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
  return { success: true };
}
```

### 9. 註冊後行為

註冊成功後**不會自動登入**，會重導至 `/login`。需要再填一次登入表單。

### 10. isolatedContext 不保證乾淨 session

`new_page({ isolatedContext: "user-a" })` 若前次測試留有 cookie，session 會殘留。
**開啟新分頁後，一律先呼叫 logout 再導航到 `/register`：**

```javascript
// 先 logout
await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
// 再導航到 register
navigate_page({ url: "http://localhost:5173/register", type: "url" })
```

### 11. 房間設定儲存後 dialog 不自動關閉

點擊「儲存設定」後，房間設定 dialog **仍留在 DOM**（顯示「房間設定已更新」）。
若接著開啟其他 dialog（例如「創建聊天室」），兩個 dialog 會共存，導致 uid 或按鈕定位錯誤。

**儲存後一定要顯式關閉：**

```javascript
() => {
  const btns = Array.from(document.querySelectorAll('button'));
  const cancel = btns.find(b => b.textContent.trim() === '取消');
  if (cancel) cancel.click();
}
```

### 12. 多 dialog 共存時，用 input value 定位目標 dialog

當有舊 dialog ghost 殘留時，不能直接找第一個「創建」button，
要先透過 input value 找到正確的 dialog，再找其中的按鈕：

```javascript
() => {
  const allDialogs = document.querySelectorAll('[role="dialog"], dialog');
  for (const d of allDialogs) {
    const inp = d.querySelector('input');
    if (inp && inp.value === '目標房間名稱') {
      const btn = Array.from(d.querySelectorAll('button'))
        .find(b => b.textContent.trim() === '創建');
      if (btn) { btn.click(); return { clicked: true }; }
    }
  }
  return { clicked: false };
}
```

---

## 重要約束

1. **不修改程式碼** — E2E 只驗證，不修正
2. **不自動 commit** — 純測試，無程式碼變更
3. **環境問題不算測試失敗** — 分清是 bug 還是環境問題
4. **測試訊息用 `e2e-test-` 前綴** — 方便辨識和清理
5. **每次切換 tab 都用 `select_page`** — 確保操作目標正確
6. **截圖留證** — 關鍵步驟和失敗畫面都要截圖
7. **檢查 console error** — 每個 suite 結束都要檢查
