# 後端變異測試報告

> 執行日期：2026-10-23　對象：`backend/app`（commit `2813ef5`，約 9.3k 行）　工具：[`backend/scripts/mutation_test.py`](../backend/scripts/mutation_test.py)
> 明細附錄：[mutation-testing-survivors.md](mutation-testing-survivors.md)（994 個存活變異體逐一分類 + 從未被執行的函數清單）

變異測試（mutation testing）會刻意把程式碼改壞一點點（`==` 改 `!=`、刪掉一行呼叫、把 `"token_version"` 改成別的欄位名……），再跑測試。測試失敗代表這個「變異體」被**殺死（killed）**；測試仍然全綠代表它**存活（survived）**——也就是說，這段邏輯就算真的寫錯，現有測試也不會發現。行覆蓋率只回答「這行有沒有被執行」，變異測試回答的是「這行如果錯了，測試會不會叫」。

前端（SvelteKit）目前沒有任何測試，不在本次範圍內。

---

## 一、結論摘要

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

| 測試 | 問題 |
|---|---|
| `tests/test_api/test_auth_api.py::test_register_with_weak_password` | 斷言 `status_code in [201, 400, 422]`，不可能失敗 |
| `tests/test_auth/test_auth_system.py::test_refresh_access_token_inactive_user` | `Mock()` 使用者沒有設 `token_version`，即使停用帳號檢查被拿掉，後面的版本比對也會拋同一個例外——測試因錯誤的原因通過 |
| `tests/test_security/test_security_features.py`（10 個測試） | 沒有 import 任何 `app` 模組，測的是測試檔內自己寫的邏輯 |
| `tests/test_models/test_data_validation.py` | 在檔案內自行定義模型，沒有測 `app.models` |
| `tests/test_database/test_indexes.py` | 只數 `create_index` 呼叫次數，不檢查索引鍵 |

另外有三個結構性因素讓大量變異體存活：

1. **測試永遠在 `DEBUG=True` 下執行**，生產分支（限流表、CORS、TrustedHost、錯誤細節隱藏、HSTS）從未被執行。
2. **conftest 吞掉 Redis 初始化錯誤、限流計數測試在 Redis 缺席時 skip**——Redis 整個沒連上時 CI 仍是綠的。
3. **WS / service 測試多以 `call_count` 斷言**，沒有斷言送出去的 payload 內容。

---

## 五、判讀過程中發現的現存問題（非變異體）

以下是目前程式碼本身的行為，已逐一對照原始碼確認，**本次未修改**，建議另案處理：

1. **`PUT /api/auth/profile` 可以不驗證目前密碼直接改密碼。** `UserUpdate` 含 `password` 欄位，`user_service.update_user` 會直接雜湊寫入；BFF（`frontend/src/routes/api/auth/profile/+server.ts`）原樣轉發 body。`/change-password` 要求的「目前密碼」因此可被繞過——拿到一個已登入的 session（共用電腦未登出、XSS）就能改掉密碼、接管帳號。建議 `UserUpdate` 移除 `password`，密碼一律走 `change_password`。
2. **上傳的副檔名白名單可用客戶端宣稱的 MIME 繞過。** `FileUploadManager.get_file_type` 是 `_EXT_TO_TYPE.get(ext) or _MIME_TO_TYPE.get(client_mime)`，而 `_matches_magic` 對沒有簽章的副檔名直接回 `True`。`evil.html` 帶 `Content-Type: image/png` 會被當成圖片存成 `uploads/image/<ts>_<id>.html`。全站的 `X-Content-Type-Options: nosniff` 加上下載時回 `application/octet-stream`，讓瀏覽器不會把它當 HTML 執行，但白名單本身已失效。建議副檔名不在表中時直接拒絕。
3. **`backend/.env` 裡的 `SECURITY_*` 設定不會生效。** `security_config.load_security_config()` 用 `os.getenv` 讀取，但 pydantic-settings 只把 `.env` 載入 `Settings` 欄位、不會寫進 `os.environ`，而 `SECURITY_*` 不是 `Settings` 欄位。`backend/.env.example` 列出的這些設定只有透過真正的環境變數設定才有效。
4. **（疑似，未在 UI 實測）房間改成私人或邀請制時不會產生邀請碼。** `update_room` 只同步 `is_public` / `room_type`，不調整 `join_policy`、不產生 `invite_code`。把「公開 + 直接加入」的房間改成私人後，`join_room` 的 DIRECT 分支要求公開房、又沒有邀請碼，看起來會變成沒有人能加入。

次要觀察：BFF 的上傳 MIME 白名單（`frontend/src/routes/api/files/+server.ts`）比後端窄（缺 `.bmp`、`.md`、`.mkv`、`.m4a`、`.flac`），且 `general` 類型完全不檢查；縮圖端點固定回 `media_type="image/png"`。

---

## 六、建議的補測順序

依「一個測試能殺死多少高風險變異體」排序：

1. **改密碼端到端測試**（P0-2）——一個 API 測試就能覆蓋 token 撤銷鏈十餘個變異體，並第一次執行 `change_password`。
2. **rooms / messages 的 HTTP 測試**（P0-1、P2）——讓 `require_room_membership`、`get_room_for_user`、全部 router 本體、錯誤狀態碼第一次被執行。
3. **WebSocket 認證與 ws ticket 測試**（P0-1）。
4. **限流 dispatch 測試（`DEBUG=False`、真實 Redis、不 skip）**（P0-4）——殺死 13 個高風險變異體與生產限流表。
5. **修正第四節的 5 個缺陷測試**——改動小，直接殺死密碼長度、停用帳號 refresh、索引鍵等變異體。
6. **房間服務的角色 / 策略斷言**（P0-3）與 **`message_repository` 真實 DB 測試**（P1-1）。
7. **檔案服務整合測試**（P0-5）。
8. **WS payload 快照與 Pydantic 邊界參數化**（P1-2、P2）。

補完後建議重跑本工具確認分數變化。

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

### 存活者判讀

994 個存活者分成 4 個領域，由 4 個平行審查各自對照原始碼、測試與前端使用方逐一分類（高 / 中 / 低 / 等價），再由人工複核所有高風險項目。複核時調降 25 個：collection 名稱改寫（#1006、#1248）、Pydantic 模型間的限制不一致（#790 等 6 個）、magic 簽章表的鍵（17 個，有 `nosniff` 與正確 MIME 緩解）改列中風險。分類為主觀判斷，等價變異體尤其可能有誤判。

### 限制

- 前端沒有測試，未納入。
- AI 供應商（NVIDIA NIM / Gemini）在測試中以 pydantic-ai 的 `FunctionModel` / `TestModel` 取代。
- 每個變異體只跑「覆蓋該行的測試」：若某測試沒執行到該行、卻能透過其他途徑偵測到變異，會被低估（實務上極少見）。
- 字串變異排除了含中文的訊息，因此錯誤訊息文字的正確性不在統計內。

---

## 八、如何重跑

需先啟動與測試相同的 MongoDB（`mongodb://root:password@localhost:27017`）與 Redis（`localhost:6379`），見 `backend/tests/test_config.py`。

```bash
cd backend
python scripts/mutation_test.py all --workers 4     # 全流程，4 核約 75 分鐘

# 或分步執行（run 可中斷後續跑）
python scripts/mutation_test.py gen
python scripts/mutation_test.py coverage
python scripts/mutation_test.py setup --workers 4
python scripts/mutation_test.py baseline --workers 4
python scripts/mutation_test.py plan
python scripts/mutation_test.py run --workers 4
python scripts/mutation_test.py report             # 輸出 backend/.mutation/report.md
```

工作目錄 `backend/.mutation/` 已加入 `.gitignore`。worker 使用 MongoDB 資料庫 `test_chatroom_mut{i}` 與 Redis DB `2 + i`。
