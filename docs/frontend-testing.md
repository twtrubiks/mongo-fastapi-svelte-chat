# 前端測試報告

> 對象：`frontend/src`（SvelteKit BFF 路由、`$lib` 的 BFF 模組、API client、stores、WebSocket 事件處理）
> 日期：2026-10-24　工具：Vitest 5（`npm run test`；`npm run check:all` 最後也會跑）

在這之前前端沒有任何自動化測試。這一輪從 BFF 路由與 stores 開始補測，共 16 個測試檔、278 個測試。補測時找到的問題以 10 個 commit 修正（儀表板與日期兩項各含兩個相關問題），每個修正都有對應的測試，並確認該測試在修正前會失敗。

---

## 測試範圍

| 範圍 | 測試檔 | 作法 |
|---|---|---|
| BFF 核心：`bff-utils`、`bff-client`、`bff-auth` | `src/lib/bff-*.test.ts` | `bff-client` 以真實 HTTP server 扮演後端；`bff-auth` 驗證透明換發 token、401 重試、並行去重 |
| BFF 路由：29 個 `+server.ts` 全部 | `src/routes/api/**/server.test.ts` | 直接呼叫 handler；以 spy 取代 `bffBackendClient.request`，依 `METHOD endpoint` 分派，未列出的端點一律 404 |
| 瀏覽器端 API client | `src/lib/api/client.test.ts` | 以真實 HTTP server 扮演 BFF，驗證信封解包、BFF 錯誤、401 判斷 |
| Stores：auth、message、room、notification | `src/lib/stores/*.test.ts` | 直接操作 store，API 以 `vi.spyOn` 取代 |
| WebSocket 事件處理 | `src/lib/websocket/handlers.test.ts` | 以後端實際推送的 payload 驅動 handler，檢查 store 結果 |
| 日期工具 | `src/lib/utils/datetime.test.ts` | 在 `Asia/Taipei` 時區下執行 |

共用工具在 `src/tests/bff.ts`：假 Cookies、未簽章 JWT、RequestEvent 與後端 spy。

---

## 修正的問題

| 問題 | 影響 | commit |
|---|---|---|
| BFF 用 `atob` 解 JWT，但 JWT 是 base64url。使用者名稱如 `abc?` 會在 payload 產生 `_`，解析失敗後被當成「已過期」 | 該使用者每個 BFF 請求都會先呼叫 `/api/auth/refresh` | `b186990` |
| FastAPI 欄位驗證失敗時 `detail` 是陣列，BFF 直接當成 `message`；限流的 `{error, message}` 也取不到訊息 | 前端 ApiClient 只認字串訊息，使用者只看到「Request failed with status code 422」 | `609f155` |
| 儀表板把 `/api/notifications/unread` 回傳的 `{notifications, unread_count}` 當陣列；房間用 `/api/rooms`（含未加入的公開房間） | 儀表板未讀數永遠是 0、通知清單永遠是空的；「已加入的房間」數量與清單不正確 | `532d09b` |
| 通知列表 BFF 把前端大寫的 `status` / `type` 原樣轉給後端，後端只認小寫 | 會回 422。目前沒有呼叫端帶這兩個參數，屬潛在問題 | `ea5f8a8` |
| 登入 / 註冊被限流（429）時，BFF 一律回 500「登入失敗」 | 使用者不知道是嘗試次數過多 | `9bac2f5` |
| 上傳 BFF 另外維護一份較短的 MIME 白名單 | 前端與後端都接受的 `.mov`（iPhone 影片）、`.bmp`、`.mkv`、`.avi`、`.md`、`.m4a`、`.flac` 在 BFF 被擋 | `42c42b8` |
| ApiClient 先丟出 BFF 錯誤，才判斷 401 呼叫 `onAuthFailure`；受保護路由的 401 都是 BFF 格式，所以從未觸發。觸發時也只登出不換頁 | refresh token 過期或被撤銷（例如在別的裝置改密碼）後，使用者留在 `/app`，每個操作都失敗 | `9e7c8d5` |
| `loadMoreMessages` 先設 `loading = true`，列表為空時才 return | 第一頁載入失敗後捲到頂端，載入動畫一直轉 | `4520e6b` |
| 探索列表以 offset 分頁，從列表加入房間或房間被刪除後 offset 沒有扣回 | 下一頁會漏掉一個房間，直到重新整理 | `80c41b7` |
| 訊息日期分隔線以 UTC 日期分組；`normalizeTimeString` 用 `includes('-')` 判斷時區，日期本身就含 `-` | 台灣凌晨 0～8 點的訊息出現在前一天的分隔線下；缺時區的字串不會補 `Z`（後端目前都帶時區） | `049e42b` |

另外 `Toast.svelte` 的計時器型別改為 `ReturnType<typeof setTimeout>`（`a19738c`），加入 Node 型別後 `setTimeout` 的回傳值不再是 `number`。

---

## 端對端驗證

單元測試把後端 mock 掉，因此另外以真實 MongoDB、Redis、FastAPI 與 `vite dev` 跑一次，經 BFF（Playwright）驗證以上修正，10 項全部通過：

- 使用者 `abc?` 連續 5 次請求，後端沒有收到 `/api/auth/refresh`
- 註冊時 email 格式錯誤回 422，`error.message` 是字串
- 寫入 3 則未讀通知後，儀表板未讀數為 3、通知為前端格式、房間只列已加入的
- 經 BFF 上傳 `.mov` 與 `.md`，後端接受
- 在瀏覽器登入並停在房間頁，從另一個 session 改密碼：頁面自動回到 `/login`，`localStorage` 的使用者資料已清除。把 `client.ts` 與 `auth.svelte.ts` 換回修正前的版本重跑，頁面停在房間頁，本地資料也還在
- 連續登入失敗直到限流，BFF 回 429「嘗試次數過多，請稍後再試」

---

## 尚未涵蓋

- **Svelte 元件**：沒有元件測試。
- **WebSocket 連線管理**（`websocket/manager.ts`）：連線、重連、心跳、ack 逾時都沒有直接測試。覆蓋率工具把這個檔案算成 98%，但測試只有在 import 時執行了建構子，這個數字不可信。
- **`bff-api-client.ts`**：儀表板、進階加入、上傳與邀請碼驗證使用的 fetch client，約 19%。
- **工具函式**：`messageRetry`、`markAsRead`、`retry`、`fileUploadHandler`、`notificationSound`、`readStatusSync`、`roomListSync` 等大多未測。
- **相依套件的安全通報**：`npm audit` 回報 axios 與 `@sveltejs/kit` 有已知漏洞，在這次變更之前就已存在，沒有處理。

以 `@vitest/coverage-v8` 量測（未加入專案相依）：BFF 路由與 `bff-*` 模組的行覆蓋率多在 80～100%，message store 93%，`utils` 整體約 24%。
