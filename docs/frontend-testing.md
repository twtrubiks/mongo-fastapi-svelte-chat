# 前端測試報告

> 對象：`frontend/src`（SvelteKit BFF 路由、`$lib` 的 BFF 模組、API client、stores、WebSocket 事件處理）
> 日期：2026-10-24　工具：Vitest 5（`npm run test`；`npm run check:all` 最後也會跑）、Playwright（`npm run test:e2e`）

在這之前前端沒有任何自動化測試。第一輪從 BFF 路由與 stores 開始補測（16 個測試檔、278 個測試），找到的問題以 10 個 commit 修正（儀表板與日期兩項各含兩個相關問題）。第二輪補上 WebSocket 連線管理的測試，並處理快速切換房間的競態與套件的安全通報。第三輪補上訊息重試與房間已讀的測試，並把瀏覽器端對端驗證整理成 `npm run test:e2e`。目前共 19 個測試檔、320 個單元測試，另有 6 個端對端測試。每個修正都有對應的測試，並確認該測試在修正前會失敗；房間頁的修正沒有元件測試，由端對端測試涵蓋。

---

## 測試範圍

| 範圍 | 測試檔 | 作法 |
|---|---|---|
| BFF 核心：`bff-utils`、`bff-client`、`bff-auth` | `src/lib/bff-*.test.ts` | `bff-client` 以真實 HTTP server 扮演後端；`bff-auth` 驗證透明換發 token、401 重試、並行去重 |
| BFF 路由：29 個 `+server.ts` 全部 | `src/routes/api/**/server.test.ts` | 直接呼叫 handler；以 spy 取代 `bffBackendClient.request`，依 `METHOD endpoint` 分派，未列出的端點一律 404 |
| 瀏覽器端 API client | `src/lib/api/client.test.ts` | 以真實 HTTP server 扮演 BFF，驗證信封解包、BFF 錯誤、401 判斷 |
| Stores：auth、message、room、notification | `src/lib/stores/*.test.ts` | 直接操作 store，API 以 `vi.spyOn` 取代 |
| WebSocket 事件處理 | `src/lib/websocket/handlers.test.ts` | 以後端實際推送的 payload 驅動 handler，檢查 store 結果 |
| WebSocket 連線管理 | `src/lib/websocket/manager.test.ts` | 以假的 WebSocket 與 fake timers 驗證連線、指數退避重連、關閉代碼、重連上限、心跳（含分頁切回前台）、ack 逾時與重疊的連線請求 |
| 訊息重試 | `src/lib/utils/messageRetry.test.ts` | 搭配真的 WebSocketManager 與假的 WebSocket：ack 逾時後重試、重試後再次逾時、重新連線後自動重送、檔案訊息重試 |
| 房間已讀 | `src/lib/utils/markAsRead.test.ts` | 進房延遲與取消、新訊息 debounce、只標記該房間的未讀通知 |
| 日期工具 | `src/lib/utils/datetime.test.ts` | 在 `Asia/Taipei` 時區下執行 |
| 端對端 | `tests/e2e/*.spec.ts` | Playwright 經由 BFF 連到真的後端，見下方「端對端驗證」 |

共用工具在 `src/tests/`：`bff.ts` 提供假 Cookies、未簽章 JWT、RequestEvent 與後端 spy；`deferred.ts` 讓測試決定回應完成的先後；`fakeWebSocket.ts` 讓測試決定 WebSocket 何時開啟、收到訊息與關閉。

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

### 第二輪

| 問題 | 影響 | commit |
|---|---|---|
| `WebSocketManager.connect()` 先等 ticket 才遞增連線編號；只關閉 OPEN 的舊連線；舊連線的連線逾時與 error 事件依共用狀態判斷 | 較早發出、較晚拿到 ticket 的請求會把新房間的連線換回舊房間；仍在連線中的舊連線開啟後留在背景；舊連線的 10 秒逾時會關掉正在連線的新連線 | `64a8a79` |
| ping 逾時後只呼叫 `ws.close(4000)`，靠 `onclose` 重連，但 `onclose` 只在 `wasClean` 為 false 時重連 | 伺服器還在時會完成關閉握手，連線斷了卻不重連；連線真的中斷時，要等關閉握手逾時才重連 | `0b230fc` |
| 房間頁 `loadRoom` 每次 await 後沒有確認使用者是否還在同一個房間；message / room store 會寫入較晚回來的舊回應 | 先點房間 A、馬上切到 B，A 的回應較晚回來時，網址停在 B，標題、訊息與 WebSocket 卻是 A，**在 B 頁面送出的訊息寫進 A** | `5b98e5c` |
| 房間頁「未登入就導向 /login」的 effect 在 `checkAuthentication` 驗證 cookie 前就執行 | cookie 有效但 localStorage 沒有使用者資料時，直接開啟的房間連結被經 `/login` → `/app/rooms` 帶到第一個房間 | `75673d3` |

套件升級（`dfff4b7`）：`npm audit fix` 並提高直接相依的最低版本，axios 1.18.1 → 1.20.0、`@sveltejs/kit` 2.67.0 → 2.70.3、devalue 5.8.1 → 5.9.4、vite 8.1.0 → 8.3.5 等，high 等級的通報全部清除。

### 第三輪

| 問題 | 影響 | commit |
|---|---|---|
| `startHeartbeat()` 不會先停掉既有的心跳；連線開啟與分頁切回前台都會呼叫它 | 在背景開啟或重連的分頁切回前台後，每 20 秒送兩次 ping，多出的那組在斷線、切換房間後仍在跑。兩次 ping 落在同一個來回時間內時，正常的連線會被當成 ping 逾時強制重連 | `e809cc0` |
| 重試把訊息寫入 socket 後就移出重試佇列，不等 ack；手動重試沒有真的重置次數 | 重試後仍沒收到 ack 的訊息再次顯示失敗，但按「重試」沒有作用，失敗提示跟著消失，訊息停在傳送中 | `30c8611` |
| 重試佇列沒有存檔案訊息的 metadata | 上傳後第一次沒送達、經「全部重試」或重新連線重送的檔案訊息，沒有檔名，大小為 0 | `2bbd12d` |

---

## 端對端驗證

單元測試把後端 mock 掉，因此第一輪另外以真實 MongoDB、Redis、FastAPI 與 `vite dev` 跑一次腳本（未納入 repo），經 BFF（Playwright）驗證第一輪的修正，10 項全部通過：

- 使用者 `abc?` 連續 5 次請求，後端沒有收到 `/api/auth/refresh`
- 註冊時 email 格式錯誤回 422，`error.message` 是字串
- 寫入 3 則未讀通知後，儀表板未讀數為 3、通知為前端格式、房間只列已加入的
- 經 BFF 上傳 `.mov` 與 `.md`，後端接受
- 在瀏覽器登入並停在房間頁，從另一個 session 改密碼：頁面自動回到 `/login`，`localStorage` 的使用者資料已清除。把 `client.ts` 與 `auth.svelte.ts` 換回修正前的版本重跑，頁面停在房間頁，本地資料也還在
- 連續登入失敗直到限流，BFF 回 429「嘗試次數過多，請稍後再試」

套件升級後重跑以上 10 項，全部通過。

### 自動化的端對端測試

房間頁、訊息重試與登入失效的驗證整理成 `frontend/tests/e2e/` 的 Playwright 測試，以 `npm run test:e2e` 執行。需先啟動 MongoDB、Redis 與後端，步驟見 `frontend/tests/e2e/README.md`。

- 只有 cookie、localStorage 沒有使用者資料時直接開啟房間連結，頁面停在該房間，過程中沒有經過 `/login`
- 從房間 P 點房間 A、0.4 秒後切到房間 B，並把 A 的訊息、房間或 ticket 請求延遲 2.5 秒。三種延遲下，網址、標題與訊息都是 B，只有一條連到 B 的 WebSocket，在 B 送出的訊息存進 B
- 攔截 WebSocket 丟掉送出的訊息，重試後再丟一次；第二次重試仍送達，且只存一筆
- 在另一個 session 改密碼後，頁面導回 `/login`，`localStorage` 的使用者資料已清除（即上面手動驗證的那一項）

分別還原對應的修正後重跑，對應的測試都會失敗。快速切換房間的三層修正缺一不可，第二輪手動驗證時分別只還原一層：只還原房間頁，仍連到 A；只還原 store，B 的訊息被 A 蓋掉；只還原 WebSocket manager（延遲 ticket），仍連到 A。

---

## 尚未涵蓋

- **Svelte 元件**：沒有元件測試。房間頁的修正由端對端測試涵蓋。
- **端對端測試**：需要真的後端，目前只能手動執行 `npm run test:e2e`。
- **WebSocket 連線管理**（`websocket/manager.ts`）：分頁切回前台時的重連、已讀請求去重與 `PUBLIC_WS_URL` 分支未測。
- **`bff-api-client.ts`**：儀表板、進階加入、上傳與邀請碼驗證使用的 fetch client，約 19%。
- **工具函式**：`retry`、`notificationSound`、`readStatusSync`、`roomListSync` 等大多未測。
- **相依套件的安全通報**：剩下的需要大版本變更才能修。`@sveltejs/kit` 與其相依的 cookie（low）要升到 SvelteKit 3；`@tailwindcss/typography` 相依的 postcss-selector-parser（moderate），audit 建議降回 0.5.4，且只在 build 時處理專案自己的 CSS。

以 `@vitest/coverage-v8` 量測（未加入專案相依）：BFF 路由與 `bff-*` 模組的行覆蓋率多在 80～100%，message store 93%，`websocket/manager.ts` 71%，`messageRetry` 78%，`markAsRead` 100%，`utils` 整體約 54%。
