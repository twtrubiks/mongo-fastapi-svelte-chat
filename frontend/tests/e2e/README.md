# 端對端測試

以 Playwright 操作瀏覽器，經由 SvelteKit BFF 連到真的 FastAPI、MongoDB 與 Redis。單元測試（`npm run test`）會把後端 mock 掉，涉及多個請求先後順序、WebSocket 與頁面導向的問題要靠這裡驗證。

| 測試檔 | 內容 |
|---|---|
| `room.spec.ts` | 只有登入 cookie 時直接開啟房間連結；從 A 快速切到 B，A 的訊息、房間資料或 WebSocket ticket 較晚回來時，畫面、連線與送出的訊息都屬於 B |
| `messages.spec.ts` | 攔截 WebSocket 丟掉送出的訊息，重試後再丟一次，第二次重試仍能送達且只存一筆 |
| `auth.spec.ts` | 在另一個 session 改密碼後，頁面導回登入頁並清除本地使用者資料 |

## 執行

1. 啟動 MongoDB 與 Redis：在專案根目錄執行 `docker-compose up -d`。
2. 啟動後端（在 `backend/`）。測試每次都會建立新的使用者與房間，建議指定獨立的資料庫：

   ```bash
   MONGODB_DATABASE=chatroom_e2e fastapi dev app/main.py
   ```

   `.env` 需設 `DEBUG=true`（`.env.example` 的預設值）。非 DEBUG 模式註冊限流為每小時 10 次，跑一次就用掉 6 次。
3. 第一次執行前安裝瀏覽器：`npx playwright install chromium`。
4. 在 `frontend/` 執行 `npm run test:e2e`。前端 dev server（:5173）沒在跑時會自動啟動；後端沒有回應 `/health` 時會直接停止並提示。

全部約 1 分鐘，其中訊息重試的測試要等兩次 10 秒的 ack 逾時。失敗時的 trace 在 `test-results/`，可用 `npx playwright show-trace <路徑>` 檢視。
