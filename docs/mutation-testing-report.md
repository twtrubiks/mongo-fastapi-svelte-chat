# 後端變異測試報告

> 對象：`backend/app`（約 9.3k 行）　工具：[`backend/scripts/mutation_test.py`](../backend/scripts/mutation_test.py)
> 第一輪（修正前）：2026-10-23，commit `2813ef5`　明細：[mutation-testing-survivors.md](mutation-testing-survivors.md)
> 第二輪（修正後）：2026-10-23，commit `0bd7335`　明細：[mutation-testing-survivors-round2.md](mutation-testing-survivors-round2.md)
> 第三輪（處理低價值存活者後）：2026-10-23，commit `ef46e1c`　明細：[mutation-testing-survivors-round3.md](mutation-testing-survivors-round3.md)
> 第四輪（WebSocket 連線層與私人房邀請制）：2026-10-24，commit `752c407`　明細：[mutation-testing-survivors-round4.md](mutation-testing-survivors-round4.md)
> 第五輪（通知）：2026-10-24，commit `2516f17`　明細：[mutation-testing-survivors-round5.md](mutation-testing-survivors-round5.md)
> 第六輪（訊息、房間事件與零星中風險）：2026-10-24，commit `cb213e0`　明細：[mutation-testing-survivors-round6.md](mutation-testing-survivors-round6.md)

變異測試（mutation testing）會刻意把程式碼改壞一點點（`==` 改 `!=`、刪掉一行呼叫、把 `"token_version"` 改成別的欄位名……），再跑測試。測試失敗代表這個「變異體」被**殺死（killed）**；測試仍然全綠代表它**存活（survived）**——也就是說，這段邏輯就算真的寫錯，現有測試也不會發現。行覆蓋率只回答「這行有沒有被執行」，變異測試回答的是「這行如果錯了，測試會不會叫」。

本報告只涵蓋後端。前端測試見 [frontend-testing.md](frontend-testing.md)。

「第六輪之後」一節記錄重跑後移除的死碼與修正的小問題（沒有重跑變異測試）。「最新結果」一節是第六輪：補上訊息、房間事件廣播與零星中風險測試，並修正錯誤處理中介層順序後的重跑結果。「第五輪」一節是補上通知 HTTP API、即時推播與批次已讀測試後的重跑結果。「第四輪」一節是補上 WebSocket 連線層測試、並讓公開房改私人時改為邀請制後的重跑結果。「第三輪」一節是處理第二輪留下的 387 個低價值存活者後的重跑結果。第〇節是第二輪：依第一輪結果修正與補測後的重跑結果。第一～八節保留第一輪（修正前）的原始分析作為基準。各項目的處理狀態以較新的一節為準。

---

## 第六輪之後：移除死碼與修正小問題

第六輪列出的 3 個死碼函數與 4 個小問題都已處理。這些修正沒有重跑變異測試，下面「最新結果」的數字仍是第六輪的實測值。

### 移除的死碼（`b5e874c`）

移除前再確認了一次：在後端程式、測試、腳本與前端搜尋呼叫端，也檢查了 `getattr` 這類動態呼叫。git 歷史顯示三個函數在初始 commit 就已存在，之後一直沒有呼叫端。

- `RoomRepository.update_member_role`：沒有任何 API 或 service 會修改成員角色。附帶一提，權限檢查認得 `admin` 角色，但目前只有 `owner` 與 `member` 會被設定，沒有任何途徑能把成員設成 `admin`。
- `app/utils/file_upload.py` 的 `upload_file`：檔案路由走 `FileService.upload_file`。移除後 utils 不再依賴 FastAPI 的 `HTTPException`。
- `BaseRepository.delete`：Room、User、Message repository 各自覆寫了 `delete`，Notification repository 用 `delete_by_id`。

這 3 個函數共 13 個變異體，原本都落在無覆蓋的程式碼上，下次重跑時會從總數中消失。

### 修正的小問題

| 問題 | 修正 | commit |
|---|---|---|
| 編輯訊息 API 接受 `status`：可把訊息設成已刪除而不廣播 `message_deleted`，DB 保留原文；也可把已刪除的訊息改回來並改寫 | `MessageUpdate` 移除 `status` 並拒絕未知欄位（422），與 `UserUpdate` 相同。已刪除的訊息不能再編輯（404），與列表一樣視為不存在 | `3f51288` |
| 引用預覽 `reply_to_message.created_at` 沒有時區標記 | 與訊息本身相同，以 `Z` 結尾 | `6478d67` |
| 通知統計 `recent_activity[].created_at` 沒有時區標記 | 改為具型別的 `NotificationActivity`，時間以 `Z` 結尾 | `6478d67` |
| 未讀通知 BFF 路由把後端回傳的物件當陣列，永遠回傳空列表 | 改用與通知列表相同的轉換函數；同時拿掉 `any`，改用 `URLSearchParams` 組 query | `824516c` |

每項都補了測試或改寫既有測試，並確認新測試在修正前會失敗。前端 BFF 路由沒有自動化測試，改為實際啟動前後端驗證：修正前回傳 `[]`，修正後回傳 1 則未讀通知與 `unread_count`。目前仍沒有前端頁面呼叫這個路由。

後端測試增為 1,050 個，行覆蓋率 93%。

**更正**：第五、六輪寫的「其他 API 一律以 `Z` 結尾」不精確。訊息與通知用 `Z`，使用者與房間用 `+00:00`，兩種都帶時區標記，瀏覽器解析結果相同。真正的問題是上面兩處完全沒有時區標記，瀏覽器會把這種時間當成本地時間。

---

## 最新結果：第六輪（訊息、房間事件與零星中風險）

第五輪後剩下 40 個中風險存活者：訊息 16 個、房間事件廣播 8 個、其他零星 16 個。這一輪逐一補上測試。補測時發現錯誤處理中介層的順序有誤，一併修正，再以相同工具完整重跑。

### 六輪對照

| 指標 | 第一輪 | 第二輪 | 第三輪 | 第四輪 | 第五輪 | 第六輪 |
|---|---:|---:|---:|---:|---:|---:|
| 測試數 | 496 | 785 | 959 | 976 | 1,008 | 1,047 |
| 行覆蓋率（`app/`） | 78% | 84% | 90% | 91% | 92% | 92% |
| 變異體 | 3,252 | 3,227 | 3,248 | 3,257 | 3,257 | 3,257 |
| killed | 1,356 | 1,975 | 2,693 | 2,765 | 2,854 | 2,924 |
| survived | 994 | 686 | 246 | 218 | 186 | 145 |
| 落在無覆蓋程式碼上 | 902 | 566 | 309 | 274 | 217 | 188 |
| 從未被任何測試執行的函數 | 96 個（623 個變異體） | 59 個（404 個變異體） | 25 個（115 個變異體） | 21 個（88 個變異體） | 11 個（35 個變異體） | 4 個（19 個變異體） |
| 存活：高風險 | 71 | 18 | 4 | 0 | 0 | 0 |
| 存活：中風險 | 355 | 190 | 68 | 51 | 40 | **0** |
| 存活：低價值 | 458 | 387 | 72 | 64 | 40 | 39 |
| 存活：等價變異體 | 110 | 91 | 102 | 103 | 106 | 106 |
| **Mutation score**（killed ÷ 排除等價後的總數） | 43% | 63% | 86% | 88% | 91% | **93%** |
| **有覆蓋程式碼的 mutation score** | 61% | 77% | 95% | 96% | 97% | **99%** |

不排除等價變異體的原始分數為 89.8%（有覆蓋：95.3%）。第六輪共 28 分鐘，1 個逾時（判為 killed）、0 個執行錯誤，1,047 個測試逐一單獨執行皆通過。

### 修正的問題：錯誤處理中介層接不到路由例外（`3ce1b5a`）

為了殺死「移除 `GlobalErrorHandler`」的變異體，測試透過真實的 app 觸發房名唯一索引衝突，結果收到 500 `{"error": "Internal server error"}`。照設計，`GlobalErrorHandler` 應該回 409 `DUPLICATE_KEY_ERROR`。

原因是註冊順序。`SecurityHeadersMiddleware` 註冊得比 `GlobalErrorHandler` 早，所以位在它的內層，而它自帶 catch-all，會先把路由拋出的例外轉成一般 500。`GlobalErrorHandler` 因此從沒處理過任何路由例外，這也是移除它的變異體能存活的原因。影響：

- 唯一索引擋下的競態（同名房間、同名帳號同時建立）回 500，而不是 409
- Redis 斷線回 500，而不是 503
- 錯誤回應不是標準格式，前端 BFF 讀不到 `error.message`，只能顯示通用錯誤

修正方式是把安全標頭中介層改成最後註冊（最外層）：例外先由 `GlobalErrorHandler` 轉成標準錯誤回應，安全標頭中介層再為所有回應補上安全標頭，錯誤回應與限流的 429 也包括在內。回歸測試模擬「名稱檢查通過後才被別人搶先建立」的房間，斷言回 409 `DUPLICATE_KEY_ERROR` 且帶安全標頭。順序要求已補進 [`technical-reference.md`](technical-reference.md)。

### 補的測試

- **訊息（`392c5d1`）**
  - HTTP：新訊息不標記為已編輯；2000 字上限；同一 `client_id` 重送回傳既有訊息，不同房間各自獨立；列表帶被回覆訊息的引用預覽，`get_reply_previews` 第一次被執行；編輯會去除前後空白並保留檔案資訊；空白編輯被拒；只改 metadata 時不動內容；搜尋排除已刪除的訊息
  - repository：序號計數器文件的位置；斷線補發排除已刪除的訊息；只帶起始或結束日期的搜尋
  - WS：圖片 / 檔案訊息保留類型與 metadata；@bot 串流途中，同房的第二次 @bot 被擋；圖片夾在兩組 @bot 往返之間時，不會截斷對話歷史
- **房間（`ba9a345`）**：加入、更新、離開房間後，所有看得到房間的在線者都收到 `room_updated`，內容是不帶收件者成員身分的摘要；離線成員離開時，`user_left` 以 `id` 識別；「我的房間」與搜尋結果的排序
- **零星（`cb213e0`）**：生產模式的錯誤回應不帶細節、不記 traceback；健康檢查在 ping 失敗時回報 disconnected；`GET /api/ai/status`；AI 串流分段送出的是增量；生產 CSP 整串比對；預設的上傳與縮圖目錄和下載端點一致；產生縮圖時也在解碼前檢查像素上限；使用者被移出唯一所在的房間後，3 秒內變為離線

### 第五輪存活者的去向

- **中風險 40 個，殺死 39 個**。剩下的 1 個（第五輪 #159：`AppError.__init__` 不呼叫 `super().__init__`）複核後改判等價：`BaseException.__new__` 已把建構參數存進 `args`，`str(e)` 不受影響。
- **低價值 40 個，殺死 1 個**：`count_after_seq` 把已刪除的訊息算進 gap，由斷線補發的新測試順帶殺死。
- **等價 106 個，殺死 1 個**：`get_after_seq` 的 `limit` 預設值。新測試以預設值呼叫，所以殺死了它；正式程式唯一的呼叫端一律明確傳入 `limit`，等價的判讀不變。
- 另更正 1 個延用的說明：`main.py` 第 66 行的 `"*"` 是 CORS 設定的比較，延用的說明誤寫成 TrustedHost。它仍屬等價。

### 發現的小問題（第六輪當時未修改，之後已修正，見「第六輪之後」一節）

- 編輯訊息的 API（`PUT /api/messages/{id}`）接受 `status` 欄位。寄件者可以把自己的訊息設成 `deleted`：不會廣播 `message_deleted`，DB 也保留原文。也可以把已刪除的訊息設回 `sent` 並改寫內容。只影響自己的訊息，前端沒有這種用法。
- 訊息列表中，引用預覽的時間戳（`reply_to_message.created_at`）沒有 `Z`，與第五輪記錄的 `recent_activity` 同類。前端只顯示作者與內容。
- 第五輪記錄的兩個小問題（`recent_activity` 的時間格式、未讀通知的 BFF 路由）仍未修改。
- 從未被執行的 4 個函數中，有 3 個是沒有呼叫端的死碼：`RoomRepository.update_member_role`、`app/utils/file_upload.py` 的 `upload_file`（檔案路由用的是 `FileService.upload_file`），以及 `BaseRepository.delete`（用到它的子類都覆寫了）。

### 仍待處理

- **高風險、中風險：0 個**
- **低價值 39 個**：14 個在 `image_processor.py`（圖片資訊的欄位名、EXIF、縮圖品質），6 個在 `file_service.py`（圖片上傳回應中前端沒用到的欄位），其餘是隨機 token 長度、錯誤訊息文字、`updated_at` 精度等。另有 2 個是工具的測試選擇沒選到的通知 `limit` 上限。
- **從未被執行的 4 個函數（19 個變異體）**：`lifespan`（app 啟動流程，測試不經過）與上述 3 個死碼。死碼已在第六輪之後移除，剩下 `lifespan`（6 個變異體）。

### 建議的下一批（第六輪當時）

第 1、2 項已完成，見「第六輪之後」一節。

1. **小問題的行為修正**：編輯 API 只允許改 `content` / `metadata`；引用預覽與 `recent_activity` 的時間格式統一帶 `Z`；修正或移除未讀通知的 BFF 路由。這些會改變 API 行為，需要先確認方向。
2. **移除 3 個死碼函數**，可直接消除 13 個無覆蓋的變異體。
3. 剩下的低價值存活者多是前端沒用到的欄位（圖片資訊、縮圖），補測的價值不高；等前端要用時再補。
4. 前端（SvelteKit）目前沒有任何測試，是下一個較大的缺口。（已補上，見 [frontend-testing.md](frontend-testing.md)）

---

## 第五輪：通知

第四輪後，通知是剩下最大的缺口：7 個通知 HTTP 路由與對應的 service 方法從未被任何測試執行，通知 repository 的統計測試又以 `>=` 斷言（數量加倍也會通過）。這一輪補上通知的端到端測試，再以相同工具完整重跑。

### 五輪對照

| 指標 | 第一輪 | 第二輪 | 第三輪 | 第四輪 | 第五輪 |
|---|---:|---:|---:|---:|---:|
| 測試數 | 496 | 785 | 959 | 976 | 1,008 |
| 行覆蓋率（`app/`） | 78% | 84% | 90% | 91% | 92% |
| 變異體 | 3,252 | 3,227 | 3,248 | 3,257 | 3,257 |
| killed | 1,356 | 1,975 | 2,693 | 2,765 | 2,854 |
| survived | 994 | 686 | 246 | 218 | 186 |
| 落在無覆蓋程式碼上 | 902 | 566 | 309 | 274 | 217 |
| 從未被任何測試執行的函數 | 96 個（623 個變異體） | 59 個（404 個變異體） | 25 個（115 個變異體） | 21 個（88 個變異體） | 11 個（35 個變異體） |
| 存活：高風險 | 71 | 18 | 4 | 0 | 0 |
| 存活：中風險 | 355 | 190 | 68 | 51 | 40 |
| 存活：低價值 | 458 | 387 | 72 | 64 | 40 |
| 存活：等價變異體 | 110 | 91 | 102 | 103 | 106 |
| **Mutation score**（killed ÷ 排除等價後的總數） | 43% | 63% | 86% | 88% | **91%** |
| **有覆蓋程式碼的 mutation score** | 61% | 77% | 95% | 96% | **97%** |

不排除等價變異體的原始分數為 87.6%（有覆蓋：93.9%）。第五輪共 28 分鐘，1 個逾時（判為 killed）、0 個執行錯誤，1,008 個測試逐一單獨執行皆通過。第一次啟動時，工具在「逐一單獨執行」這一步就中止了：新測試的參數化用了隨機產生的 ObjectId，每次收集的 node ID 都不同；改用固定值後（`2516f17`）重跑。重跑後另補了 1 個測試（`0b0bcb3`，見下），上表為重跑實測值，未計入。

### 通知測試（`2a72052`）

- **7 個通知路由**第一次以完整路由與依賴注入測試：列表回應整體比對、新到舊排序、預設分頁（列表 20 筆、未讀 50 筆）與 `skip` / `limit` 上下界、狀態與類型篩選、統計精確值；單筆已讀寫入 `read_at` 且不清掉 metadata；全部已讀只改自己的未讀、不覆蓋原本的閱讀時間；刪除 / 清空只限本人（別人的通知回 403、不存在回 404）
- **`NotificationService`**：即時推播的 payload 與 DB 中的通知整體比對；沒有內容的通知只寫入、不推播；全部 / 房間已讀寫入 `read_at`，房間已讀也比對只記在 metadata 的房間 ID；`notification_stats_update` 只在真的有通知被標記時送出一次
- **repository**：統計改為精確比對；metadata 更新與空更新

### 第四輪存活者的去向

- **中風險 51 個，殺死 11 個**：通知 8 個（單筆已讀不寫 `read_at` 4、統計 `$sum` 加倍 2、`mark_all_as_read` / `get_notification_stats` 回傳值 2）、第四輪重跑後已補斷言的 `room_type` 2 個、router 註冊 1 個
- **低價值 64 個，殺死 25 個**：通知 24 個（統計事件 9、即時推播欄位 6、房間已讀 5、全部已讀 4），以及第四輪重跑後已補斷言的錯誤事件 `timestamp`
- **等價 103 個，殺死 1 個**：`find_many` 的 #955（第四輪編號）。這是第二輪起延用分類時的誤配：`find_many` 有兩個「`"_id"` 改名」的變異體，簽名完全相同而共用了同一個判讀。在判斷式裡的那個確實等價；另一個改的是追加的 tiebreaker 欄位，等於不加 tiebreaker，應屬中風險。這輪它和同類的 #914 都只被「測試資料剛好落在同一毫秒」的測試偶然殺死，每輪由不同的測試殺死。重跑後補了確定性的測試（`0b0bcb3`）：以相同 `created_at` 的資料驗證分頁依 `_id` 新到舊排序，逐一驗證能穩定殺死兩者。

### 本輪新判讀的 6 個存活者

- **等價 4 個**：`get_user_notifications` 的參數預設值（唯一呼叫端一律明確傳入）3 個；即時推播讀不到 `status` 時退回 `UNREAD`（通知建立當下一律是未讀）1 個，第四輪原判低價值。
- **工具的測試選擇沒選到 2 個**：兩個通知列表的 `limit` 上限（`le=100` 改成 101）。測試已有 `limit=101` 回 422 的案例，`check_kill` 以整個測試檔驗證時會殺死它們；但這個請求在 FastAPI 驗證階段就被擋下、不執行路由函數本體，覆蓋率對應不到這個測試，完整重跑時便沒有選到。上表仍計為存活（列在低價值）。

### 發現的小問題（第五輪當時未修改，第六輪之後已修正）

- `GET /api/notifications/stats` 的 `recent_activity` 時間戳沒有時區標記（`2026-01-01T00:03:00`），其他 API 一律以 `Z` 結尾。前端 BFF 轉換時丟掉了這個欄位，目前不影響使用；測試只比對時間值，沒有把這個格式寫死。
- 前端 BFF `frontend/src/routes/api/notifications/unread/+server.ts` 把後端回傳的物件（`{notifications, unread_count}`）當成陣列處理，永遠回傳空列表。前端沒有任何地方呼叫這個路由。

### 仍待處理（第五輪當時）

- **中風險 40 個**：
  - 訊息（16）：`message_repository` 的 seq 計數器文件位置、同一 `client_id` 的冪等查詢、只改內容時清掉 metadata、斷線補發與搜尋包含已軟刪除的訊息、只帶單邊日期時篩選被忽略；`message_service` 的 2000 字元邊界、引用預覽、編輯時的內容驗證；WS 發送圖片 / 檔案訊息的類型與 metadata
  - 房間（8）：update / join / leave 後的 `room_updated` 廣播與內容、`is_member`、離線者離開時缺 `id`、「我的房間」與搜尋的排序
  - 其他（16）：健康檢查不 ping Mongo / Redis、生產模式錯誤細節外洩、全域錯誤處理與 AI router 未註冊、生產 CSP、`edited` 預設值、AI 串流的 `delta`、@bot 同房鎖、被踢後未排程離線、上傳與縮圖目錄、縮圖開圖的像素上限、bot 歷史遇到非文字訊息即中斷、例外訊息為空
- **低價值 40 個**：14 個在 `image_processor.py`（圖片資訊欄位），6 個在 `file_service.py`；通知只剩上述 2 個工具沒選到的。
- **從未被執行的 11 個函數**：`lifespan`、`get_reply_previews`、`update_member_role`、`FileUploadManager.upload_file`、`get_ai_status` / `is_available`、`BaseRepository.delete`，以及幾個 DI 工廠函數。

### 建議的下一批（第五輪當時）

1. **訊息**：`message_repository` 對真實 MongoDB 的冪等重送、搜尋、斷線補發排除已刪除訊息；`message_service` 的編輯驗證與引用預覽；WS 發送圖片 / 檔案訊息。可處理約 16 個中風險，並讓 `get_reply_previews` 第一次被執行。
2. **房間事件廣播**：update / join / leave 後誰收到 `room_updated`、收到什麼。可處理約 8 個中風險。
3. **零星的中風險**：健康檢查、生產模式錯誤回應、AI 串流與 @bot 同房鎖、被踢後的離線排程。

---

## 第四輪：WebSocket 連線層與私人房邀請制

第三輪留下的 4 個高風險存活者都在 WebSocket 連線層，而 `websocket_endpoint` 本身與斷線補發的 `send_gap_messages` 從未被任何測試執行。這一輪以經過 ASGI 的真實 WebSocket 連線補測，並依第一輪第五節 #4 的決定（方案 a）修正「公開房改成私人後沒有人能加入」，再以相同工具完整重跑。

### 四輪對照

| 指標 | 第一輪 | 第二輪 | 第三輪 | 第四輪 |
|---|---:|---:|---:|---:|
| 測試數 | 496 | 785 | 959 | 976 |
| 行覆蓋率（`app/`） | 78% | 84% | 90% | 91% |
| 變異體 | 3,252 | 3,227 | 3,248 | 3,257 |
| killed | 1,356 | 1,975 | 2,693 | 2,765 |
| survived | 994 | 686 | 246 | 218 |
| 落在無覆蓋程式碼上 | 902 | 566 | 309 | 274 |
| 從未被任何測試執行的函數 | 96 個（623 個變異體） | 59 個（404 個變異體） | 25 個（115 個變異體） | 21 個（88 個變異體） |
| 存活：高風險 | 71 | 18 | 4 | **0** |
| 存活：中風險 | 355 | 190 | 68 | 51 |
| 存活：低價值 | 458 | 387 | 72 | 64 |
| 存活：等價變異體 | 110 | 91 | 102 | 103 |
| **Mutation score**（killed ÷ 排除等價後的總數） | 43% | 63% | 86% | **88%** |
| **有覆蓋程式碼的 mutation score** | 61% | 77% | 95% | **96%** |

不排除等價變異體的原始分數為 84.9%（有覆蓋：92.7%）。第四輪共 28 分鐘，1 個逾時（判為 killed）、0 個執行錯誤，976 個測試逐一單獨執行皆通過。重跑後另補了 2 個斷言（改成私人後回應的 `room_type`、無效 JSON 錯誤事件的 `timestamp`，`ff7a348`），逐一驗證殺死 3 個本輪新出現的存活者（2 個中風險、1 個低價值）；上表為重跑實測值，未計入。

全套測試在這次的機器上約 34 秒；第三輪的 commit 在同一台機器上也要約 35 秒，差異來自執行環境。新增的 14 個 WebSocket 端點測試合計約 3 秒。

### 第三輪的 4 個高風險存活者：全數殺死

編號為第三輪附錄的編號：

- **斷線重連補發（#2870 `last_seq` 參數名稱、#2821 補發呼叫）**：以 `last_seq=3` 重連，斷言收到的 `message_sync` 只含 seq 4、5 且 `full_reload` 為 false；已是最新時收到空的 sync；補發失敗、`last_seq` 為空字串 / 非數字 / 負數時退回完整歷史
- **`type: "message"` 別名（#2874）**：以前端實際送出的格式發訊息，斷言訊息寫入 DB、ack 帶 `client_id` / `message_id` / `seq`、雙方都收到廣播
- **`/summary` 判斷反轉（#2886）**：一般訊息不呼叫 AI 摘要；`/summary` 以正確的對話內容呼叫摘要並廣播 bot 訊息

第三輪的 68 個中風險有 19 個被殺死，其中 15 個在即時通知推播（`send_real_time_notification`）：端點測試把推播的通知 payload 與 DB 中的通知整體比對（id、`user_id`、標題、內容、metadata、時間戳）。72 個低價值有 11 個被殺死。

### 方案 a：公開房改成私人時改為邀請制（`2b8c1fe`）

`update_room` 在更新後的房間型別為私人時，一律把 `join_policy` 設為 `invite`（與 `create_room` 相同）；房間原本沒有邀請碼就產生一組，已有則沿用。私人房也不能再被改回直接加入。測試涵蓋：公開房改私人後回應帶邀請碼、`room_type: private`、`join_policy: invite`，沒有邀請碼加入回 400、帶邀請碼可加入；已有邀請碼時沿用；私人房改 `join_policy: direct` 仍維持邀請制。

已知限制：

- 前端房間設定中的「房間類型」選項目前被註解隱藏（`RoomSettings.svelte`），只有直接呼叫 API 才能切換。
- 改成私人後，`room_updated` 只送給成員（第三輪 `7832e5c` 的修正），已經在列表上看到這個房間的非成員不會收到移除事件，重新整理後才會消失。

### WebSocket 端點測試（`752c407`）

Starlette 的 `TestClient` 在另一個事件迴圈執行 app，與測試共用的非同步 MongoDB / Redis 客戶端不相容。測試改用自寫的 ASGI WebSocket 驅動，在同一個事件迴圈中直接呼叫 app，走完整的 ws ticket 認證、路由與 `websocket_endpoint`；每個測試使用全新的 `ConnectionManager`（debounce 設為 0）。14 個測試涵蓋：

- 首次連線收到歷史；`last_seq` 重連補發（缺口、已是最新、補發失敗、無效值）
- `type: "message"` 發訊息的寫入、ack、雙方廣播，以及房主收到的即時通知 payload 與 DB 一致
- `/summary` 分派（只有 `/summary` 才呼叫 AI 摘要，bot 訊息廣播給房間）
- ping / pong、無效 JSON、未知訊息類型
- 端點層未預期例外以 4000 關閉、無效 ticket 與不存在的房間以 4001 關閉
- 斷線後廣播 `user_left` 與離線狀態

### 仍待處理（第四輪當時）

- **中風險 51 個**（其中 2 個已在重跑後補斷言殺死）：
  - 訊息（16）：`message_repository` 的 seq 計數器文件位置、同一 `client_id` 的冪等查詢、只改內容時清掉 metadata、斷線補發與搜尋包含已軟刪除的訊息、只帶單邊日期時篩選被忽略；`message_service` 的 2000 字元邊界、引用預覽、編輯時的內容驗證；WS handler 的圖片 / 檔案訊息類型與 metadata
  - 通知（8）：單筆標記已讀不寫 `read_at`、統計 `$sum` 加倍、`mark_all_as_read` / `get_notification_stats` 的回傳值
  - 房間（8，不含已殺死的 2 個）：update / join / leave 後的 `room_updated` 廣播與內容、`is_member`、離線者離開時缺 `id`、「我的房間」與搜尋的排序
  - 其他（17）：健康檢查不 ping Mongo / Redis、生產模式錯誤細節外洩、全域錯誤處理與 router 未註冊、生產 CSP、`edited` 預設值、AI 串流的 `delta`、@bot 同房鎖、被踢後未排程離線、上傳與縮圖目錄、縮圖開圖的像素上限等
- **低價值 64 個**（其中 1 個已在重跑後殺死）：25 個在 `notification_service.py`（前端未使用的統計事件欄位等），14 個在 `image_processor.py`（圖片資訊欄位）。
- **從未被執行的 21 個函數**：通知 HTTP 路由（7 個端點全部）與對應的 service 方法、`lifespan`、`get_reply_previews`、`update_member_role`、`FileUploadManager.upload_file`、`get_ai_status` 等。

### 建議的下一批（第四輪當時）

1. **通知**：HTTP 路由（列表、未讀、統計、標記已讀、全部已讀、刪除、清空）的端到端測試，連帶 repository 的 `read_at`、`$sum` 統計與 service 的回傳值。可處理 8 個中風險，並讓 7 個從未執行的路由第一次被執行。
2. **訊息**：`message_repository` 對真實 MongoDB 的冪等重送、搜尋、斷線補發排除已刪除訊息；`message_service` 的編輯驗證與引用預覽；WS 發送圖片 / 檔案訊息。可處理約 16 個中風險。
3. **房間事件廣播**：update / join / leave 後誰收到 `room_updated`、收到什麼。可處理約 8 個中風險。

---

## 第三輪：處理低價值存活者

第二輪留下 387 個「低價值（low）」存活者：改壞了測試不會發現，但當時判讀影響不大（回應欄位名、設定預設值、時間戳精度、debounce 秒數、分頁邊界等）。這一輪逐一補測，並修正補測中發現的 7 個問題，再以相同工具完整重跑。

### 三輪對照

| 指標 | 第一輪 | 第二輪 | 第三輪 |
|---|---:|---:|---:|
| 測試數 | 496 | 785 | 959 |
| 全套測試時間 | 約 35 秒 | 約 18 秒 | 約 24 秒 |
| 行覆蓋率（`app/`） | 78% | 84% | 90% |
| 變異體 | 3,252 | 3,227 | 3,248 |
| killed | 1,356 | 1,975 | 2,693 |
| survived | 994 | 686 | 246 |
| 落在無覆蓋程式碼上 | 902 | 566 | 309 |
| 從未被任何測試執行的函數 | 96 個（623 個變異體） | 59 個（404 個變異體） | 25 個（115 個變異體） |
| 存活：高風險 | 71 | 18 | **4** |
| 存活：中風險 | 355 | 190 | 68 |
| 存活：低價值 | 458 | 387 | 72 |
| 存活：等價變異體 | 110 | 91 | 102 |
| **Mutation score**（killed ÷ 排除等價後的總數） | 43% | 63% | **86%** |
| **有覆蓋程式碼的 mutation score** | 61% | 77% | **95%** |

不排除等價變異體的原始分數為 82.9%（有覆蓋：91.6%）。第三輪共 27 分鐘，1 個逾時（判為 killed）、0 個執行錯誤，959 個測試逐一單獨執行皆通過。重跑後另補了 1 個測試（`Retry-After` 最短 1 秒的邊界），逐一驗證殺死 1 個低價值變異體；上表為重跑實測值，未計入。

### 387 個低價值存活者的去向

| 結果 | 數量 | 說明 |
|---|---:|---|
| 被新測試殺死 | 377 | 其中 8 個所在的程式碼之後因修正而改寫（改寫前已逐一驗證被殺死） |
| 複核後改判等價 | 6 | 例如毫秒截斷常數 `1000 → 1001`：BSON 寫入時仍截斷回同一毫秒，且呼叫端都從 DB 讀回；`CORS_ORIGINS == "*"` 的比對改壞後走另一分支，結果仍是 `["*"]` |
| 判定不值得測 | 2 | 邀請碼與 ws ticket 的隨機位元組數（16→17、32→33）：只改變長度與熵，殺死它只能把長度寫死在測試裡 |
| 揭露真正的問題、已修正 | 2 | `Retry-After` 計算方式、WS 全部已讀回失敗（見下表） |

補測以 5 組平行進行，每組以 `check_kill`（逐一套用變異、只跑指定測試）驗證，再由完整重跑交叉確認。原則是斷言可觀察的行為（HTTP 回應、真實 MongoDB 文件、Redis 狀態、WebSocket 送出的整個 payload），不讀模組常數和字面值比對；唯一例外是 `Settings()` 在未設定任何環境變數時的預設值，它就是未設定部署的實際行為，因此整表比對。

高風險存活者也連帶從 18 個降到 4 個：WS 事件契約測試殺死了 ack、`client_id`、`seq` 與 @bot 限流視窗；debounce 時間軸測試殺死了「使用者離開後誤刪整個房間廣播名單」；設定預設值殺死了 `DEBUG` 預設值；連線生命週期測試殺死了 Redis 連線鏈；gap 邊界測試殺死了全量重載的 skip / limit。第二輪的 190 個中風險有 143 個被殺死。

另有 8 個第二輪判為等價的變異體這次被殺死。它們以整個 app 為邊界確實觀察不到（例如 `FRONTEND_URL` 在 app 內沒有讀取點），但從元件自己的公開介面看得到（`Settings()` 的預設值、`validate_file` 的回傳內容），屬於第二輪判讀的邊界定義問題，不是新測試鎖住了實作細節。

### 修正的問題

補測時發現 7 個問題，各自獨立成 commit，都附回歸測試，且已確認新測試在修正前的程式碼上會失敗。

| commit | 問題 | 影響 |
|---|---|---|
| `7832e5c` | 建立私人房時，`room_created`（房名、描述、房主、人數）廣播給所有在線使用者，前端收到就加進房間列表；`room_updated` / `room_deleted` 也一樣。改為私人房只送給成員 | 私人房的存在與資訊外洩給所有在線者，與 HTTP 端「私人房對非成員不可見」不一致 |
| `3eec482` | 任何房間成員都能經 WS 或 HTTP 送出 `message_type: "system"` 的訊息；前端把它畫成無發送者的系統公告，且連發送者都無法刪除。改為在 `MessageService.create_message` 統一拒絕（HTTP 403） | 可冒充系統公告。後端沒有任何地方會產生 system 訊息，前端也從不送出 |
| `bcd3409` | 上傳 API 回應的 `file.path` 與 `thumbnails` 是伺服器上的絕對路徑，BFF 原樣轉給瀏覽器。改為不回傳 `path`，縮圖以下載 URL 表示 | 公開伺服器的目錄配置；前端未使用這兩個欄位 |
| `7d69750` | 限流是滑動視窗，但被擋時的 `Retry-After` 用固定視窗公式對齊到下一個整分鐘 / 整點。改為擋住這次請求的那筆紀錄滑出視窗所需的秒數 | 客戶端照 `Retry-After` 等待後重試仍可能被擋，也可能被要求多等到整點 |
| `a440561` | DEBUG 模式應該不送 HSTS，但 `security_config` 產生的自訂標頭仍帶 `max-age=31536000; includeSubDomains; preload`，且會覆蓋中介層的設定 | 開發者以 HTTPS 開 localhost 時，瀏覽器會把它記成只能走 HTTPS 長達一年 |
| `24849e3` | WS 的「全部已讀」在沒有未讀通知時回 `success=False`，也不同步其他裝置；房間已讀與 HTTP `/read-all` 在同樣情況都視為成功 | 行為不一致 |
| `42b3eaf` | 房間離開計時器被取消時，在 `finally` 以 key 直接移除表項，刪掉的其實是剛排入的新計時器 | 新計時器無人追蹤，5 秒內重新進房不被當成快速重連。目前正式流程不會觸發，屬防禦性修正 |

工具與測試基礎設施：

- `1c12a98`：變異測試工具重新產生變異體時，清掉上一次的執行結果。原本沒先刪 `backend/.mutation/` 就重跑時，舊結果會被續跑機制當成已完成。
- `44364f3`：測試用的 MongoDB / Redis DB 可以用環境變數 `TEST_DATABASE_NAME`、`TEST_REDIS_URL` 覆寫，多個測試程序可以平行執行；變異測試的 worker 改用這個機制，不再以字串取代修補 `test_config.py`。
- 修正一個不穩定的測試：偽造 `X-Forwarded-For` 的測試原本從 250 個 IP 中隨機挑選，重跑時會撞到 Redis 中仍在 1 小時視窗內的舊桶。
- `tests/test_database/test_mongodb_basic.py` 原本的測試類別名稱不以 `Test` 開頭，4 個測試從未被 pytest 收集執行；改為以真實連線測試連線生命週期。

### 補的測試

| commit | 內容 |
|---|---|
| `aba7f24` | `Settings` 預設值整表比對與 `.env` 載入規則；以指定設定重新組裝 `main.py`，測生產 CORS（來源 / 方法 / 標頭）、TrustedHost、HSTS 開關、開發模式 CSP；`/`、`/health`、OpenAPI info；401 的 `WWW-Authenticate: Bearer`；錯誤處理中介層的回應信封、debug 與生產差異、錯誤日誌欄位；MongoDB / Redis 連線生命週期 |
| `f8cf197` | 固定時間來源測限流：突發視窗邊界、重置秒數、429 body 與 `Retry-After` / `X-RateLimit-*` 一致、key TTL、DEBUG 寬鬆限流表；上傳 / 下載 API 經完整路由與 DI（回應契約、下載往返、各副檔名的 Content-Type 與 inline / attachment）；檔名與大小邊界；縮圖尺寸與 5 千萬像素上限 |
| `2dc68ac` | Repository 寫入時間戳截斷到毫秒（回傳值、DB 讀回值、當下時間三者一致）；排序以 `created_at` 為準（刻意讓 `created_at`、`_id`、插入順序互不相同）；5 個列表端點的分頁預設值與上下界；成功回應整體比對；gap 恰為 200 逐則補發、201 全量重載；AI 模型參數 |
| `219a167` | WS handler 對外事件契約：以替身 `connection_manager` 收集送出的事件、轉成客戶端實際收到的 JSON 後整個 payload 精確比對（welcome、歷史、ack、廣播、錯誤、通知預覽截斷、@bot 串流 / 錯誤 / 限流視窗、`/summary` 撈取量、typing、已讀各分支、背景 AI task） |
| `1199ee1` | 以虛擬時鐘驗證離線（3 秒）與重新進房（5 秒）debounce 的邊界、計時器取消與重排；在線 / 離線 / 通知事件 payload；bot 歷史的往返組數、時間窗、回答截斷；缺欄位的舊快取與舊 token |

### 仍存活的 4 個高風險變異體（第四輪已全數殺死）

都在 WebSocket 連線與訊息分派，編號為第三輪附錄的編號：

- **斷線重連補發（2）**：重連的 `last_seq` 參數名稱（#2870）、補發呼叫（#2821）。`send_gap_messages` 從未被任何測試執行
- **前端實際使用的 `type: "message"` 別名（1）**：#2874
- **`/summary` 判斷反轉（1）**：#2886，改壞後每則一般訊息都會觸發 AI 摘要

### 仍待處理（第三輪當時）

- **中風險 68 個**：26 個是本輪新判讀的（多為這輪才第一次被執行到的程式碼），集中在即時通知的 payload（`notification_service.py` 17 個：例如推播的通知 id 與 DB id 不一致、必填欄位遺失時前端會丟棄通知）與通知統計（`$sum` 加倍）；其餘 42 個延續第二輪。
- **低價值 72 個**：69 個是本輪新判讀的（圖片資訊欄位、通知統計事件等前端未使用的欄位）；其餘 3 個是判定不值得測的隨機位元組數。
- **從未被執行的 25 個函數**：通知 HTTP 路由（7 個端點全部）、`send_gap_messages`、`ConnectionManager.broadcast_message` / `handle_ping`、WebSocket 端點本身、`lifespan`、`get_reply_previews`、`update_member_role` 等。

### 待決定（第四輪已採方案 a）

第一輪第五節 #4 當時仍待產品決定：把公開房改成私人時，`update_room` 不會產生邀請碼，也不會調整 `join_policy`，結果沒有人能加入。選項：(a) 改私人時自動產生邀請碼並改為邀請制；(b) 禁止公開 / 私人互換；(c) 維持現狀。

### 建議的下一批（第三輪當時）

1. **WebSocket 連線層**：以真實 WebSocket（Starlette `TestClient.websocket_connect`）測 `last_seq` 重連補發、`type: "message"` 別名、`/summary` 分派。可處理剩下 4 個高風險，並覆蓋 `send_gap_messages`、`websocket_endpoint`、`broadcast_message`。
2. **通知**：HTTP 路由（列表、未讀、統計、標記已讀、刪除）與即時推播 payload 的整體比對。可處理約 23 個中風險與 7 個未執行的路由。
3. **剩下的中風險**：訊息搜尋的日期篩選與已刪除訊息、冪等重送（同一 `client_id`）、房間事件廣播時機。

---

## 〇、修正後重跑（第二輪）

依第一輪的建議修正了 7 個問題、修正了 5 個有缺陷的測試、補上 P0 的測試，再以相同工具與方法重跑。

### 前後對照

| 指標 | 第一輪（修正前） | 第二輪（修正後） |
|---|---:|---:|
| 測試數 | 496 | 785 |
| 全套測試時間 | 約 35 秒 | 約 18 秒 |
| 行覆蓋率（`app/`） | 78% | 84% |
| 變異體 | 3,252 | 3,227 |
| killed | 1,356 | 1,975 |
| survived | 994 | 686 |
| 落在無覆蓋程式碼上 | 902 | 566 |
| 從未被任何測試執行的函數 | 96 個（623 個變異體） | 59 個（404 個變異體） |
| 存活：高風險 | 71 | **18** |
| 存活：中風險 | 355 | 190 |
| 存活：等價變異體 | 110 | 91 |
| **Mutation score**（killed ÷ 排除等價後的總數） | 43% | **63%** |
| **有覆蓋程式碼的 mutation score** | 61% | **77%** |

不排除等價變異體的原始分數為 41.7% → 61.2%（有覆蓋：57.7% → 74.2%）。變異體總數略減，是因為修正時移除了部分程式碼（例如 MIME 回退表、`os.getenv` 讀取邏輯）。第二輪共 35.6 分鐘，0 個逾時、0 個執行錯誤，785 個測試逐一單獨執行皆通過。第二輪結束後另補了 1 個斷言（邀請碼驗證回應的 `valid` 欄位），逐一驗證殺死 2 個中風險變異體；上表為第二輪實測值，未計入這 2 個。

第一輪缺口最集中的檔案：

| 檔案 | 第一輪 score | 第二輪 score |
|---|---:|---:|
| `security_config.py` | 5% | 88% |
| `websocket/auth.py` | 15% | 93% |
| `middleware/rate_limiting.py` | 19% | 78% |
| `routers/rooms.py` | 1% | 73% |
| `models/room.py` | 34% | 93% |
| `services/room_service.py` | 48% | 73% |
| `database/indexes.py` | 62% | 100% |
| `services/user_service.py` | 69% | 86% |
| `utils/file_upload.py` | 24% | 60% |

<details>
<summary>第二輪：依架構分層與依檔案</summary>

| 層 | 變異體 | killed | survived | 其中 high | 其中 medium | 無覆蓋 | score | 有覆蓋 score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| auth | 64 | 53 | 9 | 0 | 0 | 2 | 87% | 90% |
| routers | 212 | 122 | 30 | 0 | 2 | 60 | 58% | 80% |
| services | 593 | 317 | 80 | 2 | 37 | 196 | 55% | 84% |
| repositories | 518 | 352 | 77 | 0 | 17 | 89 | 71% | 86% |
| websocket | 554 | 302 | 175 | 13 | 54 | 77 | 55% | 64% |
| middleware | 381 | 283 | 93 | 0 | 3 | 5 | 75% | 76% |
| models | 126 | 101 | 22 | 0 | 2 | 3 | 94% | 96% |
| utils | 437 | 222 | 102 | 0 | 53 | 113 | 52% | 70% |
| database | 75 | 53 | 18 | 2 | 2 | 4 | 74% | 78% |
| core / config / main | 267 | 170 | 80 | 1 | 20 | 17 | 64% | 69% |
| **合計** | **3,227** | **1,975** | **686** | **18** | **190** | **566** | **63%** | **77%** |

| 檔案 | 變異體 | killed | survived | 其中 high | 其中 medium | 無覆蓋 | score | 有覆蓋 score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `services/file_service.py` | 65 | 0 | 0 | 0 | 0 | 65 | 0% | — |
| `websocket/routes.py` | 6 | 0 | 0 | 0 | 0 | 6 | 0% | — |
| `routers/notifications.py` | 43 | 1 | 0 | 0 | 0 | 42 | 2% | 100% |
| `routers/files.py` | 16 | 1 | 0 | 0 | 0 | 15 | 6% | 100% |
| `utils/image_processor.py` | 116 | 8 | 20 | 0 | 10 | 88 | 7% | 29% |
| `services/notification_service.py` | 100 | 13 | 1 | 0 | 1 | 86 | 13% | 93% |
| `database/redis_conn.py` | 15 | 3 | 10 | 2 | 2 | 2 | 21% | 25% |
| `routers/ai.py` | 3 | 1 | 0 | 0 | 0 | 2 | 33% | 100% |
| `main.py` | 70 | 29 | 35 | 0 | 10 | 6 | 42% | 46% |
| `config.py` | 45 | 19 | 26 | 1 | 3 | 0 | 43% | 43% |
| `repositories/message_repository.py` | 156 | 75 | 27 | 0 | 8 | 54 | 49% | 75% |
| `websocket/handlers.py` | 318 | 158 | 113 | 12 | 26 | 47 | 50% | 59% |
| `websocket/manager.py` | 171 | 91 | 57 | 1 | 28 | 23 | 54% | 63% |
| `database/mongodb.py` | 20 | 10 | 8 | 0 | 0 | 2 | 56% | 62% |
| `routers/invitations.py` | 5 | 3 | 2 | 0 | 2 | 0 | 60% | 60% |
| `utils/file_upload.py` | 241 | 142 | 78 | 0 | 43 | 21 | 60% | 66% |
| `repositories/base.py` | 93 | 54 | 21 | 0 | 2 | 18 | 64% | 81% |
| `core/bot.py` | 48 | 32 | 8 | 0 | 2 | 8 | 67% | 80% |
| `middleware/error_handler.py` | 93 | 64 | 26 | 0 | 2 | 3 | 69% | 71% |
| `services/message_service.py` | 107 | 71 | 19 | 2 | 8 | 17 | 69% | 83% |
| `routers/messages.py` | 27 | 19 | 7 | 0 | 0 | 1 | 70% | 73% |
| `services/ai_service.py` | 31 | 22 | 7 | 0 | 3 | 2 | 71% | 76% |
| `routers/rooms.py` | 71 | 52 | 19 | 0 | 0 | 0 | 73% | 73% |
| `services/room_service.py` | 208 | 141 | 50 | 0 | 25 | 17 | 73% | 81% |
| `middleware/security_headers.py` | 51 | 38 | 12 | 0 | 0 | 1 | 76% | 78% |
| `core/exceptions.py` | 13 | 10 | 3 | 0 | 1 | 0 | 77% | 77% |
| `middleware/rate_limiting.py` | 237 | 181 | 55 | 0 | 1 | 1 | 78% | 78% |
| `auth/dependencies.py` | 37 | 27 | 9 | 0 | 0 | 1 | 79% | 82% |
| `repositories/notification_repository.py` | 89 | 69 | 15 | 0 | 5 | 5 | 82% | 87% |
| `auth/password.py` | 7 | 6 | 0 | 0 | 0 | 1 | 86% | 100% |
| `services/user_service.py` | 82 | 70 | 3 | 0 | 0 | 9 | 86% | 97% |
| `repositories/room_repository.py` | 126 | 103 | 14 | 0 | 2 | 9 | 87% | 94% |
| `core/fastapi_integration.py` | 41 | 36 | 3 | 0 | 3 | 2 | 88% | 92% |
| `security_config.py` | 50 | 44 | 5 | 0 | 1 | 1 | 88% | 90% |
| `models/notification.py` | 13 | 9 | 4 | 0 | 1 | 0 | 90% | 90% |
| `models/user.py` | 24 | 18 | 6 | 0 | 0 | 0 | 90% | 90% |
| `utils/json_encoder.py` | 42 | 38 | 0 | 0 | 0 | 4 | 90% | 100% |
| `utils/ws_ticket.py` | 14 | 12 | 2 | 0 | 0 | 0 | 92% | 92% |
| `models/room.py` | 49 | 38 | 8 | 0 | 0 | 3 | 93% | 100% |
| `websocket/auth.py` | 59 | 53 | 5 | 0 | 0 | 1 | 93% | 95% |
| `repositories/user_repository.py` | 54 | 51 | 0 | 0 | 0 | 3 | 94% | 100% |
| `routers/auth.py` | 43 | 41 | 2 | 0 | 0 | 0 | 95% | 95% |
| `models/message.py` | 32 | 28 | 4 | 0 | 1 | 0 | 97% | 97% |
| `auth/jwt_handler.py` | 20 | 20 | 0 | 0 | 0 | 0 | 100% | 100% |
| `database/indexes.py` | 40 | 40 | 0 | 0 | 0 | 0 | 100% | 100% |
| `models/enums.py` | 8 | 8 | 0 | 0 | 0 | 0 | 100% | 100% |
| `routers/ws_ticket.py` | 4 | 4 | 0 | 0 | 0 | 0 | 100% | 100% |
| `utils/datetime_utils.py` | 7 | 7 | 0 | 0 | 0 | 0 | 100% | 100% |
| `utils/user_cache.py` | 17 | 15 | 2 | 0 | 0 | 0 | 100% | 100% |

</details>

### 修正的問題

7 個問題，每個都附回歸測試；有新測試的修正都已確認新測試在修正前的程式碼上會失敗。

| commit | 問題 | 來源 |
|---|---|---|
| `9d28a63` | `PUT /api/auth/profile` 不驗證目前密碼就能改密碼。`UserUpdate` 移除 `password` 並拒絕未知欄位，密碼只能經 `change-password` 修改 | 第一輪第五節 #1 |
| `89d94f0` | 上傳時副檔名不在白名單就改用客戶端宣稱的 MIME，`evil.html` 帶 `image/png` 會被當成圖片存下。改為只採信副檔名 | 第一輪第五節 #2 |
| `75bc5af` | 寫在 `.env` 的 `SECURITY_*` 不生效。改由 `Settings` 讀取 | 第一輪第五節 #3 |
| `9998862` | `GET /api/messages/{id}` 只要求登入，知道訊息 ID 就能讀私人房的訊息（IDOR）。改為僅限房間成員，私人房非成員回 404 | 補測時新發現 |
| `a852bbf` | 限流設定依 dict 順序做前綴比對，圖片上傳 `/api/files/upload/image` 套用的是通用 `/api/` 限制而非上傳限制。改為最長前綴優先 | 補測時新發現 |
| `1ce72ac` | 邀請碼過期檢查拿 DB 讀回的 naive 時間與 aware 時間比較，會拋 `TypeError`（500）。目前沒有程式寫入過期時間，屬潛伏問題 | 補測時新發現 |
| `a657a56` | `ws_ticket` 使用 redis-py 已棄用的 `setex`，改用 `set(..., ex=)` | 補測時新發現 |

### 補的測試

| commit | 內容 |
|---|---|
| `60f89e2` | 修正第四節的 5 個有缺陷測試：弱密碼邊界、停用帳號 refresh 對照組、索引改用真實 DB 比對規格與唯一性、模型邊界與列舉契約、真實 app 的安全行為 |
| `b1a55fc` | token 撤銷端到端：改密碼後舊 access / refresh token 401、只改資料不撤銷、刪帳後被拒，並斷言快取確實生效 |
| `681d856` | rooms / messages HTTP 授權：成員限定端點、私人房可見性、邀請碼僅房主可見、各加入策略、房主權限、訊息讀寫授權；`add_member` 的原子人數條件 |
| `a657a56` | WebSocket 認證鏈與一次性 ws ticket |
| `a852bbf` | 限流 dispatch：生產設定、真實 Redis，實際打到 429；Redis 不可用時改為失敗而非 skip |
| `75bc5af` | 安全配置的載入來源與生產 CSP / HSTS 內容 |
| `f62e86f` | 測試中把 bcrypt cost 降到 rounds=4（雜湊格式與流程不變），全套測試由約 48 秒降到約 17 秒 |
| `0bd7335` | 補強 3 處斷言：WS 頭像、人數上限確實寫入、路徑 `room_id` 優先於 body |

### 第一輪缺口的處理狀態

| 項目 | 狀態 | 說明 |
|---|---|---|
| P0-1 認證與授權入口 | ✅ 已補 | `require_room_membership`、`get_room_for_user`、WS 認證鏈、ws ticket、rooms / messages 路由皆已被測試執行並斷言 |
| P0-2 token 撤銷鏈 | ✅ 已補 | 第一輪列出的 13 個相關存活者：12 個（或改寫後對應的變異體）已被殺死，#2226 所在程式碼已隨修正移除 |
| P0-3 房間存取規則 | ✅ 已補 | `room_service.py` 高風險存活 8 → 0 |
| P0-4 限流 | ✅ 已補（Redis 連線鏈除外） | `rate_limiting.py` 高風險存活 13 → 0；`redis_conn.py` 仍有 2 個 |
| P0-5 檔案上傳 / 下載 | 🟡 部分 | 上傳管理器（白名單、magic 簽章、內容完整性、檔名唯一）已測；`file_service.py` 仍完全無覆蓋（含下載路徑穿越防護） |
| P0-6 密碼長度政策 | ✅ 已補 | |
| P1-1 序號、斷線補發、冪等 | ⬜ 未處理 | 剩 6 個高風險 |
| P1-2 即時廣播與 WS 協定 | ⬜ 未處理 | 剩 7 個高風險 |
| P1-3 唯一索引耦合 | ✅ 已補 | `indexes.py` 100% |
| P2 API 契約與設定 | 🟡 部分 | 錯誤狀態碼、路由接線、Pydantic 邊界、列舉契約、生產安全標頭已測；生產 CORS / TrustedHost、`DEBUG` 預設值、通知、WS payload 尚未 |

### 仍存活的 18 個高風險變異體

編號為第二輪附錄的編號（第三輪後剩 4 個，第四輪全數殺死，見「第四輪」一節）：

- **訊息序號與斷線補發（6）**：重連的 `last_seq` 參數名稱（#2848）、補發呼叫（#2799）、沒帶 `last_seq` 時的條件（#2798）、gap 超過 200 時全量重載的 skip / limit（#1826、#1828）、即時廣播的 `seq` 欄位（#2790）
- **WebSocket 協定與廣播（7）**：前端實際使用的 `type: "message"` 別名（#2852）、`client_id` 讀取（#2856、#2951）、ack 的送出與格式（#2757、#2950、#2956）、使用者離開後誤刪整個房間的廣播名單（#3187）
- **@bot 濫用防護（2）**：`/summary` 判斷反轉（#2864）、@bot 限流視窗改成 0（#2961）
- **Redis 連線鏈（2）**：`init_redis` 不連線（#271）、`connect` 條件反轉（#276）。conftest 仍吞掉 Redis 初始化錯誤
- **安全預設（1）**：`Settings.DEBUG` 預設值（#89）

### 待決定（第四輪已採方案 a）

第一輪第五節 #4：把公開房改成私人時，`update_room` 不會產生邀請碼，也不會調整 `join_policy`。目前已加測試，固定「私人房 + DIRECT 一律拒絕直接加入（403）」這個安全面的行為；但「改成私人後沒有邀請碼、沒人能加入」要怎麼處理，需要產品決定：
- (a) 改成私人時自動產生邀請碼，並改為邀請制
- (b) 禁止公開 / 私人互換
- (c) 維持現狀

### 建議的下一批（第二輪當時）

1. **WebSocket handler 層測試**：`last_seq` 補發的三種情況、`type` 別名、ack 與廣播 payload、離開後的廣播名單。預計可處理 13 個高風險。
2. **`message_repository` 對真實 MongoDB 的測試**：`next_room_seq` 連號不重號、同一 `client_id` 只存一筆。
3. **Redis 連線測試**：不吞錯；@bot 限流與 `/summary` 分派。
4. **補覆蓋**：`file_service` 整合測試（含下載路徑穿越）、通知路由與服務。
5. **設定預設值**：`Settings()` 在未設 `DEBUG` 時為 `False`；生產環境的 CORS / TrustedHost 分支。

---

## 一、第一輪結論摘要（修正前）

| 指標 | 數值 |
|---|---:|
| 變異體總數 | 3,252 |
| 被殺死（killed） | 1,356 |
| 存活（survived） | 994 |
| 落在完全沒被測試執行的程式碼上（無覆蓋） | 902 |
| 存活者中判定為等價變異體（不可能被任何測試抓到） | 110 |
| **Mutation score**（killed ÷ 排除等價後的總數） | **43%** |
| **有覆蓋程式碼的 mutation score**（killed ÷ 排除等價後的 killed + survived） | **61%** |

存活者分類：**高風險 71**、中風險 355、低價值 458、等價 110。

1. **測試多半確認「有呼叫」，很少確認「結果對」。** 496 個測試大量使用 mock 並以 `call_count`、`>=`、`in [201, 400, 422]` 這類寬鬆斷言，因此刪掉 payload 欄位、反轉條件、改錯 MongoDB 欄位名都不會被發現。
2. **安全控制是最弱的一環。** HTTP 房間成員檢查（`require_room_membership`）、WebSocket 認證鏈、一次性 WS ticket、私人房非成員 404、`change_password`、檔案下載的路徑穿越防護——這些函數在整個測試套件中**一行都沒被執行過**。有被執行的安全邏輯（token 撤銷、限流、邀請碼遮蔽、`max_members` 原子條件）也有多處能被改壞而不被發現。
3. **HTTP 路由層幾乎只測了 `/api/auth`。** rooms、messages、notifications、files、invitations、ws-ticket 的路由本體沒有任何測試執行過；刪掉 `main.py` 裡 auth 以外任何一個 `include_router`、甚至刪掉 `RateLimitingMiddleware` 或 `GlobalErrorHandler` 的註冊，496 個測試照樣全綠。
4. 判讀過程另外發現 **4 個現存問題**（不是變異體，是目前程式碼本身的行為）與 **5 個本身有缺陷的測試**，見第四、五節。

---

## 二、數字總覽

### 依架構分層

| 層 | 變異體 | killed | survived | 其中 high | 其中 medium | 無覆蓋 | score | 有覆蓋 score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| auth | 64 | 41 | 7 | 2 | 0 | 16 | 66% | 89% |
| routers | 211 | 45 | 0 | 0 | 0 | 166 | 21% | 100% |
| services | 592 | 254 | 96 | 16 | 47 | 242 | 44% | 75% |
| repositories | 520 | 310 | 91 | 6 | 24 | 119 | 63% | 83% |
| websocket | 554 | 257 | 171 | 13 | 52 | 126 | 47% | 61% |
| middleware | 378 | 144 | 156 | 13 | 7 | 78 | 39% | 49% |
| models | 127 | 40 | 84 | 5 | 45 | 3 | 37% | 38% |
| utils | 439 | 125 | 189 | 4 | 127 | 125 | 29% | 41% |
| database | 75 | 35 | 36 | 10 | 2 | 4 | 49% | 51% |
| core / config / main | 292 | 105 | 164 | 2 | 51 | 23 | 40% | 43% |
| **合計** | **3,252** | **1,356** | **994** | **71** | **355** | **902** | **43%** | **61%** |

routers 的「有覆蓋 score 100%」只代表少數被執行到的行（`/api/auth`）都有被測到；79% 的 router 變異體落在從未執行的程式碼上。

### 依變異運算子

| 運算子 | 數量 | killed | survived | 無覆蓋 | 有覆蓋時被殺比例 |
|---|---:|---:|---:|---:|---:|
| 字串常數改寫（dict key、Mongo 欄位名、路徑…） | 1,234 | 453 | 432 | 349 | 51% |
| 數值 +1 / 改 0 | 496 | 107 | 257 | 132 | 29% |
| `return x` → `return None` | 302 | 174 | 13 | 115 | 93% |
| 刪除呼叫敘述 | 232 | 107 | 68 | 57 | 61% |
| 比較運算子（`==`↔`!=`、`<`↔`<=`、`in`↔`not in`…） | 218 | 138 | 50 | 30 | 73% |
| `True` ↔ `False` | 133 | 59 | 52 | 22 | 53% |
| 反轉 `if` 條件 | 129 | 79 | 28 | 22 | 74% |
| 移除 `not` | 124 | 80 | 15 | 29 | 84% |
| 刪除屬性 / 下標賦值 | 121 | 51 | 30 | 40 | 63% |
| 刪除 `raise` | 101 | 34 | 1 | 66 | 97% |
| `and` ↔ `or` | 67 | 35 | 21 | 11 | 62% |
| 算術運算子 | 63 | 27 | 18 | 18 | 60% |
| 其他（三元條件、`break`/`continue`、`+=`） | 32 | 12 | 9 | 11 | 57% |

`return None` 與刪除 `raise` 的被殺比例很高（93%、97%），代表「有沒有回傳東西」「有沒有拋錯」測得不錯；數值與字串常數的比例最低（29%、51%），代表**邊界值與欄位內容**幾乎沒被斷言。

<details>
<summary>依檔案（由低分到高分）</summary>

| 檔案 | 變異體 | killed | survived | 其中 high | 其中 medium | 無覆蓋 | score | 有覆蓋 score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `database/redis_conn.py` | 15 | 0 | 13 | 5 | 2 | 2 | 0% | 0% |
| `services/file_service.py` | 65 | 0 | 0 | 0 | 0 | 65 | 0% | — |
| `utils/ws_ticket.py` | 14 | 0 | 3 | 0 | 1 | 11 | 0% | 0% |
| `websocket/routes.py` | 6 | 0 | 0 | 0 | 0 | 6 | 0% | — |
| `routers/rooms.py` | 71 | 1 | 0 | 0 | 0 | 70 | 1% | 100% |
| `routers/notifications.py` | 43 | 1 | 0 | 0 | 0 | 42 | 2% | 100% |
| `routers/messages.py` | 26 | 1 | 0 | 0 | 0 | 25 | 4% | 100% |
| `security_config.py` | 86 | 3 | 77 | 0 | 21 | 6 | 5% | 5% |
| `utils/image_processor.py` | 116 | 7 | 21 | 0 | 11 | 88 | 6% | 25% |
| `routers/files.py` | 16 | 1 | 0 | 0 | 0 | 15 | 6% | 100% |
| `services/notification_service.py` | 100 | 13 | 1 | 0 | 1 | 86 | 13% | 93% |
| `websocket/auth.py` | 59 | 9 | 0 | 0 | 0 | 50 | 15% | 100% |
| `middleware/rate_limiting.py` | 234 | 43 | 117 | 13 | 5 | 74 | 19% | 28% |
| `routers/invitations.py` | 5 | 1 | 0 | 0 | 0 | 4 | 20% | 100% |
| `config.py` | 34 | 8 | 26 | 1 | 3 | 0 | 24% | 24% |
| `utils/file_upload.py` | 243 | 58 | 163 | 4 | 115 | 22 | 24% | 27% |
| `models/enums.py` | 8 | 2 | 6 | 0 | 5 | 0 | 25% | 25% |
| `routers/ws_ticket.py` | 4 | 1 | 0 | 0 | 0 | 3 | 25% | 100% |
| `core/exceptions.py` | 13 | 4 | 9 | 0 | 7 | 0 | 31% | 31% |
| `models/user.py` | 25 | 7 | 18 | 3 | 8 | 0 | 33% | 33% |
| `routers/ai.py` | 3 | 1 | 0 | 0 | 0 | 2 | 33% | 100% |
| `models/room.py` | 49 | 14 | 32 | 2 | 15 | 3 | 34% | 37% |
| `main.py` | 70 | 23 | 41 | 1 | 15 | 6 | 34% | 38% |
| `models/message.py` | 32 | 12 | 20 | 0 | 12 | 0 | 41% | 41% |
| `repositories/message_repository.py` | 156 | 63 | 29 | 0 | 11 | 64 | 41% | 72% |
| `auth/dependencies.py` | 37 | 15 | 7 | 2 | 0 | 15 | 43% | 75% |
| `services/room_service.py` | 205 | 94 | 57 | 8 | 32 | 54 | 48% | 66% |
| `websocket/handlers.py` | 318 | 157 | 114 | 12 | 26 | 47 | 50% | 59% |
| `models/notification.py` | 13 | 5 | 8 | 0 | 5 | 0 | 50% | 50% |
| `websocket/manager.py` | 171 | 91 | 57 | 1 | 26 | 23 | 54% | 63% |
| `database/mongodb.py` | 20 | 10 | 8 | 0 | 0 | 2 | 56% | 62% |
| `repositories/base.py` | 93 | 52 | 22 | 0 | 4 | 19 | 61% | 79% |
| `database/indexes.py` | 40 | 25 | 15 | 5 | 0 | 0 | 62% | 62% |
| `services/message_service.py` | 100 | 63 | 19 | 2 | 8 | 18 | 66% | 81% |
| `core/bot.py` | 48 | 32 | 8 | 0 | 2 | 8 | 67% | 80% |
| `middleware/error_handler.py` | 93 | 64 | 26 | 0 | 1 | 3 | 69% | 71% |
| `services/user_service.py` | 91 | 62 | 12 | 6 | 3 | 17 | 69% | 85% |
| `services/ai_service.py` | 31 | 22 | 7 | 0 | 3 | 2 | 71% | 76% |
| `repositories/user_repository.py` | 56 | 39 | 6 | 3 | 1 | 11 | 72% | 91% |
| `repositories/room_repository.py` | 126 | 88 | 18 | 3 | 3 | 20 | 74% | 89% |
| `middleware/security_headers.py` | 51 | 37 | 13 | 0 | 1 | 1 | 74% | 76% |
| `repositories/notification_repository.py` | 89 | 68 | 16 | 0 | 5 | 5 | 81% | 86% |
| `core/fastapi_integration.py` | 41 | 35 | 3 | 0 | 3 | 3 | 85% | 92% |
| `auth/password.py` | 7 | 6 | 0 | 0 | 0 | 1 | 86% | 100% |
| `routers/auth.py` | 43 | 38 | 0 | 0 | 0 | 5 | 88% | 100% |
| `utils/json_encoder.py` | 42 | 38 | 0 | 0 | 0 | 4 | 90% | 100% |
| `auth/jwt_handler.py` | 20 | 20 | 0 | 0 | 0 | 0 | 100% | 100% |
| `utils/datetime_utils.py` | 7 | 7 | 0 | 0 | 0 | 0 | 100% | 100% |
| `utils/user_cache.py` | 17 | 15 | 2 | 0 | 0 | 0 | 100% | 100% |

`utils/user_cache.py` 的 2 個存活者皆為等價變異體，故分數為 100%。

</details>

---

## 三、最需要補的缺口（依優先順序）

以下 `#編號` 對應附錄中的變異體；「無覆蓋」表示該函數從未被任何測試執行。每一項都附上「如果這段程式真的寫錯，使用者或攻擊者會遇到什麼」，以及應該擴充的既有測試檔。

### P0-1　認證與授權入口沒有任何測試執行

以下函數在整個測試套件中**一行都沒被執行過**（附錄「從未被任何測試執行的函數」）：

| 函數 | 保護的是什麼 |
|---|---|
| `auth/dependencies.py::require_room_membership` | 所有 `/api/rooms/{id}/...` 與訊息端點的成員檢查；PRIVATE 房非成員回 404 不洩漏存在 |
| `services/room_service.py::get_room_for_user` | `GET /api/rooms/{id}`：成員看完整資料、非成員看摘要、PRIVATE 房非成員 404 |
| `websocket/auth.py::websocket_auth_middleware`、`authenticate_websocket`、`_get_user_info`、`extract_token_from_query`、`authenticate_websocket_by_ticket` | WS 連線認證：停用帳號拒絕、token_version 比對、Bearer scheme 檢查 |
| `utils/ws_ticket.py::create_ws_ticket`、`validate_ws_ticket` | 一次性 ticket：`getdel` 原子消費、ticket 綁定 room_id、30 秒 TTL |
| `routers/*`（auth 以外全部） | 所有房間、訊息、通知、檔案、邀請、ws-ticket 的 HTTP 端點 |

只有 `verify_room_membership` 有測試（`tests/test_websocket/test_auth.py`）。

**建議：** 新增 `tests/test_api/test_rooms_api.py`、`test_messages_api.py`，用既有的 `async_client` 走完整 HTTP 路徑——非成員讀 PUBLIC 房訊息應 403、讀 PRIVATE 房應 404、成員應 200；`tests/test_websocket/test_auth.py` 補 `websocket_auth_middleware` 的 ticket / token / 停用帳號 / 改密碼後舊 token；新增 `tests/test_utils/test_ws_ticket.py` 驗證第二次使用回 `None`、room 不符回 `None`。

### P0-2　「改密碼後舊 token 立即失效」整條鏈沒有被驗證

| 變異體 | 改壞的地方 | 後果 |
|---|---|---|
| #1355、#1340、#1319 | `user_repository.update` 的 `$inc: {"token_version": 1}` 欄位名、整行、或條件 | 改密碼後版本不遞增，**被竊的舊 token 永久有效** |
| #25、#29 | `dependencies.py` 讀取 token / 使用者的 `token_version` | 版本比對形同停用 |
| #2226 | `update_user` 改密碼時不 bump 版本 | 透過 `PUT /api/auth/profile` 改密碼不撤銷舊 token |
| #2174、#2177 | 更新 / 刪除使用者後不清 Redis 快取 | 舊 token 在快取 TTL（5 分鐘）內仍有效；刪除的帳號仍能登入 |
| #2229、#2243、#2254 | 登入 / refresh 簽發的 token 版本 | 改過密碼的使用者重新登入後每個請求都 401 |
| #2218、#2219 | `refresh_access_token` 的停用帳號檢查 | 停用帳號可無限換發 token |

另外 `user_service.change_password`（`PUT /api/auth/change-password` 的實作）**從未被執行過**。現有的 `test_update_user_profile_with_password` 只斷言 200。

**建議：** 在 `tests/test_api/test_auth_api.py` 寫一個端到端測試：登入 → 以舊 token 打 `/api/auth/me` 暖快取 → 分別走 `PUT /profile` 與 `PUT /change-password` 改密碼 → 斷言舊 access token 與舊 refresh token 都回 401 → 重新登入的 token 回 200；另測只改 `full_name` 時原 token 仍有效、`DELETE /profile` 後原 token 被拒。這一個測試可殺死上表大部分變異體。

### P0-3　房間存取規則改壞不會被發現

| 變異體 | 改壞的地方 | 後果 |
|---|---|---|
| #1971、#2083 | `_convert_to_response` 的邀請碼遮蔽條件 | 一般成員拿到私人房的 `invite_code`，可轉給外人加入 |
| #2145 | `join_room` 邀請碼檢查 `or` → `and` | 空 body `{}` 即可加入沒有邀請碼的邀請制房 |
| #2002 | 私人房強制 INVITE 的條件 | 私人房可用密碼加入；公開房反而變邀請制 |
| #2004、#2029、#2097 | `is_public` ↔ `room_type` 同步 | 私人房出現在探索與搜尋列表；只改名就把公開房變私人 |
| #1297、#1307 | `add_member` 的 `$expr: {$lt: [{$size: "$members"}, "$max_members"]}` | 原子保底失效，併發加入可超過 `max_members` |
| #1222 | `room_repository.update` 的 `password_hash is not None` | 改房間密碼後舊密碼仍有效；改描述就清空密碼 |
| #2118 | 房名唯一性檢查 `!=` → `==` | 房主儲存設定永遠 409；改成別房名稱反而不被 service 攔截 |

現有房間服務測試大多只確認 repository 被呼叫，`test_update_room_success` 比對的是同一個被原地修改的 `update_data` 物件，因此看不到同步邏輯被改壞。

**建議：** `tests/test_services/test_room_service.py` 以 OWNER / ADMIN / MEMBER 三種角色斷言 `invite_code` 是否為 `None`；`join_room` 對 `None` 與 `RoomJoinRequest()` 都斷言拋錯；斷言傳給 `repo.create` / `repo.update` 的 `is_public` 與 `room_type` 一致。`tests/test_repositories/test_room_repository.py` 補「已滿房間 `add_member` 回 `False` 且 `members` 不變」與密碼更新 / 保留的往返測試。

### P0-4　限流可以被整個關掉而測試全綠

`RateLimitingMiddleware.dispatch` 的 catch-all 會吞掉任何錯誤並放行請求（fail-open），而 `async_client` fixture 把 `_should_skip_rate_limiting` patch 成 `True`、測試又固定 `DEBUG=True`。結果：

- 刪掉 `main.py` 的 `app.add_middleware(RateLimitingMiddleware, ...)`（#278）——全綠
- 以 `None` 建 limiter（#445）、初始化永遠失敗（#470、#472、#506–#509）、設定鍵讀錯（#653、#654）、跳過條件反轉（#467、#468）、非精確路徑查表錯（#464）——全部 fail-open 放行，全綠
- 生產環境套用 DEBUG 的寬鬆限流表（#446）——全綠
- burst 視窗 `now - 60` 的 60 秒改成 0 秒（#514），burst 限制退化成只計同一秒內的請求——全綠
- Redis 連線鏈任何一處壞掉（#260、#262、#264、#265、#268）：app 照常啟動、限流全停、`/api/ws-ticket` 全回 500——全綠，因為 conftest 只把 `init_redis` 失敗記成 warning，而計數測試在 Redis 不可用時 `pytest.skip`
- @bot 每分鐘限流的視窗改成 0（#2986）：fail-open，付費 LLM 可被無限呼叫

`dispatch` 有 19 個變異體、生產限流表整段（`__init__` 的 `else` 分支）有 52 個變異體從未被執行。

**建議：** `tests/test_middleware/test_rate_limiting.py` 新增 dispatch 層測試：最小 Starlette app 掛 `RateLimitingMiddleware(settings=Settings(DEBUG=False))` 與真實 Redis，連打 `/api/auth/login` 斷言第 N+1 次回 429；斷言 `/health` 以外的路徑不會被 skip；用 `caplog` 斷言沒有走進 fail-open 分支；Redis 不可用時應 fail 而不是 skip。

### P0-5　檔案上傳 / 下載

- `services/file_service.py` 的 65 個變異體**全部無覆蓋**：包括 `_validate_path_within`（`resolve()` + `is_relative_to` 的路徑穿越防護）、`_validate_filename`、`resolve_download`、`resolve_thumbnail`。`tests/test_services/test_file_handling.py` 全部以 mock 取代。
- 存檔內容沒有被驗證（#2336、#2500、#2422）：刪掉 `seek(0)` 或寫入，所有上傳檔案會少掉前 16 bytes 或變成 0 bytes，API 仍回 201。現有測試只斷言檔案 `exists()`。
- 唯一檔名的隨機段變空字串（#2478）：同一秒上傳同副檔名的兩個檔案會互相覆寫。
- `_MAGIC_SIGNATURES` 19 個副檔名中只有 `.jpg`、`.webp` 被測到（#2279–#2296）：任一項被移除就等於該副檔名不檢查檔頭。

**建議：** `tests/test_services/test_file_handling.py` 加一個不 mock 的整合測試（`tmp_path`）：上傳 → `resolve_download` 找回同一個檔案、內容 bytes 相同；`resolve_download("image", "../../etc/passwd")` 應拋錯。`tests/test_utils/test_file_upload_security.py` 對 `_MAGIC_SIGNATURES` 每個鍵做參數化（偽造內容回 `False`、真實檔頭回 `True`），並斷言鍵集合涵蓋所有允許的副檔名。

### P0-6　密碼長度政策沒有被測

把 `UserCreate`、`UserUpdate`、`PasswordChange`、`RoomCreate`、`RoomUpdate` 的 `min_length=6` 改成 0（#840、#842、#849、#803、#816）全部存活——空字串或 1 個字元的密碼都能註冊或設定。原因是 `test_register_with_weak_password` 的斷言是 `status_code in [201, 400, 422]`，**這個測試不可能失敗**。

**建議：** 改成 5 個字元 → 422、6 個字元 → 201 的邊界測試，並對其他四個模型做同樣的參數化。

### P1-1　訊息序號、斷線補發與冪等

- `message_repository` 的 `next_room_seq`（原子取號）、`get_by_client_id`（冪等去重）、`get_after_seq` / `count_after_seq`（斷線補發）、`get_reply_previews`、`delete_by_room_id` **從未對真實 MongoDB 執行過**——service 測試全部 mock 掉了。
- `handlers.send_gap_messages` 從未執行；重連的 `last_seq` 參數名改壞（#2873）或補發呼叫被刪（#2824），使用者斷線期間超過 50 則的訊息會永久消失；`and` → `or`（#2823）讓沒帶 `last_seq` 的首次連線直接拋例外被關閉。
- gap 超過 200 時的全量重載 skip / limit（#1843、#1845）、即時廣播缺 `seq`（#2815）也都存活。

**建議：** `tests/test_repositories/test_message_repository.py` 對真實 DB 測 `next_room_seq` 連續遞增、併發 `asyncio.gather` 不重號、同一 `client_id` 只存一筆；`tests/test_websocket/test_handlers_additional.py` 以真的 `query_params` 測無 `last_seq`、`last_seq=abc`、`last_seq=5` 三種情況。

### P1-2　即時廣播與 WebSocket 協定

- #3212：`_execute_room_leave` 的 `if not self.room_users[room_id]` 拿掉 `not`——使用者切換房間 5 秒後，若原房間還有人，**整個房間的廣播名單被刪除**，其他人再也收不到訊息。
- #2877：前端實際送的是 `type: "message"`（`frontend/src/lib/websocket/manager.ts`），但後端測試只用 `chat_message`；這個別名被改壞時所有人都無法發言。
- #2881、#2782、#2975、#2981、#2976：`client_id` 讀不到或 ack 沒送出 / 格式錯——前端 10 秒後判定失敗並重試，每次重試都產生一則重複訊息。
- 即時訊息 payload 的 content、username、user_id、created_at、metadata、avatar 欄位（M1 群組，見附錄）、`user_joined` / `user_left` / 在線狀態事件的 payload：現有測試大多只檢查 `send_*` 的 `call_count`。

**建議：** `tests/test_websocket/test_connection_manager.py` 兩人同房、一人離開後推進 debounce，斷言另一人仍在 `room_users` 且收得到廣播；`test_handlers_additional.py` 參數化 `type` 為 `message` / `chat_message`，並對 ack 與廣播 payload 做完整等值斷言。

### P1-3　唯一索引與 collection 的耦合

`tests/test_database/test_indexes.py` 以 mock 只斷言 `create_index` 的呼叫次數與 `unique=True`，不看索引鍵。把 `username`、`email`、房間 `name`、`invite_code`、訊息 `(room_id, client_id)` 的索引鍵改成不存在的欄位（#219、#220、#228、#229、#226）全部存活——唯一性保底消失，而且所有文件在該欄位都是 null，第二位使用者註冊、第二間有邀請碼的房間就會撞鍵。repository 的 collection 名稱改掉（#1006、#1248）也一樣不會被發現。

**建議：** 對真實 Mongo 執行 `ensure_indexes()` 後比對 `index_information()` 的 key 與 `unique`；斷言各 repository 的 `collection.name`。

### P2　API 契約與設定（中風險，逐項見附錄）

- **錯誤狀態碼**：`AppError` 400、`NotFoundError` 404、`ForbiddenError` 403 改成其他值都存活（#146–#154）——service 測試用 `pytest.raises` 只看例外類別，HTTP 層又沒有對應測試。
- **路由接線**：刪掉 `main.py` 中 auth 以外任一個 `include_router`（#280、#282–#288）或 `GlobalErrorHandler`（#279）都存活。一個斷言 `app.routes` 含各前綴的冒煙測試即可。
- **Pydantic 輸入邊界**：房名長度、描述長度、`max_members` 2–1000、使用者名稱 3–50、訊息長度等 `Field` 限制全部沒有邊界測試。`tests/test_models/test_data_validation.py` 在檔案裡**自己定義模型**，沒有 import `app.models`。另外 `RoomUpdate` 與 `RoomInDB` 的限制若不一致（#807、#809、#812、#813），房主可寫入讀不回來的資料，讓含該房間的列表頁對所有人 500。
- **列舉字串值**（`"public"`、`"invite"`、`"text"`、`"unread"`…）：改了只要後端自洽就不會被發現，但會打破前端契約與既有資料。
- **生產安全標頭**：`main.py` 實際把 `security_config.get_security_headers()` 當作 `custom_headers` 覆蓋 middleware 預設值，但測試只對 `SecurityHeadersMiddleware` 類別做單元測試，因此生產環境實際送出的 CSP / `X-Frame-Options` / HSTS 改壞不會被發現（`security_config.py` 有覆蓋 score 僅 5%）。
- **安全預設**：`Settings.DEBUG` 預設值從 `False` 改成 `True`（#89）存活——部署時忘了設 `DEBUG` 就會以寬鬆限流、`CORS *`、錯誤細節外洩的模式運作。
- **通知統計**：`$sum: 1` 改成 2（#1184、#1186）存活，因為 `test_get_stats` 全部用 `>=` 斷言。

---

## 四、測試套件本身的問題

變異測試同時揭露了幾個「看起來有測、其實沒測」的測試：

| 測試 | 問題 | 第二輪 |
|---|---|---|
| `tests/test_api/test_auth_api.py::test_register_with_weak_password` | 斷言 `status_code in [201, 400, 422]`，不可能失敗 | ✅ `60f89e2` |
| `tests/test_auth/test_auth_system.py::test_refresh_access_token_inactive_user` | `Mock()` 使用者沒有設 `token_version`，即使停用帳號檢查被拿掉，後面的版本比對也會拋同一個例外——測試因錯誤的原因通過 | ✅ `60f89e2` |
| `tests/test_security/test_security_features.py`（10 個測試） | 沒有 import 任何 `app` 模組，測的是測試檔內自己寫的邏輯 | ✅ `60f89e2` |
| `tests/test_models/test_data_validation.py` | 在檔案內自行定義模型，沒有測 `app.models` | ✅ `60f89e2` |
| `tests/test_database/test_indexes.py` | 只數 `create_index` 呼叫次數，不檢查索引鍵 | ✅ `60f89e2` |

另外有三個結構性因素讓大量變異體存活：

1. **測試永遠在 `DEBUG=True` 下執行**，生產分支（限流表、CORS、TrustedHost、錯誤細節隱藏、HSTS）從未被執行。第二輪：限流與安全標頭已改以生產設定測試；CORS / TrustedHost 尚未。
2. **conftest 吞掉 Redis 初始化錯誤、限流計數測試在 Redis 缺席時 skip**——Redis 整個沒連上時 CI 仍是綠的。第二輪：限流測試已改為 Redis 不可用即失敗；conftest 仍吞錯。
3. **WS / service 測試多以 `call_count` 斷言**，沒有斷言送出去的 payload 內容。第二輪：尚未處理。

---

## 五、判讀過程中發現的現存問題（非變異體）

以下是第一輪時程式碼本身的行為，已逐一對照原始碼確認。第二輪處理狀態：#1～#3 已修正（`9d28a63`、`89d94f0`、`75bc5af`），#4 於第四輪採方案 (a) 修正（`2b8c1fe`）；補測時另外發現並修正的 4 個問題見第〇節。

1. **`PUT /api/auth/profile` 可以不驗證目前密碼直接改密碼。** `UserUpdate` 含 `password` 欄位，`user_service.update_user` 會直接雜湊寫入；BFF（`frontend/src/routes/api/auth/profile/+server.ts`）原樣轉發 body。`/change-password` 要求的「目前密碼」因此可被繞過——拿到一個已登入的 session（共用電腦未登出、XSS）就能改掉密碼、接管帳號。建議 `UserUpdate` 移除 `password`，密碼一律走 `change_password`。
2. **上傳的副檔名白名單可用客戶端宣稱的 MIME 繞過。** `FileUploadManager.get_file_type` 是 `_EXT_TO_TYPE.get(ext) or _MIME_TO_TYPE.get(client_mime)`，而 `_matches_magic` 對沒有簽章的副檔名直接回 `True`。`evil.html` 帶 `Content-Type: image/png` 會被當成圖片存成 `uploads/image/<ts>_<id>.html`。全站的 `X-Content-Type-Options: nosniff` 加上下載時回 `application/octet-stream`，讓瀏覽器不會把它當 HTML 執行，但白名單本身已失效。建議副檔名不在表中時直接拒絕。
3. **`backend/.env` 裡的 `SECURITY_*` 設定不會生效。** `security_config.load_security_config()` 用 `os.getenv` 讀取，但 pydantic-settings 只把 `.env` 載入 `Settings` 欄位、不會寫進 `os.environ`，而 `SECURITY_*` 不是 `Settings` 欄位。`backend/.env.example` 列出的這些設定只有透過真正的環境變數設定才有效。
4. **（疑似，未在 UI 實測）房間改成私人或邀請制時不會產生邀請碼。** `update_room` 只同步 `is_public` / `room_type`，不調整 `join_policy`、不產生 `invite_code`。把「公開 + 直接加入」的房間改成私人後，`join_room` 的 DIRECT 分支要求公開房、又沒有邀請碼，看起來會變成沒有人能加入。

次要觀察：BFF 的上傳 MIME 白名單（`frontend/src/routes/api/files/+server.ts`）比後端窄（缺 `.bmp`、`.md`、`.mkv`、`.m4a`、`.flac`），且 `general` 類型完全不檢查；縮圖端點固定回 `media_type="image/png"`。

---

## 六、建議的補測順序

依「一個測試能殺死多少高風險變異體」排序（狀態為第二輪）：

1. ✅ **改密碼端到端測試**（P0-2）——一個 API 測試就能覆蓋 token 撤銷鏈十餘個變異體，並第一次執行 `change_password`。
2. ✅ **rooms / messages 的 HTTP 測試**（P0-1、P2）——讓 `require_room_membership`、`get_room_for_user`、全部 router 本體、錯誤狀態碼第一次被執行。
3. ✅ **WebSocket 認證與 ws ticket 測試**（P0-1）。
4. ✅ **限流 dispatch 測試（`DEBUG=False`、真實 Redis、不 skip）**（P0-4）——殺死 13 個高風險變異體與生產限流表。
5. ✅ **修正第四節的 5 個缺陷測試**——改動小，直接殺死密碼長度、停用帳號 refresh、索引鍵等變異體。
6. 🟡 **房間服務的角色 / 策略斷言**（P0-3，已完成）與 **`message_repository` 真實 DB 測試**（P1-1，未處理）。
7. 🟡 **檔案服務整合測試**（P0-5）——上傳管理器已測，`file_service` 未處理。
8. 🟡 **WS payload 快照與 Pydantic 邊界參數化**（P1-2、P2）——Pydantic 邊界已測，WS payload 未處理。

第二輪的建議見第〇節「建議的下一批」。

---

## 七、方法

### 為什麼不用 mutmut

mutmut 3 以 trampoline 包裝函數：會跳過帶 decorator 的函數（本專案所有 FastAPI 路由、Pydantic validator）、不變異 class 層級常數（`Field(max_length=...)` 等業務限制），且其包裝可能干擾 FastAPI 依簽名做的依賴注入；加上測試共用同一個 MongoDB 資料庫，平行執行會互相干擾。因此自行實作 [`backend/scripts/mutation_test.py`](../backend/scripts/mutation_test.py)。

### 流程

1. **產生變異體**：以 AST 定位節點，對原始碼做位元組精準的替換，再重新 parse 並確認 AST 與預期的變異 AST 完全一致（0 個被丟棄）。排除：docstring、log 呼叫、f-string、型別註記、import、含非 ASCII 的字串（給人看的訊息）、`description` / `title` 等文件用參數。
2. **對應測試**：以 `pytest --cov-context=test` 取得每一行被哪些測試執行；每個變異體只跑覆蓋其所在行的測試（decorator / 預設值對應該函數本體）。只在 import 期執行的 module / class 層級程式碼（477 個變異體）跑全套 496 個測試。
3. **隔離**：4 個 worker 各有獨立的 backend 複本、MongoDB 資料庫名稱與 Redis DB 編號。worker 預載第三方套件後，每個變異體 fork 子程序在行程內跑 pytest，父程序從不 import `app`，並停用 bytecode 寫入以避免同大小、同 mtime 的變異被舊 `.pyc` 遮蔽。
4. **判定**：測試失敗、收集錯誤、或變異讓 app 在 import 時崩潰 → killed；全部通過 → survived；逾時（預估時間 × 2.5 + 20 秒）→ killed（本次 0 個）。

### 正確性驗證

- 基準：496 個測試全套通過，且**逐一單獨執行也全部通過**（排除順序相依造成的假 killed）。
- 執行結束後 4 個 worker 的 `app/` 與原始碼逐檔比對一致。
- 隨機抽 5 個存活者，以全新目錄、一般 `pytest` subprocess（不經 fork-server）重跑，結果 5/5 一致。
- 整理後提交的工具重跑 40 個隨機變異體，測試選擇與判定結果 40/40 與正式執行一致。
- 共 75 分鐘完成（4 核心）；0 個逾時、0 個執行錯誤。
- 第二輪以提交的工具 `all` 指令完整重跑：785 個測試逐一單獨執行皆通過，35.6 分鐘，0 個逾時、0 個執行錯誤。
- 第三輪同樣以 `all` 完整重跑：959 個測試逐一單獨執行皆通過，27 分鐘，1 個逾時、0 個執行錯誤。
- 第四輪同樣以 `all` 完整重跑：976 個測試逐一單獨執行皆通過，28 分鐘，1 個逾時、0 個執行錯誤。
- 第五輪同樣以 `all` 完整重跑：1,008 個測試逐一單獨執行皆通過，28 分鐘，1 個逾時、0 個執行錯誤。
- 第六輪同樣以 `all` 完整重跑：1,047 個測試逐一單獨執行皆通過，28 分鐘，1 個逾時、0 個執行錯誤。

### 存活者判讀

994 個存活者分成 4 個領域，由 4 個平行審查各自對照原始碼、測試與前端使用方逐一分類（高 / 中 / 低 / 等價），再由人工複核所有高風險項目。複核時調降 25 個：collection 名稱改寫（#1006、#1248）、Pydantic 模型間的限制不一致（#790 等 6 個）、magic 簽章表的鍵（17 個，有 `nosniff` 與正確 MIME 緩解）改列中風險。分類為主觀判斷，等價變異體尤其可能有誤判。

第二輪的 686 個存活者中，程式碼未變的沿用第一輪分類（依檔案、函數、運算子與變異前後內容比對）；本輪才出現的（多為原本從未執行、這次才被執行到的程式碼）為人工判讀。

第三輪的 246 個存活者中，132 個沿用第二輪分類；114 個為人工判讀：113 個本輪才出現的存活者，加上 1 個在本輪修改過的函數裡被簽名比對誤配的延用結果。

第四輪的 218 個存活者中，212 個沿用第三輪分類（簽名相同時再依行序配對，避免誤配）；6 個本輪才出現的為人工判讀。

第五輪的 186 個存活者中，180 個沿用第四輪分類；6 個為人工判讀：5 個本輪才出現的存活者，加上 1 個複核後由低價值改判等價的延用結果。複核時另發現 1 個自第二輪起延用的等價判讀有誤（`find_many` 的 tiebreaker 欄位，見「第五輪」一節）。

第六輪的 145 個存活者全部沿用第五輪分類；複核後改判 1 個（#159，中風險改為等價），並更正 1 個等價判讀的說明（`main.py` 的 CORS 比較）。

### 限制

- 前端沒有測試，未納入。
- AI 供應商（NVIDIA NIM / Gemini）在測試中以 pydantic-ai 的 `FunctionModel` / `TestModel` 取代。
- 每個變異體只跑「覆蓋該行的測試」：若某測試沒執行到該行、卻能透過其他途徑偵測到變異，會被低估（實務上極少見）。第五、六輪都有 2 個：路由參數的上限（`le=100`）只有被 FastAPI 驗證擋下的請求（回 422）能偵測，而這種請求不會執行路由函數本體。
- 字串變異排除了含中文的訊息，因此錯誤訊息文字的正確性不在統計內。

---

## 八、如何重跑

需先啟動與測試相同的 MongoDB（`mongodb://root:password@localhost:27017`）與 Redis（`localhost:6379`），見 `backend/tests/test_config.py`。

```bash
cd backend
python scripts/mutation_test.py all --workers 4     # 全流程，4 核約 30 分鐘

# 或分步執行（run 可中斷後續跑）
python scripts/mutation_test.py gen
python scripts/mutation_test.py coverage
python scripts/mutation_test.py setup --workers 4
python scripts/mutation_test.py baseline --workers 4
python scripts/mutation_test.py plan
python scripts/mutation_test.py run --workers 4
python scripts/mutation_test.py report             # 輸出 backend/.mutation/report.md
```

工作目錄 `backend/.mutation/` 已加入 `.gitignore`。`gen` 會清掉上一次的執行結果；要保留上一輪的資料作比較，請在重跑前先把目錄移走。worker 透過環境變數 `TEST_DATABASE_NAME`、`TEST_REDIS_URL` 使用 MongoDB 資料庫 `test_chatroom_mut{i}` 與 Redis DB `2 + i`。
