# 變異測試附錄：存活變異體與未覆蓋函數明細

本文件為 [變異測試報告](mutation-testing-report.md) 的附錄，列出全部 994 個存活變異體的分類，以及從未被任何測試執行過的函數。
編號（`#id`）對應 `backend/scripts/mutation_test.py gen` 產生的變異體編號；程式碼變動時編號會改變，請以位置與變異內容為準。

分類定義：

- **高風險**：削弱安全控制、授權 / 認證、token 撤銷、限流、資料完整性或核心業務規則，且執行中的 app 會出現可觀察的錯誤行為
- **中風險**：一般邏輯或 API / WS 契約的可觀察改變（欄位、狀態碼、分頁、事件、使用者會碰到的預設值），合理的測試應該抓到
- **低價值**：確實改變行為，但不值得專門寫測試（調參常數、會被部署覆寫的設定預設值、log、純效能、錯誤訊息文字）
- **等價**：任何輸入下都不會產生可觀察差異（語意相同、值會被覆寫、死碼），計算分數時應排除

## 目錄

- [高風險](#高風險high)
- [中風險](#中風險medium)
- [低價值](#低價值low)
- [等價變異體](#等價變異體equivalent)
- [從未被任何測試執行的函數](#從未被任何測試執行的函數)

## 高風險（high）

共 71 個。

### `app/auth/dependencies.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 29 | 54 | `get_current_user_token` | `"token_version"` → `"XXtoken_versionXX"` | TokenData 版本恆為 0：改密碼後舊 v0 token 仍通過，新 token 反被拒，撤銷失效 | 改密碼後以舊 access token 打 /api/auth/me 應 401，重新登入的 token 應 200 |
| 25 | 73 | `get_current_user` | `"token_version"` → `"XXtoken_versionXX"` | 使用者端版本恆讀為 0：改密碼後舊 v0 token 通過比對，撤銷失效 | 改密碼後以舊 access token 打 /api/auth/me 應 401，重新登入的 token 應 200 |

### `app/config.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 89 | 47 | `<class Settings>` | `False` → `True` | 安全預設翻轉：未設 DEBUG 時生產即 DEBUG（CORS*、寬鬆限流、錯誤細節外洩） | 移除 DEBUG 環境變數並以 _env_file=None 建 Settings，斷言 DEBUG is False |

### `app/database/indexes.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 219 | 21 | `ensure_indexes` | `"username"` → `"XXusernameXX"` | username 唯一索引建在錯欄位：重名註冊競態無保底，且第二位使用者即撞 null 鍵 | 斷言 users 索引 key 為 username 且 unique（或真實 Mongo 驗索引） |
| 220 | 22 | `ensure_indexes` | `"email"` → `"XXemailXX"` | email 唯一索引建在錯欄位：重複信箱競態無保底，第二位使用者撞 null 鍵 | 斷言 users.create_index 的 key 為 [('email',1)] 且 unique |
| 226 | 32 | `ensure_indexes` | `"client_id"` → `"XXclient_idXX"` | 去重索引變 (room_id,null) 唯一：每房僅能有一則帶 client_id 的訊息 | 斷言去重索引 key 為 room_id+client_id；同房兩則不同 client_id 皆成功 |
| 228 | 40 | `ensure_indexes` | `"name"` → `"XXnameXX"` | 房名唯一索引建在錯欄位：TOCTOU 競態無保底，建第二間房即撞鍵 | 斷言 rooms.create_index 的 key 為 [('name',1)] 且 unique |
| 229 | 43 | `ensure_indexes` | `"invite_code"` → `"XXinvite_codeXX"` | 邀請碼唯一索引建錯欄：第二間有邀請碼的房間即撞鍵，且碼唯一性失守 | 斷言 invite_code 部分唯一索引 key 與 partialFilterExpression 一致 |

### `app/database/redis_conn.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 265 | 20 | `connect` | `is` → `is not` | Redis 永不連線且不報錯：限流 fail-open 全停用、WS ticket 全 500 | init_redis 後斷言 get_redis() 可 ping；Redis 缺席時測試應失敗非 skip |
| 268 | 45 | `get_client` | `is` → `is not` | 已連線卻拋 RuntimeError：限流/快取全 fail-open，WS ticket 失敗 | 已連線時斷言 get_redis() 回傳可 ping 的 client |
| 264 | 47 | `get_client` | `self.redis_client` → `None` | get_client 回 None：限流器以 None 運作後 fail-open，全站限流失效 | 已連線時斷言 get_redis() 回傳可 ping 的 client |
| 260 | 56 | `init_redis` | `await _redis_manager.connect()` → `pass` | init_redis 不連線：限流靜默停用、WS ticket 500、bot 限流失效 | init_redis 後斷言 get_redis().ping() 為 True |
| 262 | 66 | `get_redis` | `await _redis_manager.get_client()` → `None` | get_redis 回 None：所有 Redis 依賴 fail-open，限流失效 | 斷言 get_redis() 非 None 且可 ping |

### `app/main.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 278 | 109 | `<module>` | `app.add_middleware(RateLimitingMiddleware, sett…` → `pass` | RateLimitingMiddleware 未註冊，全站沒有限流 | 不 patch skip 的 client 連打 /api/auth/login 超過上限應得 429 |

### `app/middleware/rate_limiting.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 445 | 108 | `__init__` | `redis_client` → `not (redis_client)` | 以 None 建 limiter，is_allowed 拋錯被 fail-open 吞掉，全站限流失效 | 以真實 app（不 patch skip）連打超過上限應 429 |
| 446 | 113 | `__init__` | `self.settings.DEBUG` → `not (self.settings.DEBUG)` | DEBUG 判斷反轉：生產套用 5–10 倍寬鬆的 DEBUG 限流表 | DEBUG=False 建 middleware，斷言 login 為 300 秒/20 次/burst 10 |
| 464 | 195 | `_get_rate_limit_config` | `in` → `not in` | 非精確路徑查表 KeyError 被 fail-open 吞掉，多數 API 失去限流 | 斷言 _get_rate_limit_config('/api/rooms') 回 /api/ 設定，且連打應 429 |
| 467 | 214 | `_should_skip_rate_limiting` | `path.startswith(skip_path)` → `not (path.startswith(skip_pat…` | 跳過條件反轉，幾乎所有路徑跳過限流，限流全面失效 | 斷言 _should_skip_rate_limiting('/api/rooms') 為 False |
| 468 | 217 | `_should_skip_rate_limiting` | `False` → `True` | 所有路徑都跳過限流，限流全面失效 | 斷言 _should_skip_rate_limiting('/api/rooms') 為 False |
| 506 | 221 | `_initialize_limiter` | `is` → `is not` | 初始化未建立有效 limiter，每次 AttributeError 被 fail-open 吞掉，限流停用 | dispatch 一次後斷言 middleware.limiter 有 redis，且超限回 429 |
| 507 | 221 | `_initialize_limiter` | `is` → `is not` | 初始化未建立有效 limiter，每次 AttributeError 被 fail-open 吞掉，限流停用 | dispatch 一次後斷言 middleware.limiter 有 redis，且超限回 429 |
| 508 | 224 | `_initialize_limiter` | `self.redis_client = await get_redis()` → `pass` | 初始化未建立有效 limiter，每次 AttributeError 被 fail-open 吞掉，限流停用 | dispatch 一次後斷言 middleware.limiter 有 redis，且超限回 429 |
| 509 | 225 | `_initialize_limiter` | `self.limiter = SlidingWindowRateLimiter( self.r…` → `pass` | 初始化未建立有效 limiter，每次 AttributeError 被 fail-open 吞掉，限流停用 | dispatch 一次後斷言 middleware.limiter 有 redis，且超限回 429 |
| 470 | 231 | `_initialize_limiter` | `True` → `False` | 初始化恆回 False，每次走 fail-open 放行，限流停用 | Redis 可用時連打超過上限應 429 |
| 472 | 240 | `dispatch` | `not` → `` | 初始化成功反而直接放行，限流停用 | Redis 可用時連打超過上限應 429 |
| 653 | 257 | `dispatch` | `"window"` → `"XXwindowXX"` | 讀 config 鍵 KeyError 被 fail-open 吞掉，所有路徑限流停用 | Redis 可用時連打超過上限應 429 |
| 654 | 258 | `dispatch` | `"max_requests"` → `"XXmax_requestsXX"` | 讀 config 鍵 KeyError 被 fail-open 吞掉，所有路徑限流停用 | Redis 可用時連打超過上限應 429 |

### `app/models/room.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 803 | 32 | `<class RoomCreate>` | `6` → `0` | 允許空或 1 字元房間密碼，密碼房可被輕易暴力猜中 | RoomCreate/RoomUpdate password 5 字元 422、6 字元通過 |
| 816 | 45 | `<class RoomUpdate>` | `6` → `0` | 可將房間密碼改為空或 1 字元；空密碼雜湊後房間實際無法加入 | RoomCreate/RoomUpdate password 5 字元 422、6 字元通過 |

### `app/models/user.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 840 | 23 | `<class UserCreate>` | `6` → `0` | 允許空或 1 字元密碼註冊，帳號可被輕易猜中 | 註冊/改密碼/PUT profile：5 字元 422、6 字元成功 |
| 842 | 32 | `<class UserUpdate>` | `6` → `0` | PUT /auth/profile 可將密碼設為空或 1 字元 | 註冊/改密碼/PUT profile：5 字元 422、6 字元成功 |
| 849 | 97 | `<class PasswordChange>` | `6` → `0` | 改密碼可設為空字串或 1 字元 | 註冊/改密碼/PUT profile：5 字元 422、6 字元成功 |

### `app/repositories/room_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1222 | 67 | `update` | `is not` → `is` | 新密碼不寫入（舊密碼仍有效）；無密碼更新時清空 password_hash | update 帶 hash 後 DB 有新 hash；不帶時原 hash 保留 |
| 1297 | 182 | `add_member` | `"$lt"` → `"XX$ltXX"` | $expr 變物件常值恆為真→max_members 原子保底失效，併發可超員 | 房間已滿時 add_member 回 False 且 members 不變 |
| 1307 | 182 | `add_member` | `"$max_members"` → `"XX$max_membersXX"` | 與字串比較恆為真→max_members 原子保底失效，併發可超員 | 房間已滿時 add_member 回 False 且 members 不變 |

### `app/repositories/user_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1319 | 110 | `update` | `bump_token_version` → `not (bump_token_version)` | 改密碼不遞增版本（撤銷失效），一般資料更新反而強制登出 | PUT /profile 改密碼後舊 token 打 /me 應 401；改 full_name 後應 200 |
| 1340 | 111 | `update` | `update_ops["$inc"] = {"token_version": 1}` → `pass` | 改密碼不遞增 token_version，舊 access/refresh token 永久有效 | 改密碼後舊 token 打 /api/auth/me 應 401，DB token_version 應 +1 |
| 1355 | 111 | `update` | `"token_version"` → `"XXtoken_versionXX"` | $inc 寫到錯欄位，token_version 不變，撤銷失效 | 改密碼後斷言 DB token_version 由 0 變 1，舊 token 401 |

### `app/services/message_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1843 | 277 | `sync_messages_since` | `0` → `1` | 大 gap 全量重載 skip=1：清空後少了最新一則，客戶端靜默漏訊息 | gap>200 時斷言回傳訊息包含最新 seq 且 full_reload=True |
| 1845 | 277 | `sync_messages_since` | `50` → `0` | 全量重載 limit=0 拋錯→退回無 full_reload 的歷史，中間數百則靜默漏掉 | gap>200 時斷言回傳 50 筆且 full_reload=True |

### `app/services/room_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1971 | 71 | `_convert_to_response` | `user_id` → `not (user_id)` | 帶 user_id 時不遮蔽→一般成員取得 invite_code；房主更新回應反被遮蔽 | get_room_for_user：MEMBER 拿到 invite_code=None，OWNER/ADMIN 可見 |
| 2083 | 73 | `_convert_to_response` | `not in` → `in` | 一般成員看得到 invite_code，owner/admin 反而看不到 | get_room_for_user：MEMBER 拿到 invite_code=None，OWNER/ADMIN 可見 |
| 2002 | 146 | `create_room` | `==` → `!=` | 私人房不再強制 INVITE/邀請碼（可用 PASSWORD 加入），公開房反變邀請制 | 建 PRIVATE+password 房：斷言 join_policy=INVITE 且有邀請碼 |
| 2004 | 155 | `create_room` | `==` → `!=` | is_public 與 room_type 相反→私人房出現在公開列表/搜尋，公開房消失 | 建 PRIVATE 房斷言傳給 repo.create 的 is_public is False |
| 2118 | 302 | `update_room` | `!=` → `==` | 以原名更新自己的房間被判衝突（前端必送 name→設定永遠 409） | get_by_name 回自身房間時 update_room 應成功 |
| 2029 | 306 | `update_room` | `is not` → `is` | 未給 room_type 時 is_public 被設 False；給時不同步→私人房仍公開列出 | update(room_type=PRIVATE) 斷言 is_public False；只改名不動 is_public |
| 2097 | 308 | `update_room` | `is not` → `is` | 未給 is_public/room_type 時房間被改為 PRIVATE，與 is_public 脫鉤 | update(is_public=False) 斷言 room_type=PRIVATE；只改名不動 room_type |
| 2145 | 445 | `join_room` | `or` → `and` | 邀請制房 invite_code 為 None（經 update 改 INVITE）時空 body 即可加入 | INVITE 房以 None 與 RoomJoinRequest() 加入皆拋 AppError |

### `app/services/user_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2226 | 161 | `update_user` | `True` → `False` | PUT /profile 改密碼不撤銷舊 token | PUT /profile 改密碼後舊 access token 打 /me、舊 refresh 換發皆 401 |
| 2174 | 170 | `update_user` | `await invalidate_user_cache(user_id)` → `pass` | 更新後不清快取：改密碼後舊 token 最長 5 分鐘仍有效、新 token 被拒 | 先打 /me 建快取，PUT /profile 改密碼，立即以舊 token 打 /me 應 401 |
| 2177 | 227 | `delete_user` | `await invalidate_user_cache(user_id)` → `pass` | 刪帳後快取仍 is_active=True，舊 token 5 分鐘內 HTTP/WS 仍可用 | 先打 /me 建快取，DELETE /profile 後同 token 打 /me 應被拒 |
| 2229 | 257 | `authenticate_user` | `"token_version"` → `"XXtoken_versionXX"` | 登入 token 不帶版本：改過密碼的使用者登入後每個請求都 401 | 改密碼→重新登入→新 token 打 /api/auth/me 應 200 |
| 2218 | 301 | `refresh_access_token` | `or` → `and` | 停用帳號仍能以 refresh token 換發新 token（現有測試因 Mock 版本誤過） | inactive 測試設 mock_user.token_version=0 後仍應 401 |
| 2219 | 302 | `refresh_access_token` | `raise UnauthorizedError("無效或過期的 Refresh Token")` → `pass` | 停用帳號仍能以 refresh token 換發新 token（現有測試因 Mock 版本誤過） | inactive 測試設 mock_user.token_version=0 後仍應 401 |

### `app/utils/file_upload.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2478 | 217 | `generate_unique_filename` | `8` → `0` | 唯一碼變空字串：同秒同副檔名上傳檔名相撞，後者覆寫他人檔案 | 固定時間下連續兩次上傳應得不同檔名，且兩檔內容皆完整保留 |
| 2336 | 260 | `save_file` | `await file.seek(0)` → `pass` | 讀檔頭後未 seek 回 0，存檔缺前 16 bytes，所有上傳檔靜默損毀但回報成功 | save_file 後讀回磁碟檔，內容應與上傳位元組完全相同 |
| 2500 | 260 | `save_file` | `0` → `1` | seek(1) 使存檔缺第一個位元組，所有上傳檔靜默損毀但回報成功 | save_file 後讀回磁碟檔，內容應與上傳位元組完全相同 |
| 2422 | 280 | `save_file` | `await f.write(content)` → `pass` | 未寫入內容：所有上傳檔為 0 位元組但回報成功（資料遺失） | save_file 後磁碟檔內容等於上傳內容，回應 size 等於實際位元組數 |

### `app/websocket/handlers.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2815 | 86 | `_format_message_payload` | `"seq"` → `"XXseqXX"` | 即時訊息缺 seq：客戶端無法追蹤最大序號，重連 gap 補發基準錯誤，空房情境會漏訊息 | 斷言 chat 廣播與 ack 的 seq 等於 create_message 回傳 seq |
| 2873 | 150 | `handle_websocket_connection` | `"last_seq"` → `"XXlast_seqXX"` | 重連 last_seq 參數永遠讀不到，只送最近 50 則，斷線期間超過 50 則即漏 | 帶 last_seq=5 連線，斷言走 send_gap_messages 而非歷史 |
| 2823 | 151 | `handle_websocket_connection` | `and` → `or` | 無 last_seq（首次連線/空房）時 None.isdigit() 例外→連線被關閉，空房無法即時聊天 | query 無 last_seq 與 last_seq=abc 時斷言送出 message_history 且連線不關閉 |
| 2824 | 152 | `handle_websocket_connection` | `await send_gap_messages(user_id, room_id, int(l…` → `pass` | 重連帶 last_seq 時不補發 gap，斷線期間訊息永久遺失於即時視圖 | 帶 last_seq 連線，斷言收到 message_sync 含 seq>last_seq 訊息 |
| 2877 | 227 | `handle_message` | `"message"` → `"XXmessageXX"` | 前端送 type:'message'，別名失效後所有 WS 聊天訊息被當未知類型，無法發送 | handle_message 以 type='message' 斷言呼叫 handle_chat_message |
| 2881 | 268 | `handle_chat_message` | `"client_id"` → `"XXclient_idXX"` | 讀不到 client_id：冪等去重失效、ack 無 client_id 致前端重試→重複訊息 | WS 帶 client_id，斷言 MessageCreate 與 ack 的 client_id 相同 |
| 2782 | 314 | `handle_chat_message` | `await connection_manager.send_personal_message(…` → `pass` | ack 未送/無法辨識/缺 client_id：前端 10 秒後標記失敗並重試，每則訊息顯示發送失敗 | 斷言發送成功後送出 type=ack，含正確 client_id/message_id/seq |
| 2975 | 318 | `handle_chat_message` | `"type"` → `"XXtypeXX"` | ack 未送/無法辨識/缺 client_id：前端 10 秒後標記失敗並重試，每則訊息顯示發送失敗 | 斷言發送成功後送出 type=ack，含正確 client_id/message_id/seq |
| 2981 | 318 | `handle_chat_message` | `"ack"` → `"XXackXX"` | ack 未送/無法辨識/缺 client_id：前端 10 秒後標記失敗並重試，每則訊息顯示發送失敗 | 斷言發送成功後送出 type=ack，含正確 client_id/message_id/seq |
| 2976 | 319 | `handle_chat_message` | `"client_id"` → `"XXclient_idXX"` | ack 未送/無法辨識/缺 client_id：前端 10 秒後標記失敗並重試，每則訊息顯示發送失敗 | 斷言發送成功後送出 type=ack，含正確 client_id/message_id/seq |
| 2889 | 398 | `handle_chat_message` | `is_summary_command(content)` → `not (is_summary_command(conte…` | 非 @bot 的每則文字訊息都觸發 AI 摘要（成本暴增、bot 洗版），/summary 反而無效 | 一般訊息斷言未 spawn 摘要；'/summary' 斷言 spawn handle_summary_command |
| 2986 | 428 | `_check_bot_rate_limit` | `60` → `0` | window_size=0：清空所有紀錄且 now%0 例外 fail-open，@bot 限流完全失效 | 以真實（fake）Redis 連續呼叫超過上限，斷言 _check_bot_rate_limit 回 False |

### `app/websocket/manager.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 3212 | 365 | `_execute_room_leave` | `not` → `` | 使用者切走房間後若房內仍有人，整個 room_users 被刪，其餘在線成員收不到任何廣播 | A、B 同房，A 斷線 debounce 後斷言 B 仍收得到 broadcast_to_room 訊息 |

## 中風險（medium）

共 355 個。

### `app/config.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 77 | 27 | `<class Settings>` | `60` → `0` | 生產 /api/ 每分鐘上限變 0（.env 未覆寫），所有一般 API 請求皆 429 | Settings(DEBUG=False) 建 middleware，斷言 /api/ 上限為 60 |
| 81 | 29 | `<class Settings>` | `10` → `0` | burst=0 使生產 /api/ 突發限制停用，有效上限由每分 10 次放寬為 60 次 | 以生產設定斷言 /api/ burst=10，且同分鐘第 11 次請求回 429 |
| 88 | 44 | `<class Settings>` | `5` → `0` | @bot 上限預設 0（.env 未覆寫），每次 @bot/summary 皆被限流 | 預設設定下 _check_bot_rate_limit 第 1 次允許、第 6 次拒絕 |

### `app/core/bot.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 119 | 117 | `_as_utc` | `dt.tzinfo` → `not (dt.tzinfo)` | DB 的 naive 時間與 aware 比較拋 TypeError，fail-open 使 @bot 多輪記憶恆空 | 以 naive datetime 呼叫 build_bot_history，斷言仍配出歷史 |
| 129 | 147 | `build_bot_history` | `continue` → `break` | 遇到第一則非文字訊息即中斷，之後（較新）的 @bot 往返全部遺失 | 圖片訊息夾在兩組 @bot 往返中間，斷言兩組都進入歷史 |

### `app/core/exceptions.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 146 | 11 | `<class AppError>` | `400` → `401` | AppError 預設 400→401：如改密碼舊密碼錯誤回 401，誤觸 BFF 換發/登出流程 | PUT /api/auth/change-password 帶錯誤舊密碼，斷言 400 與 detail |
| 147 | 11 | `<class AppError>` | `400` → `0` | AppError 狀態碼變 0，直接 raise AppError 的路徑回應失敗 | PUT /api/auth/change-password 帶錯誤舊密碼，斷言 400 與 detail |
| 148 | 16 | `__init__` | `super().__init__(message)` → `pass` | Exception.args 為空，WS handler 以 str(e) 回傳的錯誤訊息變空字串 | WS 送空白/超長訊息，斷言 error payload 的 message 為具體中文訊息 |
| 149 | 22 | `<class NotFoundError>` | `404` → `405` | NotFoundError 狀態碼 404 被改，查無資源 API 回錯誤狀態碼 | HTTP 查不存在的房間/訊息（經 app），斷言 404 |
| 150 | 22 | `<class NotFoundError>` | `404` → `0` | NotFoundError 狀態碼 404 被改，查無資源 API 回錯誤狀態碼 | HTTP 查不存在的房間/訊息（經 app），斷言 404 |
| 153 | 35 | `<class ForbiddenError>` | `403` → `404` | ForbiddenError 狀態碼 403 被改，權限拒絕回錯誤狀態碼 | 非擁有者經 HTTP 刪除房間，斷言 403 |
| 154 | 35 | `<class ForbiddenError>` | `403` → `0` | ForbiddenError 狀態碼 403 被改，權限拒絕回錯誤狀態碼 | 非擁有者經 HTTP 刪除房間，斷言 403 |

### `app/core/fastapi_integration.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 167 | 113 | `get_health_check_info` | `await db.command("ping")` → `pass` | 不 ping Mongo：DB 斷線時健康檢查仍報 connected | get_database 回傳 command 會拋錯的 db，斷言 mongodb=disconnected |
| 189 | 113 | `get_health_check_info` | `"ping"` → `"XXpingXX"` | ping 指令名錯，健康檢查永遠 unhealthy，探針誤判重啟 | test_healthy 斷言 db.command 以 'ping' 被 await |
| 169 | 123 | `get_health_check_info` | `await client.ping()` → `pass` | 不 ping Redis：Redis 斷線時健康檢查仍報 connected | get_redis 回傳 ping 會拋錯的 client，斷言 redis=disconnected |

### `app/database/redis_conn.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 270 | 22 | `connect` | `self.redis_client = redis.from_url( settings.RE…` → `pass` | client 未賦值，ping None 拋錯，生產啟動直接失敗（測試吞掉） | init_redis 後斷言 _redis_manager.redis_client 非 None 且可 ping |
| 273 | 25 | `connect` | `"utf-8"` → `"XXutf-8XX"` | 非法編碼使首個 Redis 指令失敗，生產啟動崩潰（conftest 吞掉） | init_redis 後斷言 _redis_manager.redis_client 非 None 且可 ping |

### `app/main.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 275 | 61 | `<module>` | `settings.DEBUG` → `not (settings.DEBUG)` | 生產忽略 CORS_ORIGINS，改為 * 並允許 credentials | DEBUG=False 且指定 CORS_ORIGINS 重建 app，惡意 Origin 不得回 ACAO |
| 301 | 66 | `<module>` | `==` → `!=` | 生產忽略 CORS_ORIGINS，改為 * 並允許 credentials | DEBUG=False 且指定 CORS_ORIGINS 重建 app，惡意 Origin 不得回 ACAO |
| 295 | 81 | `<module>` | `not` → `` | 生產未掛 TrustedHostMiddleware，ALLOWED_HOSTS 設定失效 | DEBUG=False、ALLOWED_HOSTS=api.x 重建 app，偽造 Host 應回 400 |
| 310 | 84 | `<module>` | `!=` → `==` | 生產未掛 TrustedHostMiddleware，ALLOWED_HOSTS 設定失效 | DEBUG=False、ALLOWED_HOSTS=api.x 重建 app，偽造 Host 應回 400 |
| 296 | 86 | `<module>` | `allowed_hosts` → `not (allowed_hosts)` | 生產未掛 TrustedHostMiddleware，ALLOWED_HOSTS 設定失效 | DEBUG=False、ALLOWED_HOSTS=api.x 重建 app，偽造 Host 應回 400 |
| 302 | 87 | `<module>` | `app.add_middleware(TrustedHostMiddleware, allow…` → `pass` | 生產未掛 TrustedHostMiddleware，ALLOWED_HOSTS 設定失效 | DEBUG=False、ALLOWED_HOSTS=api.x 重建 app，偽造 Host 應回 400 |
| 279 | 112 | `<module>` | `app.add_middleware(GlobalErrorHandler, debug=se…` → `pass` | 移除全域錯誤處理：DuplicateKey 變 500、Redis 錯誤不回 503、格式改變 | 經 app 觸發 DuplicateKeyError，斷言 409 與 DUPLICATE_KEY_ERROR |
| 280 | 127 | `<module>` | `app.include_router(ai.router, prefix="/api")` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 282 | 129 | `<module>` | `app.include_router(rooms.router, prefix="/api")` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 283 | 130 | `<module>` | `app.include_router(messages.router, prefix="/ap…` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 284 | 131 | `<module>` | `app.include_router(notifications.router, prefix…` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 285 | 132 | `<module>` | `app.include_router(files.router, prefix="/api")` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 286 | 133 | `<module>` | `app.include_router(invitations.router, prefix="…` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 287 | 134 | `<module>` | `app.include_router(ws_ticket.router, prefix="/a…` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 288 | 137 | `<module>` | `app.include_router(websocket_routes.router)` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |

### `app/middleware/error_handler.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 374 | 86 | `handle_error` | `and` → `or` | 非 debug 也回 details：生產洩漏 DuplicateKey 的集合/索引/鍵值 | debug=False 觸發 DuplicateKeyError，斷言回應 error 不含 details |

### `app/middleware/rate_limiting.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 514 | 60 | `is_allowed` | `60` → `0` | 突發視窗變 0 秒，突發限制退化為「每秒」計數 | mock time 跨秒：60 秒內超過 burst 次數仍應被拒 |
| 466 | 200 | `_get_rate_limit_config` | `path.startswith(pattern)` → `not (path.startswith(pattern))` | 前綴比對反轉，各路徑套錯設定（多數套到 login 設定） | 斷言 /api/rooms、/ws/x、/ 各自取得 /api/、/ws、default 設定 |
| 501 | 211 | `_should_skip_rate_limiting` | `"/health"` → `"XX/healthXX"` | /health 被納入限流，生產 default burst 10/分使健康探針 429 | 斷言 skip 判斷對 /health 為 True、對 /api/x 為 False |
| 537 | 215 | `_should_skip_rate_limiting` | `True` → `False` | 跳過清單失效，/health 等也被限流，探針可能 429 | 斷言 _should_skip_rate_limiting 對 /health 回 True |
| 655 | 259 | `dispatch` | `"burst"` → `"XXburstXX"` | burst 恆為 None，所有突發限制停用（視窗上限仍在） | 同分鐘超過 burst 次數（未達 max_requests）應 429 |

### `app/middleware/security_headers.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 702 | 117 | `__call__` | `continue` → `break` | 生產非 HTTPS 時於 STS 處 break，其後的 CSP 不會被加上 | enable_hsts=True 的 middleware 處理 HTTP 請求，斷言回應仍含 CSP |

### `app/models/enums.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 723 | 9 | `<class RoomType>` | `"public"` → `"XXpublicXX"` | PUBLIC 字串值改變：前端送 'public' 得 422，既有房間文件載入失敗 | 斷言 RoomType/JoinPolicy 各成員 .value 等於前端字串並以字串建房 |
| 724 | 10 | `<class RoomType>` | `"private"` → `"XXprivateXX"` | PRIVATE 字串值改變：前端無法建立私人房，既有私人房載入失敗 | 斷言 RoomType/JoinPolicy 各成員 .value 等於前端字串並以字串建房 |
| 725 | 16 | `<class JoinPolicy>` | `"direct"` → `"XXdirectXX"` | DIRECT 字串值改變：前端送 'direct' 得 422，API 回傳值與前端列舉不符 | 斷言 RoomType/JoinPolicy 各成員 .value 等於前端字串並以字串建房 |
| 726 | 17 | `<class JoinPolicy>` | `"invite"` → `"XXinviteXX"` | INVITE 字串值改變：邀請制房建立 422、既有資料載入失敗 | 斷言 RoomType/JoinPolicy 各成員 .value 等於前端字串並以字串建房 |
| 727 | 18 | `<class JoinPolicy>` | `"password"` → `"XXpasswordXX"` | PASSWORD 字串值改變：密碼房建立 422、既有資料載入失敗 | 斷言 RoomType/JoinPolicy 各成員 .value 等於前端字串並以字串建房 |

### `app/models/message.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 733 | 18 | `<class MessageType>` | `"text"` → `"XXtextXX"` | MessageType 線上字串值改變：API/WS 回傳型別值變、既有 DB 文件驗證失敗致歷史 500 | 序列化契約測試：建立各類訊息後斷言 JSON message_type 為 text/image/file 字面值 |
| 734 | 19 | `<class MessageType>` | `"image"` → `"XXimageXX"` | MessageType 線上字串值改變：API/WS 回傳型別值變、既有 DB 文件驗證失敗致歷史 500 | 序列化契約測試：建立各類訊息後斷言 JSON message_type 為 text/image/file 字面值 |
| 735 | 20 | `<class MessageType>` | `"file"` → `"XXfileXX"` | MessageType 線上字串值改變：API/WS 回傳型別值變、既有 DB 文件驗證失敗致歷史 500 | 序列化契約測試：建立各類訊息後斷言 JSON message_type 為 text/image/file 字面值 |
| 736 | 21 | `<class MessageType>` | `"system"` → `"XXsystemXX"` | MessageType 線上字串值改變：API/WS 回傳型別值變、既有 DB 文件驗證失敗致歷史 500 | 序列化契約測試：建立各類訊息後斷言 JSON message_type 為 text/image/file 字面值 |
| 737 | 27 | `<class MessageStatus>` | `"sent"` → `"XXsentXX"` | MessageStatus 字串值改變：既有 sent/deleted 文件載入驗證失敗，回應 status 值漂移 | 斷言新訊息 JSON status=='sent'、軟刪除後 DB status=='deleted' 字面值 |
| 738 | 28 | `<class MessageStatus>` | `"deleted"` → `"XXdeletedXX"` | MessageStatus 字串值改變：既有 sent/deleted 文件載入驗證失敗，回應 status 值漂移 | 斷言新訊息 JSON status=='sent'、軟刪除後 DB status=='deleted' 字面值 |
| 747 | 35 | `<class MessageBase>` | `1` → `2` | content min_length 1→2：單字訊息（如「好」）HTTP/WS 皆無法發送，且既有單字訊息載入失敗 | 以 1 字元內容建立訊息（HTTP 與 WS）應成功 |
| 750 | 55 | `<class MessageUpdate>` | `1` → `2` | 編輯 min_length 1→2：無法把訊息編輯成單一字元 | PUT 編輯內容為 1 字元應成功 200 |
| 752 | 71 | `<class MessageInDB>` | `False` → `True` | edited 預設變 True：所有新訊息存成已編輯，前端每則顯示「（已編輯）」 | 建立訊息後斷言回應與 DB 的 edited is False |
| 755 | 128 | `<class MessageSearchQuery>` | `1` → `2` | 搜尋關鍵字 min_length 1→2：前端單字搜尋（如「好」）一律 422 | 以 1 字元 keyword 搜尋應回 200 並命中 |
| 744 | 134 | `<class MessageSearchQuery>` | `1` → `2` | page ge=2：前端每次搜尋都帶 page=1，全部 422，搜尋功能失效 | POST search 帶 page=1 應 200 |
| 746 | 135 | `<class MessageSearchQuery>` | `20` → `0` | 預設 page_size=0→to_list(0) ValueError，未帶 page_size 的搜尋回 500 | 不帶 page_size 搜尋應 200 且 ≤20 筆 |

### `app/models/notification.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 763 | 14 | `<class NotificationType>` | `"message"` → `"XXmessageXX"` | MESSAGE 列舉值改變：前端大寫比對 MESSAGE 失效、?type=message 回 422、舊資料驗證失敗 | API 測試：建立訊息通知後回應與 DB 的 type 應為字串 "message" |
| 764 | 15 | `<class NotificationType>` | `"system"` → `"XXsystemXX"` | SYSTEM 列舉值改變：前端類型判斷與 ?type=system 過濾失效、舊資料驗證失敗 | 斷言系統通知序列化 type == "system" 且 ?type=system 可查到 |
| 765 | 21 | `<class NotificationStatus>` | `"unread"` → `"XXunreadXX"` | UNREAD 值改變：前端未讀判斷失效、?status=unread 回 422、舊未讀資料不計數 | API 測試：新通知回應 status 為 "unread"，DB 文件 status 字串相同 |
| 766 | 22 | `<class NotificationStatus>` | `"read"` → `"XXreadXX"` | READ 值改變：前端已讀判斷失效，既有已讀文件載入時驗證失敗 | 標記已讀後直接查 DB 文件 status 應為字串 "read" |
| 767 | 88 | `serialize_datetime` | `format_datetime_for_json(dt)` → `None` | 通知 created_at/updated_at/read_at 在 API 回應與 WS 推播中全變 null | model_dump 後 created_at 應為 ISO 字串而非 None |

### `app/models/room.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 790 | 13 | `<class RoomBase>` | `1` → `2` | RoomBase 拒 1 字名稱但 RoomUpdate 仍允許→寫入後 RoomInDB 讀不回，列表 500 | RoomCreate(name='a') 應成功；RoomUpdate 與 RoomBase 長度限制一致 |
| 797 | 18 | `<class RoomBase>` | `2` → `3` | RoomInDB 拒 max_members=2 但 RoomUpdate 允許→房間/列表 500；2 人房無法建 | RoomCreate(max_members=2) 成功、=1 得 422 |
| 798 | 18 | `<class RoomBase>` | `2` → `0` | 可建立 max_members 為 0/1 的房間，房主以外無人能加入 | RoomCreate(max_members=1) 應 ValidationError |
| 802 | 32 | `<class RoomCreate>` | `6` → `7` | 6 字元房間密碼被誤拒（422） | RoomCreate/RoomUpdate password 5 字元 422、6 字元通過 |
| 805 | 32 | `<class RoomCreate>` | `128` → `0` | max_length=0 與 min 6 互斥→任何房間密碼皆 422，無法建立密碼房 | RoomCreate(password='secret1') 應成功 |
| 806 | 39 | `<class RoomUpdate>` | `1` → `2` | 改名為 1 字元被誤拒 | RoomUpdate(name='a') 應通過驗證 |
| 807 | 39 | `<class RoomUpdate>` | `100` → `101` | 可寫入 101 字名稱但 RoomInDB 上限 100→該房與公開列表對所有人 500 | 參數化：RoomUpdate 與 RoomBase 的 name/描述/max_members 邊界一致 |
| 809 | 40 | `<class RoomUpdate>` | `500` → `501` | 可寫入 501 字描述但 RoomInDB 上限 500→該房與公開列表對所有人 500 | 參數化：RoomUpdate 與 RoomBase 的 name/描述/max_members 邊界一致 |
| 811 | 44 | `<class RoomUpdate>` | `2` → `3` | max_members 更新為 2 被誤拒 | RoomUpdate(max_members=2) 應通過驗證 |
| 812 | 44 | `<class RoomUpdate>` | `2` → `0` | 僅房主時可設 max_members=1，RoomInDB(ge=2) 讀不回→房間/列表 500 | RoomUpdate(max_members=1) 應 ValidationError |
| 813 | 44 | `<class RoomUpdate>` | `1000` → `1001` | 可設 max_members=1001，RoomInDB(le=1000) 讀不回→房間/列表 500 | RoomUpdate(max_members=1001) 應 ValidationError |
| 815 | 45 | `<class RoomUpdate>` | `6` → `7` | 更新房間密碼為 6 字元被誤拒 | RoomCreate/RoomUpdate password 5 字元 422、6 字元通過 |
| 818 | 45 | `<class RoomUpdate>` | `128` → `0` | max_length=0→無法將房間密碼更新為任何非空值 | RoomUpdate(password='secret1') 應通過驗證 |
| 787 | 82 | `serialize_datetime` | `is` → `is not` | DB 讀出的 naive 時間不補 UTC，ISO 字串缺時區→前端時間偏移 | naive datetime 序列化須以 +00:00 結尾且非 null |
| 782 | 84 | `serialize_datetime` | `dt.isoformat()` → `None` | 房間 created_at/updated_at 序列化為 null（API 與 WS 皆是） | naive datetime 序列化須以 +00:00 結尾且非 null |

### `app/models/user.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 835 | 13 | `<class UserBase>` | `3` → `4` | 3 字元使用者名稱註冊被拒，且既有 3 字元使用者載入失敗 | 註冊 username='abc' 應 201、'ab' 應 422 |
| 836 | 13 | `<class UserBase>` | `3` → `0` | 允許空或 1 字元使用者名稱 | 註冊 username='ab' 與 '' 應 422 |
| 839 | 23 | `<class UserCreate>` | `6` → `7` | 6 字元密碼註冊被誤拒 | 註冊/改密碼/PUT profile：5 字元 422、6 字元成功 |
| 841 | 32 | `<class UserUpdate>` | `6` → `7` | PUT /auth/profile 設 6 字元密碼被誤拒 | 註冊/改密碼/PUT profile：5 字元 422、6 字元成功 |
| 831 | 61 | `serialize_datetime` | `is` → `is not` | 所有非 None 時間皆序列化為 null | naive datetime 序列化須以 +00:00 結尾且非 null |
| 832 | 63 | `serialize_datetime` | `is` → `is not` | naive 時間不補 UTC，使用者時間字串缺時區標記 | naive datetime 序列化須以 +00:00 結尾且非 null |
| 827 | 67 | `serialize_datetime` | `dt.isoformat()` → `None` | 使用者 created_at/updated_at 序列化為 null | naive datetime 序列化須以 +00:00 結尾且非 null |
| 848 | 97 | `<class PasswordChange>` | `6` → `7` | 改密碼時 6 字元新密碼被誤拒 | 註冊/改密碼/PUT profile：5 字元 422、6 字元成功 |

### `app/repositories/base.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 873 | 57 | `find_many` | `0` → `1` | get_by_ids 依賴預設 skip→跳過一位使用者，成員列表/訊息頭像缺人 | 真實 DB 測 get_by_ids 3 個 id 回 3 筆且保序 |
| 856 | 62 | `find_many` | `sort` → `not (sort)` | 有 sort 時不排序；無 sort 時迭代 None→get_by_ids/回覆預覽 TypeError | find_many 無 sort 不拋錯；有 sort 時結果依 created_at 降冪 |
| 894 | 64 | `find_many` | `not in` → `in` | 不再追加 _id tiebreaker，同時間戳資料分頁順序不穩定 | 插入同 created_at 多筆，斷言依 _id 降冪且分頁不重疊 |
| 880 | 103 | `update_one` | `update["$set"] = {"updated_at": now}` → `pass` | remove_member 不再更新 updated_at；非成員離開由 200 變 400 | remove_member 後 updated_at 變大；非成員 leave 行為明確斷言 |

### `app/repositories/message_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1006 | 31 | `__init__` | `"messages"` → `"XXmessagesXX"` | 寫到別的 collection：client_id 唯一索引失效致併發重複訊息，既有訊息全不可見 | 斷言 collection 名為 messages，併發同 client_id 只存一筆 |
| 947 | 95 | `get_with_reply` | `message.reply_to` → `not (message.reply_to)` | 有 reply_to 時不取預覽：GET 單則訊息與 @bot 回覆廣播缺引用區塊 | test_get_with_reply 斷言 reply_to_message.content/username 正確 |
| 969 | 97 | `get_with_reply` | `reply_msg` → `not (reply_msg)` | 被回覆訊息存在時預覽為 None；不存在時 None.id 拋 AttributeError | 斷言有效 reply 帶預覽、被回覆訊息不存在時回傳 None 預覽不拋錯 |
| 980 | 188 | `update` | `is not` → `is` | 只改 content 時把 metadata 設成 null（API 可清掉檔案資訊），給 metadata 反被忽略 | 編輯帶 metadata 的訊息只改 content，斷言 metadata 保留 |
| 989 | 243 | `get_room_messages` | `False` → `True` | 軟刪除過濾失效：歷史/REST/@bot/summary 重新出現「此訊息已被刪除」佔位訊息 | 刪除一則後 get_room_messages 不應包含該則（含 WS 歷史） |
| 990 | 263 | `get_room_messages` | `not` → `` | 軟刪除過濾失效：歷史/REST/@bot/summary 重新出現「此訊息已被刪除」佔位訊息 | 刪除一則後 get_room_messages 不應包含該則（含 WS 歷史） |
| 991 | 264 | `get_room_messages` | `query["status"] = {"$ne": MessageStatus.DELETED}` → `pass` | 軟刪除過濾失效：歷史/REST/@bot/summary 重新出現「此訊息已被刪除」佔位訊息 | 刪除一則後 get_room_messages 不應包含該則（含 WS 歷史） |
| 1025 | 264 | `get_room_messages` | `"status"` → `"XXstatusXX"` | 軟刪除過濾失效：歷史/REST/@bot/summary 重新出現「此訊息已被刪除」佔位訊息 | 刪除一則後 get_room_messages 不應包含該則（含 WS 歷史） |
| 958 | 280 | `get_room_messages` | `messages.reverse()` → `pass` | 歷史變新→舊；前端 REST 載入不重排而倒序顯示，@bot 歷史配對與摘要逐字稿亦錯 | 建立 3 則後斷言 get_room_messages 依 created_at/seq 由舊到新 |
| 1014 | 343 | `search_messages` | `"status"` → `"XXstatusXX"` | 搜尋結果包含已軟刪除訊息（佔位內容） | 刪除一則後搜尋其內容/佔位字，結果不應含該則 |
| 1001 | 355 | `search_messages` | `or` → `and` | 只帶 start_date 或 end_date 時日期篩選整個被忽略 | 只帶 start_date 搜尋，斷言較早訊息被排除 |

### `app/repositories/notification_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1114 | 46 | `update` | `is not` → `is` | 單筆標記已讀時 read_at 不寫入，通知仍顯示未有閱讀時間 | mark_as_read 後 get_by_id 斷言 status=read 且 read_at 不為 None |
| 1116 | 48 | `update` | `is not` → `is` | 未帶 metadata 的更新改為把 metadata 設 None：標記已讀即清空跳轉資訊 | 標記已讀後斷言 metadata（room_id/message_id）原樣保留 |
| 1184 | 132 | `get_stats` | `1` → `2` | by_status 計數加倍：unread/read/total 全錯，徽章與 WS stats 未讀數翻倍 | 1 未讀 1 已讀後 get_stats 以 == 斷言 unread=1、read=1、total=2 |
| 1186 | 134 | `get_stats` | `1` → `2` | by_type 計數加倍：type_counts 錯誤，前端 by_type 統計翻倍 | get_stats 以 == 斷言 type_counts == {message:2, system:1} |
| 1179 | 141 | `get_stats` | `0` → `1` | recent 內含 ObjectId _id，GET /notifications/stats 序列化失敗回 500 | API 測試：有通知時 GET /notifications/stats 回 200，recent 項目不含 _id |

### `app/repositories/room_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1248 | 20 | `__init__` | `"rooms"` → `"XXroomsXX"` | 集合改名→indexes.py 的 name/invite_code 唯一索引不覆蓋，既有房間全消失 | 斷言 RoomRepository(db).collection.name == 'rooms' |
| 1302 | 108 | `get_user_rooms` | `"updated_at"` → `"XXupdated_atXX"` | 「我的房間」不再依最近更新時間排序 | 較舊房間更新後應排在 get_user_rooms 第一筆 |
| 1305 | 160 | `search_rooms` | `"name"` → `"XXnameXX"` | 搜尋結果不再依名稱字母序排列 | search_rooms 斷言結果依 name 升冪 |

### `app/repositories/user_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1350 | 94 | `update` | `!=` → `==` | 送出本人現有 email 被當衝突回 None，服務層轉成 404 | PUT /api/auth/profile 帶本人原 email 與新 full_name，應 200 |

### `app/security_config.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1595 | 40 | `get_hsts_header` | `"; ".join(parts)` → `None` | HSTS 值為 None，HTTPS 回應設定標頭時拋錯變 500 | 生產設定 app 帶 X-Forwarded-Proto: https，斷言 STS 完整值且 200 |
| 1624 | 40 | `get_hsts_header` | `"; "` → `"XX; XX"` | HSTS 字串毀損（max-age 非數字），瀏覽器忽略整個 HSTS | 斷言 get_hsts_header() 為完整 max-age; includeSubDomains; preload |
| 1596 | 44 | `get_csp_header` | `self.development_mode` → `not (self.development_mode)` | 生產 CSP 換成開發寬鬆版（unsafe-inline/eval、任意連線） | development_mode=False 時斷言 CSP 為嚴格版且無 unsafe-eval |
| 1611 | 58 | `get_csp_header` | `"default-src 'self'; " "script-src 'self'; " "s…` → `"XXdefault-src 'self'; script…` | 生產 CSP 字串毀損，default-src 指令失效 | 斷言生產 get_csp_header() 以 "default-src 'self';" 開頭 |
| 1606 | 78 | `get_security_headers` | `not` → `` | 自訂安全標頭全失效，生產退回 base 寬鬆 CSP（unsafe-inline/eval） | 生產設定下 app 回應的 CSP 應等於 get_csp_header() 嚴格版 |
| 1630 | 84 | `get_security_headers` | `"nosniff"` → `"XXnosniffXX"` | X-Content-Type-Options 值無效，生產失去 nosniff | app 回應斷言 X-Content-Type-Options == 'nosniff' |
| 1599 | 100 | `get_security_headers` | `self.enable_csp` → `not (self.enable_csp)` | 嚴格 CSP 未寫入自訂標頭，生產退回 base 寬鬆 CSP | 生產設定下 app 回應的 CSP 應等於 get_csp_header() 嚴格版 |
| 1613 | 102 | `get_security_headers` | `self.csp_report_only` → `not (self.csp_report_only)` | 嚴格 CSP 變 Report-Only，實際強制的是 base 寬鬆 CSP | 預設設定下回應不得有 CSP-Report-Only，CSP 為嚴格版 |
| 1637 | 104 | `get_security_headers` | `"Content-Security-Policy"` → `"XXContent-Security-PolicyXX"` | CSP 鍵名錯，嚴格 CSP 未生效，強制的是 base 寬鬆 CSP | 生產設定下 app 回應的 CSP 應等於 get_csp_header() 嚴格版 |
| 1609 | 106 | `get_security_headers` | `headers[header_name] = self.get_csp_header()` → `pass` | 嚴格 CSP 未寫入自訂標頭，生產退回 base 寬鬆 CSP | 生產設定下 app 回應的 CSP 應等於 get_csp_header() 嚴格版 |
| 1600 | 108 | `get_security_headers` | `headers` → `None` | 自訂安全標頭全失效，生產退回 base 寬鬆 CSP（unsafe-inline/eval） | 生產設定下 app 回應的 CSP 應等於 get_csp_header() 嚴格版 |
| 1614 | 115 | `load_security_config` | `==` → `!=` | HSTS 開關解析錯，未設環境變數時生產完全不送 HSTS | 清空 SECURITY_* 後斷言 load_security_config().enable_hsts is True |
| 1638 | 115 | `load_security_config` | `"true"` → `"XXtrueXX"` | HSTS 開關解析錯，未設環境變數時生產完全不送 HSTS | 清空 SECURITY_* 後斷言 load_security_config().enable_hsts is True |
| 1652 | 115 | `load_security_config` | `"true"` → `"XXtrueXX"` | HSTS 開關解析錯，未設環境變數時生產完全不送 HSTS | 清空 SECURITY_* 後斷言 load_security_config().enable_hsts is True |
| 1617 | 122 | `load_security_config` | `==` → `!=` | CSP 開關解析錯，未設環境變數時完全不送 CSP | 清空 SECURITY_* 後斷言 enable_csp is True 且回應含 CSP |
| 1641 | 122 | `load_security_config` | `"true"` → `"XXtrueXX"` | CSP 開關解析錯，未設環境變數時完全不送 CSP | 清空 SECURITY_* 後斷言 enable_csp is True 且回應含 CSP |
| 1658 | 122 | `load_security_config` | `"true"` → `"XXtrueXX"` | CSP 開關解析錯，未設環境變數時完全不送 CSP | 清空 SECURITY_* 後斷言 enable_csp is True 且回應含 CSP |
| 1618 | 123 | `load_security_config` | `==` → `!=` | report_only 解析反轉，嚴格 CSP 僅報告、強制者為寬鬆版 | 清空 SECURITY_* 後斷言 csp_report_only is False |
| 1619 | 126 | `load_security_config` | `==` → `!=` | 安全標頭總開關解析錯，生產退回 base 寬鬆 CSP | 清空 SECURITY_* 後斷言 enable_security_headers is True |
| 1662 | 126 | `load_security_config` | `"true"` → `"XXtrueXX"` | 安全標頭總開關解析錯，生產退回 base 寬鬆 CSP | 清空 SECURITY_* 後斷言 enable_security_headers is True |
| 1644 | 127 | `load_security_config` | `"true"` → `"XXtrueXX"` | 安全標頭總開關解析錯，生產退回 base 寬鬆 CSP | 清空 SECURITY_* 後斷言 enable_security_headers is True |

### `app/services/ai_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1669 | 27 | `<module>` | `2048` → `0` | max_tokens=0：供應商拒絕或空回覆，@bot 與 /summary 全數失敗 | 斷言兩供應商模型 settings 的 max_tokens 等於常數且 >0 |
| 1696 | 64 | `_build_gemini_model` | `"thinking_budget"` → `"XXthinking_budgetXX"` | Gemini thinking_budget 失效：思考 token 吃掉額度截斷回覆或 SDK 拒收 | 斷言 Gemini 模型 google_thinking_config 為 thinking_budget=0 |
| 1695 | 159 | `stream_reply` | `True` → `False` | stream_text(delta=False) 回傳累積全文，handler 再累加→預覽與落地回覆重複亂碼 | 以多 chunk 串流 FunctionModel 斷言 yield 的片段串接等於完整回覆 |

### `app/services/message_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1782 | 63 | `validate_message_content` | `>` → `>=` | 長度檢查 >→>=：恰好 2000 字元訊息被拒，與 Pydantic max_length=2000 不一致 | validate_message_content 2000 字元通過、2001 字元拋 AppError |
| 1773 | 292 | `_format_with_avatars` | `unique_user_ids` → `not (unique_user_ids)` | 有訊息時不查使用者，歷史/同步訊息頭像全為 None | test_get_room_messages 斷言 avatar 等於使用者頭像 |
| 1803 | 304 | `_format_with_avatars` | `msg_dict["avatar"] = avatar_map.get(msg.user_id)` → `pass` | 歷史/gap 補發訊息頭像遺失（avatar 一律 None） | 使用者有 avatar 時，get_room_messages 與 sync 回傳 avatar 正確 |
| 1838 | 304 | `_format_with_avatars` | `"avatar"` → `"XXavatarXX"` | 歷史/gap 補發訊息頭像遺失（avatar 一律 None） | 使用者有 avatar 時，get_room_messages 與 sync 回傳 avatar 正確 |
| 1805 | 319 | `_attach_reply_previews` | `reply_ids` → `not (reply_ids)` | 訊息列表 reply_to_message 引用預覽遺失 | 列表中回覆訊息斷言 reply_to_message.content 為被回覆內容 |
| 1842 | 324 | `_attach_reply_previews` | `r.reply_to` → `not (r.reply_to)` | 訊息列表 reply_to_message 引用預覽遺失 | 列表中回覆訊息斷言 reply_to_message.content 為被回覆內容 |
| 1810 | 357 | `update_message` | `is not` → `is` | 編輯跳過 strip/空白檢查；只改 metadata/status 時 None.strip 造成 500 | PUT 內容 '   ' 應 400；只帶 metadata 應 200 |
| 1811 | 358 | `update_message` | `update_data.content = self.validate_message_con…` → `pass` | 編輯路徑不驗證內容：純空白可通過、前後空白未去除，與 HTTP/WS 發送規則不一致 | update_message 內容為空白應拋 AppError，且儲存值已 strip |

### `app/services/notification_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1913 | 63 | `_create_notification_business_logic` | `or` → `and` | or→and：有 metadata 時被換成 {}，訊息通知遺失 message_id/room_name 等跳轉資訊 | 發送訊息通知後 DB metadata 應含 message_id、room_id |

### `app/services/room_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2081 | 60 | `_convert_to_summary` | `False` → `True` | WS room_created/updated 對所有人帶 is_member=True，前端誤判已加入 | _convert_to_summary 無 user_id 時 is_member is False |
| 1970 | 69 | `_convert_to_response` | `room_data["is_member"] = True` → `pass` | 成員的 RoomResponse is_member=False，BFF 誤判非成員顯示加入彈窗 | _convert_to_response 斷言 is_member is True |
| 1997 | 69 | `_convert_to_response` | `True` → `False` | 成員的 RoomResponse is_member=False，BFF 誤判非成員 | _convert_to_response 斷言 is_member is True |
| 2082 | 69 | `_convert_to_response` | `"is_member"` → `"XXis_memberXX"` | is_member 寫到錯誤鍵，成員回應 is_member=False | _convert_to_response 斷言 is_member is True |
| 1999 | 108 | `_notify_room_change` | `updated_room` → `not (updated_room)` | 房間存在時不廣播 room_updated，列表人數不即時更新 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2138 | 110 | `_notify_room_change` | `"type"` → `"XXtypeXX"` | room_updated 事件缺 type，被前端 guard 丟棄 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2139 | 110 | `_notify_room_change` | `"room"` → `"XXroomXX"` | room_updated 事件缺 room 欄位，前端判為無效資料 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2140 | 110 | `_notify_room_change` | `"room_updated"` → `"XXroom_updatedXX"` | 事件 type 變成未知值，被前端丟棄 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2086 | 111 | `_notify_room_change` | `await self._broadcast_room_event(message)` → `pass` | room_updated 完全不廣播 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2088 | 150 | `create_room` | `or` → `and` | 公開邀請制房未給邀請碼時不產生→無人能加入 | 公開 INVITE 房未給 code 時應自動產生 invite_code |
| 2112 | 150 | `create_room` | `==` → `!=` | 公開邀請制房不產生邀請碼；DIRECT/PASSWORD 房反被多產生 | 公開 DIRECT 房 invite_code 為 None；INVITE 房非 None |
| 2114 | 190 | `create_room` | `"type"` → `"XXtypeXX"` | room_created 事件缺 type，被前端丟棄 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 2117 | 190 | `create_room` | `"room_created"` → `"XXroom_createdXX"` | room_created 事件 type 變未知值，被前端丟棄 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 2115 | 191 | `create_room` | `"room"` → `"XXroomXX"` | room_created 事件缺 room，前端無法加入列表 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 2006 | 194 | `create_room` | `await self._broadcast_room_event(message, exclu…` → `pass` | 新房間不即時廣播給其他線上使用者 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 2092 | 296 | `update_room` | `<` → `<=` | max_members 設為等於現有人數也被拒 | 5 人房更新 max_members=5 應成功 |
| 2028 | 300 | `update_room` | `is not` → `is` | 改名略過 Service 唯一性檢查，只靠 DB 索引回通用 409 訊息 | 改成他房名稱應拋 ConflictError「房間名稱已存在」 |
| 1982 | 325 | `update_room` | `await self._notify_room_change(room_id)` → `pass` | update_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2124 | 420 | `join_room` | `or` → `and` | 空 body 或 password=null 時 500，而非 400「需要提供密碼」 | 密碼房以 None 與 RoomJoinRequest() 加入皆拋 AppError |
| 1986 | 464 | `join_room` | `await self._notify_room_change(room_id)` → `pass` | join_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2106 | 536 | `leave_room` | `not` → `` | user_left 的 user 錯置：線上者丟 username、離線者缺 id | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2151 | 537 | `leave_room` | `"id"` → `"XXidXX"` | 離線者離開時 user 缺 id，前端無法自成員列表移除 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2063 | 538 | `leave_room` | `await self._connection_manager.broadcast_to_roo…` → `pass` | 其他成員收不到 user_left，成員列表殘留 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2160 | 541 | `leave_room` | `"type"` → `"XXtypeXX"` | user_left 缺 type，被前端丟棄 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2165 | 541 | `leave_room` | `"user_left"` → `"XXuser_leftXX"` | user_left type 變未知值，被前端丟棄 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2161 | 542 | `leave_room` | `"user"` → `"XXuserXX"` | user_left 缺 user，前端 handler 取 user.id 失敗 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2162 | 543 | `leave_room` | `"timestamp"` → `"XXtimestampXX"` | 缺 timestamp→前端不顯示「離開了聊天室」系統訊息 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2164 | 545 | `leave_room` | `"removed"` → `"XXremovedXX"` | 缺 removed→離開者僅標為離線而非自成員列表移除 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2166 | 545 | `leave_room` | `True` → `False` | removed=False→離開者僅標為離線而非自成員列表移除 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 1990 | 552 | `leave_room` | `await self._notify_room_change(room_id)` → `pass` | leave_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2065 | 557 | `get_room_members` | `0` → `1` | WS 通知走預設 skip→members[0]（房主）收不到訊息通知 | get_room_members(room_id) 預設應含第一位成員 |
| 2068 | 572 | `get_room_members` | `not` → `` | 存在的房間回空成員列表、訊息通知全數不發 | get_room_members 對有成員房間回傳對應 UserResponse |

### `app/services/user_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2193 | 152 | `update_user` | `False` → `True` | 任何資料更新都遞增版本，改頭像/名稱即全裝置登出 | PUT /profile 只改 full_name 後，原 token 打 /me 仍應 200 |
| 2254 | 305 | `refresh_access_token` | `"token_version"` → `"XXtoken_versionXX"` | refresh 端版本恆為 0，改過密碼者 refresh 永遠失敗被迫重登 | token_version=1 使用者以新 refresh token 換發應成功 |
| 2243 | 312 | `refresh_access_token` | `"token_version"` → `"XXtoken_versionXX"` | 換發的新 token 不帶版本，改過密碼者 refresh 後立刻 401 | token_version=1 使用者 refresh 後新 token 應帶版本 1 |

### `app/utils/file_upload.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2342 | 19 | `<module>` | `".jpg"` → `"XX.jpgXX"` | .jpg 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2343 | 19 | `<module>` | `".jpeg"` → `"XX.jpegXX"` | .jpeg 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2344 | 19 | `<module>` | `".png"` → `"XX.pngXX"` | .png 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2345 | 19 | `<module>` | `".gif"` → `"XX.gifXX"` | .gif 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2346 | 19 | `<module>` | `".webp"` → `"XX.webpXX"` | .webp 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2347 | 19 | `<module>` | `".bmp"` → `"XX.bmpXX"` | .bmp 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2348 | 21 | `<module>` | `"image/jpeg"` → `"XXimage/jpegXX"` | .jpg 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2349 | 22 | `<module>` | `"image/jpeg"` → `"XXimage/jpegXX"` | .jpeg 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2350 | 23 | `<module>` | `"image/png"` → `"XXimage/pngXX"` | .png 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2351 | 24 | `<module>` | `"image/gif"` → `"XXimage/gifXX"` | .gif 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2352 | 25 | `<module>` | `"image/webp"` → `"XXimage/webpXX"` | .webp 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2353 | 26 | `<module>` | `"image/bmp"` → `"XXimage/bmpXX"` | .bmp 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2355 | 28 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2426 | 28 | `<module>` | `10` → `11` | 圖片上限由 10MB 放寬為 11MB | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2428 | 28 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2272 | 30 | `<module>` | `"document"` → `"XXdocumentXX"` | 類別 document 改名：file_type 與 URL 路徑改變，BFF 下載白名單拒絕，該類檔案無法下載 | 上傳後斷言 file_type=='document'、url 以 /api/files/document/ 開頭 |
| 2357 | 31 | `<module>` | `".pdf"` → `"XX.pdfXX"` | .pdf 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2358 | 31 | `<module>` | `".doc"` → `"XX.docXX"` | .doc 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2359 | 31 | `<module>` | `".docx"` → `"XX.docxXX"` | .docx 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2360 | 31 | `<module>` | `".txt"` → `"XX.txtXX"` | .txt 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2361 | 31 | `<module>` | `".md"` → `"XX.mdXX"` | .md 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2362 | 33 | `<module>` | `"application/pdf"` → `"XXapplication/pdfXX"` | .pdf 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2313 | 39 | `<module>` | `"max_size"` → `"XXmax_sizeXX"` | 文件 max_size 鍵不存在：非空文件上傳 KeyError 回 500 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2314 | 39 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2367 | 39 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2368 | 39 | `<module>` | `1024` → `1025` | 文件上限 50MB 微幅放寬（1024→1025），超規格檔被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2369 | 39 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2430 | 39 | `<module>` | `50` → `51` | 文件上限由 50MB 放寬為 51MB | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2431 | 39 | `<module>` | `50` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2432 | 39 | `<module>` | `1024` → `1025` | 文件上限 50MB 微幅放寬（1024→1025），超規格檔被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2433 | 39 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2273 | 41 | `<module>` | `"video"` → `"XXvideoXX"` | 類別 video 改名：file_type 與 URL 路徑改變，BFF 下載白名單拒絕，該類檔案無法下載 | 上傳後斷言 file_type=='video'、url 以 /api/files/video/ 開頭 |
| 2370 | 42 | `<module>` | `".mp4"` → `"XX.mp4XX"` | .mp4 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2371 | 42 | `<module>` | `".mov"` → `"XX.movXX"` | .mov 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2372 | 42 | `<module>` | `".avi"` → `"XX.aviXX"` | .avi 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2373 | 42 | `<module>` | `".mkv"` → `"XX.mkvXX"` | .mkv 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2374 | 42 | `<module>` | `".webm"` → `"XX.webmXX"` | .webm 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2375 | 44 | `<module>` | `"video/mp4"` → `"XXvideo/mp4XX"` | .mp4 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2376 | 45 | `<module>` | `"video/quicktime"` → `"XXvideo/quicktimeXX"` | .mov 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2377 | 46 | `<module>` | `"video/x-msvideo"` → `"XXvideo/x-msvideoXX"` | .avi 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2378 | 47 | `<module>` | `"video/x-matroska"` → `"XXvideo/x-matroskaXX"` | .mkv 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2379 | 48 | `<module>` | `"video/webm"` → `"XXvideo/webmXX"` | .webm 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2317 | 50 | `<module>` | `"max_size"` → `"XXmax_sizeXX"` | 影片 max_size 鍵不存在：非空影片上傳 KeyError 回 500 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2318 | 50 | `<module>` | `*` → `/` | *→/ 使影片上限變 100 位元組，幾乎所有影片被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2380 | 50 | `<module>` | `*` → `/` | *→/ 使影片上限變 100 位元組，幾乎所有影片被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2381 | 50 | `<module>` | `1024` → `1025` | 影片上限 100MB 微幅放寬（1024→1025），超規格檔被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2382 | 50 | `<module>` | `1024` → `0` | 影片上限變 0，所有非空影片被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2434 | 50 | `<module>` | `100` → `101` | 影片上限由 100MB 放寬為 101MB | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2435 | 50 | `<module>` | `100` → `0` | 影片上限變 0，所有非空影片被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2436 | 50 | `<module>` | `1024` → `1025` | 影片上限 100MB 微幅放寬（1024→1025），超規格檔被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2437 | 50 | `<module>` | `1024` → `0` | 影片上限變 0，所有非空影片被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2274 | 52 | `<module>` | `"audio"` → `"XXaudioXX"` | 類別 audio 改名：file_type 與 URL 路徑改變，BFF 下載白名單拒絕，該類檔案無法下載 | 上傳後斷言 file_type=='audio'、url 以 /api/files/audio/ 開頭 |
| 2383 | 53 | `<module>` | `".mp3"` → `"XX.mp3XX"` | .mp3 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2384 | 53 | `<module>` | `".wav"` → `"XX.wavXX"` | .wav 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2385 | 53 | `<module>` | `".ogg"` → `"XX.oggXX"` | .ogg 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2386 | 53 | `<module>` | `".m4a"` → `"XX.m4aXX"` | .m4a 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2387 | 53 | `<module>` | `".flac"` → `"XX.flacXX"` | .flac 移出副檔名表：類型改依客戶端 MIME（非標準 MIME 的合法檔被拒），下載變 octet-stream | 參數化：各副檔名配 octet-stream MIME 仍判正確類型，get_mime_type 正確 |
| 2321 | 61 | `<module>` | `"max_size"` → `"XXmax_sizeXX"` | 音檔 max_size 鍵不存在：非空音檔上傳 KeyError 回 500 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2322 | 61 | `<module>` | `*` → `/` | *→/ 使音檔上限變 20 位元組，幾乎所有音檔被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2393 | 61 | `<module>` | `*` → `/` | *→/ 使音檔上限變 20 位元組，幾乎所有音檔被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2394 | 61 | `<module>` | `1024` → `1025` | 音檔上限 20MB 微幅放寬（1024→1025），超規格檔被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2395 | 61 | `<module>` | `1024` → `0` | 音檔上限變 0，所有非空音檔被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2438 | 61 | `<module>` | `20` → `21` | 音檔上限由 20MB 放寬為 21MB | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2439 | 61 | `<module>` | `20` → `0` | 音檔上限變 0，所有非空音檔被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2440 | 61 | `<module>` | `1024` → `1025` | 音檔上限 20MB 微幅放寬（1024→1025），超規格檔被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2441 | 61 | `<module>` | `1024` → `0` | 音檔上限變 0，所有非空音檔被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2275 | 73 | `<module>` | `_EXT_TO_TYPE[_ext] = _file_type` → `pass` | 副檔名→類型表清空：類型全由客戶端 Content-Type 決定，可錯置類別與大小上限 | 上傳 x.png 但 content_type=video/mp4，應判 image 並套 10MB 上限 |
| 2276 | 74 | `<module>` | `_EXT_TO_MIME[_ext] = _mime` → `pass` | 副檔名→MIME 表清空：所有下載 Content-Type 變 octet-stream，圖片/PDF 無法內嵌 | 斷言 get_mime_type 對 .png/.pdf 回 image/png、application/pdf |
| 2279 | 88 | `<module>` | `".jpeg"` → `"XX.jpegXX"` | .jpeg 移出簽章表：magic-byte 檢查被跳過，偽裝成 .jpeg 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2443 | 88 | `<module>` | `0` → `1` | .jpeg 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2280 | 89 | `<module>` | `".png"` → `"XX.pngXX"` | .png 移出簽章表：magic-byte 檢查被跳過，偽裝成 .png 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2281 | 90 | `<module>` | `".gif"` → `"XX.gifXX"` | .gif 移出簽章表：magic-byte 檢查被跳過，偽裝成 .gif 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2446 | 90 | `<module>` | `0` → `1` | .gif 的 GIF89a 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2283 | 92 | `<module>` | `".bmp"` → `"XX.bmpXX"` | .bmp 移出簽章表：magic-byte 檢查被跳過，偽裝成 .bmp 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2450 | 92 | `<module>` | `0` → `1` | .bmp 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2284 | 93 | `<module>` | `".pdf"` → `"XX.pdfXX"` | .pdf 移出簽章表：magic-byte 檢查被跳過，偽裝成 .pdf 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2451 | 93 | `<module>` | `0` → `1` | .pdf 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2285 | 94 | `<module>` | `".doc"` → `"XX.docXX"` | .doc 移出簽章表：magic-byte 檢查被跳過，偽裝成 .doc 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2452 | 94 | `<module>` | `0` → `1` | .doc 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2286 | 95 | `<module>` | `".docx"` → `"XX.docxXX"` | .docx 移出簽章表：magic-byte 檢查被跳過，偽裝成 .docx 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2453 | 95 | `<module>` | `0` → `1` | .docx 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2287 | 96 | `<module>` | `".mp4"` → `"XX.mp4XX"` | .mp4 移出簽章表：magic-byte 檢查被跳過，偽裝成 .mp4 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2454 | 96 | `<module>` | `4` → `5` | .mp4 ftyp offset 4→5：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2455 | 96 | `<module>` | `4` → `0` | .mp4 ftyp offset 4→0：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2288 | 97 | `<module>` | `".mov"` → `"XX.movXX"` | .mov 移出簽章表：magic-byte 檢查被跳過，偽裝成 .mov 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2456 | 97 | `<module>` | `4` → `5` | .mov ftyp offset 4→5：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2457 | 97 | `<module>` | `4` → `0` | .mov ftyp offset 4→0：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2289 | 98 | `<module>` | `".m4a"` → `"XX.m4aXX"` | .m4a 移出簽章表：magic-byte 檢查被跳過，偽裝成 .m4a 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2458 | 98 | `<module>` | `4` → `5` | .m4a ftyp offset 4→5：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2459 | 98 | `<module>` | `4` → `0` | .m4a ftyp offset 4→0：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2290 | 99 | `<module>` | `".avi"` → `"XX.aviXX"` | .avi 移出簽章表：magic-byte 檢查被跳過，偽裝成 .avi 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2460 | 99 | `<module>` | `0` → `1` | .avi RIFF offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2461 | 99 | `<module>` | `8` → `9` | .avi 'AVI ' offset 8→9：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2462 | 99 | `<module>` | `8` → `0` | .avi 'AVI ' offset 8→0（與 RIFF 互斥）：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2291 | 100 | `<module>` | `".mkv"` → `"XX.mkvXX"` | .mkv 移出簽章表：magic-byte 檢查被跳過，偽裝成 .mkv 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2463 | 100 | `<module>` | `0` → `1` | .mkv 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2292 | 101 | `<module>` | `".webm"` → `"XX.webmXX"` | .webm 移出簽章表：magic-byte 檢查被跳過，偽裝成 .webm 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2464 | 101 | `<module>` | `0` → `1` | .webm 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2293 | 102 | `<module>` | `".mp3"` → `"XX.mp3XX"` | .mp3 移出簽章表：magic-byte 檢查被跳過，偽裝成 .mp3 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2465 | 102 | `<module>` | `0` → `1` | .mp3 ID3 簽章 offset 0→1（帶 ID3 標籤者）：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2466 | 102 | `<module>` | `0` → `1` | .mp3 \xff\xfb 簽章 offset 0→1（無標籤 MPEG-1）：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2294 | 103 | `<module>` | `".wav"` → `"XX.wavXX"` | .wav 移出簽章表：magic-byte 檢查被跳過，偽裝成 .wav 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2469 | 103 | `<module>` | `0` → `1` | .wav RIFF offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2470 | 103 | `<module>` | `8` → `9` | .wav WAVE offset 8→9：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2471 | 103 | `<module>` | `8` → `0` | .wav WAVE offset 8→0（與 RIFF 互斥）：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2295 | 104 | `<module>` | `".ogg"` → `"XX.oggXX"` | .ogg 移出簽章表：magic-byte 檢查被跳過，偽裝成 .ogg 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2472 | 104 | `<module>` | `0` → `1` | .ogg 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2296 | 105 | `<module>` | `".flac"` → `"XX.flacXX"` | .flac 移出簽章表：magic-byte 檢查被跳過，偽裝成 .flac 的任意內容可上傳 | 參數化所有簽章副檔名：偽造內容 save_file 應拋「檔案內容與副檔名不符」 |
| 2473 | 105 | `<module>` | `0` → `1` | .flac 簽章 offset 0→1：真實檔案被誤拒為內容不符 | 參數化：每種格式的真實檔頭樣本 _matches_magic 應回 True |
| 2325 | 132 | `__init__` | `"uploads"` → `"XXuploadsXX"` | 上傳寫入 XXuploadsXX，但下載依 settings.UPLOAD_DIR=uploads，所有檔案下載 404 | 上傳後以 resolve_download 取回同檔；manager 目錄應等於 settings.UPLOAD_DIR |
| 2327 | 156 | `get_file_type` | `or` → `and` | or→and：已知副檔名改由 MIME 決定類型，且非標準 MIME 的合法檔被拒 | x.png 配 video/mp4 應判 image；x.wav 配 audio/x-wav 應被接受 |
| 2410 | 192 | `validate_file` | `"\\"` → `"XX\\XX"` | 反斜線（路徑分隔字元）不再被拒；儲存用產生檔名未實際穿越，但縱深防禦失效 | 參數化：含 / \ < > : 等字元的檔名 validate_file 應拋 FileUploadError |
| 2411 | 192 | `validate_file` | `"/"` → `"XX/XX"` | 「/」不再被拒，../ 形式檔名被接受；儲存用產生檔名未實際穿越，縱深防禦失效 | 參數化：含 / \ < > : 等字元的檔名 validate_file 應拋 FileUploadError |
| 2487 | 294 | `save_file` | `"path"` → `"XXpathXX"` | 缺 path 鍵：產生縮圖時 KeyError，所有圖片上傳回 500（檔案已落地成孤兒） | FileService 用真 FileUploadManager 上傳 PNG 應成功並含 thumbnails |
| 2489 | 296 | `save_file` | `"url"` → `"XXurlXX"` | 缺 url 鍵：前端「上傳回應中沒有檔案URL」，聊天檔案分享與頭像上傳全失敗 | save_file 回傳 url == f"/api/files/{file_type}/{filename}" |

### `app/utils/image_processor.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2513 | 13 | `<module>` | `"small"` → `"XXsmallXX"` | small 鍵改名：縮圖 API size=small 回 400，small 縮圖改用 300px | 上傳圖片後 resolve_thumbnail(size=small) 成功且縮圖寬高≤150 |
| 2514 | 13 | `<module>` | `"medium"` → `"XXmediumXX"` | medium 鍵消失：create_thumbnail 預設值 KeyError 未被捕捉，所有圖片上傳回 500 | 對真實圖片呼叫 create_multiple_thumbnails，三種尺寸皆產生 |
| 2515 | 13 | `<module>` | `"large"` → `"XXlargeXX"` | large 鍵改名：縮圖 API size=large 回 400，large 縮圖改用 300px | 上傳圖片後 resolve_thumbnail(size=large) 成功且縮圖寬高≤600 |
| 2522 | 13 | `<module>` | `150` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2524 | 13 | `<module>` | `150` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2526 | 13 | `<module>` | `300` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2528 | 13 | `<module>` | `300` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2530 | 13 | `<module>` | `600` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2532 | 13 | `<module>` | `600` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2534 | 39 | `__init__` | `"processed"` → `"XXprocessedXX"` | 輸出目錄改名，但 resolve_thumbnail 寫死 processed/thumbnails，縮圖恆 404 | 產生縮圖後 resolve_thumbnail 能找到同檔（兩處路徑應同源） |
| 2545 | 44 | `__init__` | `"thumbnails"` → `"XXthumbnailsXX"` | 縮圖子目錄改名，與 resolve_thumbnail 寫死路徑不一致，縮圖 API 恆 404 | 產生縮圖後 resolve_thumbnail 能找到同檔（兩處路徑應同源） |

### `app/utils/ws_ticket.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2686 | 16 | `<module>` | `30` → `0` | SETEX 0 秒被 Redis 拒絕，ticket 無法建立，WS 全部連不上 | create_ws_ticket 後斷言 TTL 介於 1–30 且 validate 一次成功、第二次失敗 |

### `app/websocket/handlers.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2809 | 78 | `_format_message_payload` | `"room_id"` → `"XXroom_idXX"` | 即時訊息缺 room_id：bot 預覽無法收掉、getMaxSeq 忽略即時訊息使重連 last_seq 過舊 | 斷言 _format_message_payload 輸出含 room_id 等完整前端 Message 欄位 |
| 2810 | 79 | `_format_message_payload` | `"user_id"` → `"XXuser_idXX"` | 即時訊息缺 user_id：自己訊息判斷、分組與 bot 預覽替換失效 | 斷言廣播 payload user_id 等於發送者 |
| 2811 | 82 | `_format_message_payload` | `"username"` → `"XXusernameXX"` | 即時訊息缺 top-level username，名稱空白（重整才正常） | 斷言廣播 payload username 等於發送者名稱 |
| 2812 | 83 | `_format_message_payload` | `"content"` → `"XXcontentXX"` | 即時訊息缺 content，所有人即時看到空白訊息 | 斷言廣播 payload content 等於已 strip 內容 |
| 2813 | 84 | `_format_message_payload` | `"message_type"` → `"XXmessage_typeXX"` | 即時訊息缺 message_type，圖片/檔案無法渲染 | image 訊息廣播 payload message_type=='image' |
| 2817 | 88 | `_format_message_payload` | `"created_at"` → `"XXcreated_atXX"` | 即時訊息缺 created_at：前端排序 NaN、時間顯示 Invalid Date | 斷言廣播 payload created_at 存在且可解析 |
| 2818 | 89 | `_format_message_payload` | `"metadata"` → `"XXmetadataXX"` | 即時訊息缺 metadata：檔案名稱/大小/類型不顯示 | file 訊息廣播 payload metadata 等於送出 metadata |
| 2819 | 90 | `_format_message_payload` | `"user"` → `"XXuserXX"` | 即時訊息缺 user 物件：前端頭像 fallback 失敗 | 斷言 payload['user'] 含 id/username/avatar |
| 2866 | 93 | `_format_message_payload` | `"avatar"` → `"XXavatarXX"` | payload.user.avatar 缺失且無 top-level avatar，即時訊息頭像消失 | 斷言 payload['user']['avatar'] 等於傳入 avatar |
| 2775 | 122 | `handle_websocket_connection` | `await websocket.accept()` → `pass` | 未 accept 即 close(4001)→握手被 403 拒，前端收 1006 非乾淨關閉而反覆重連 | 認證失敗時斷言先 accept 再以 4001 關閉 |
| 2917 | 266 | `handle_chat_message` | `"message_type"` → `"XXmessage_typeXX"` | 讀不到 message_type，WS 送出的圖片/檔案一律存成 TEXT | WS 送 message_type='image'，斷言 create_message 收到 IMAGE |
| 2835 | 270 | `handle_chat_message` | `"metadata"` → `"XXmetadataXX"` | 讀不到 metadata：檔案/圖片訊息的檔名、大小、MIME 永久遺失 | WS 帶 metadata 送 file 訊息，斷言持久化 metadata 相同 |
| 2883 | 293 | `handle_chat_message` | `"image"` → `"XXimageXX"` | image/file 類型比對失效，圖片或檔案訊息存成 TEXT | 參數化 image/file，斷言 msg_type 對應 IMAGE/FILE |
| 2919 | 295 | `handle_chat_message` | `"file"` → `"XXfileXX"` | image/file 類型比對失效，圖片或檔案訊息存成 TEXT | 參數化 image/file，斷言 msg_type 對應 IMAGE/FILE |
| 2978 | 321 | `handle_chat_message` | `"seq"` → `"XXseqXX"` | ack 缺 seq：自己訊息永遠沒有 seq，重連 last_seq 基準偏舊 | 斷言 ack.seq 等於 created_message.seq |
| 2921 | 329 | `handle_chat_message` | `"avatar"` → `"XXavatarXX"` | 即時訊息頭像讀錯鍵，一律 None | user_info 帶 avatar 時斷言廣播 payload user.avatar 相同 |
| 3026 | 349 | `handle_chat_message` | `10000` → `0` | 成員切片 limit=0 回空，任何成員都收不到新訊息通知 | 3 人房發訊息，斷言 send_message_notification 被呼叫 2 次 |
| 2925 | 361 | `handle_chat_message` | `+` → `-` | str - str TypeError 被 fail-open 吞掉，超過 50 字的訊息不發任何通知 | 51 字訊息斷言通知被送出且預覽為前 50 字+... |
| 2926 | 365 | `handle_chat_message` | `!=` → `==` | 通知只發給發送者自己，其他成員都收不到 | 斷言通知對象為除發送者外的所有成員，且不含發送者 |
| 2935 | 456 | `_broadcast_bot_error` | `"room_id"` → `"XXroom_idXX"` | bot_error 缺 room_id，前端無法收掉 streaming 預覽，卡在打字中 | 串流失敗時斷言 bot_error payload room_id 正確 |
| 2765 | 464 | `<module>` | `50` → `0` | 撈取 limit=0→to_list ValueError，fail-open 使 @bot 多輪記憶恆空 | 斷言 _load_bot_history 以 >0 的 limit 撈取並回非空歷史 |
| 2766 | 523 | `handle_bot_mention` | `_bot_streaming_rooms.add(room_id)` → `pass` | 同房並發鎖從未加上，兩個 @bot 同時串流混入同一預覽並雙倍呼叫 AI | 串流中（stream 阻塞）同房第二次 @bot 應收到「正在回覆中」錯誤 |
| 3055 | 542 | `handle_bot_mention` | `"room_id"` → `"XXroom_idXX"` | bot_typing 缺 room_id，前端直接丟棄，串流預覽完全不顯示 | 斷言 bot_typing payload 含 room_id/user/content |
| 2768 | 594 | `<module>` | `30` → `0` | /summary 撈取 limit=0→ValueError，摘要指令永遠失敗 | 斷言 summary 以 limit=SUMMARY_MESSAGE_LIMIT(>0) 撈取並成功落地 |
| 2943 | 684 | `handle_typing_indicator` | `"user"` → `"XXuserXX"` | typing 事件缺 user，前端解構 TypeError，打字指示器失效 | 斷言 typing 廣播 payload user 等於 user_info |
| 2804 | 874 | `send_recent_messages` | `50` → `0` | 預設 limit=0→ValueError，連線時歷史載入失敗並跳「無法載入歷史訊息」 | 連線後斷言收到 message_history 含最近訊息 |

### `app/websocket/manager.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 3239 | 125 | `connect` | `"user"` → `"XXuserXX"` | user_joined 缺 user，前端 TypeError 丟棄事件，成員列表不更新 | 斷言 user_joined payload user 等於 user_info |
| 3240 | 126 | `connect` | `"timestamp"` → `"XXtimestampXX"` | user_joined/user_left 缺 timestamp，前端不產生「加入/離開聊天室」系統訊息 | 斷言 user_joined/user_left payload 含 ISO timestamp |
| 3224 | 147 | `connect` | `"global_online_user_ids"` → `"XXglobal_online_user_idsXX"` | room_users 缺 global_online_user_ids，前端退回房內邏輯，在別房在線者顯示離線 | 斷言連線後 room_users 含 global_online_user_ids 且含其他房在線者 |
| 3075 | 154 | `connect` | `await self._broadcast_user_status( user_id, use…` → `pass` | 上線時不通知其他房間 user_status_changed，其他房看不到其上線 | 使用者在 A 房時連 B 房，斷言 A 房收到 is_online=True |
| 3173 | 155 | `connect` | `True` → `False` | 上線時廣播 is_online=False，其他房把剛上線者標為離線 | 斷言連線時 user_status_changed.is_online is True |
| 3181 | 224 | `force_disconnect` | `self._schedule_offline(user_id)` → `pass` | 被踢/房間刪除後未排程離線，該使用者全域永遠顯示在線 | force_disconnect 唯一房間後推進時間，斷言 global_online_users 不含該使用者 |
| 3076 | 259 | `_broadcast_user_left` | `await self.broadcast_to_room( room_id, { "type"…` → `pass` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3200 | 262 | `_broadcast_user_left` | `"type"` → `"XXtypeXX"` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3204 | 262 | `_broadcast_user_left` | `"user_left"` → `"XXuser_leftXX"` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3201 | 263 | `_broadcast_user_left` | `"user"` → `"XXuserXX"` | user_left 缺 user，前端 TypeError 丟棄事件 | 斷言 user_left payload user 等於離線者資訊 |
| 3202 | 264 | `_broadcast_user_left` | `"timestamp"` → `"XXtimestampXX"` | user_joined/user_left 缺 timestamp，前端不產生「加入/離開聊天室」系統訊息 | 斷言 user_joined/user_left payload 含 ISO timestamp |
| 3141 | 279 | `_broadcast_user_status` | `continue` → `break` | 遇到排除房間即 break，排序在後的房間收不到上下線通知 | 使用者在三房，排除房在中間，斷言另兩房都收到 user_status_changed |
| 3099 | 280 | `_broadcast_user_status` | `await self.broadcast_to_room( rid, { "type": "u…` → `pass` | user_status_changed 不送/無法辨識，跨房在線狀態不同步 | 斷言其他房收到 type=user_status_changed |
| 3230 | 283 | `_broadcast_user_status` | `"type"` → `"XXtypeXX"` | user_status_changed 不送/無法辨識，跨房在線狀態不同步 | 斷言其他房收到 type=user_status_changed |
| 3235 | 283 | `_broadcast_user_status` | `"user_status_changed"` → `"XXuser_status_changedXX"` | user_status_changed 不送/無法辨識，跨房在線狀態不同步 | 斷言其他房收到 type=user_status_changed |
| 3231 | 284 | `_broadcast_user_status` | `"user_id"` → `"XXuser_idXX"` | 缺 user_id，前端直接 return，狀態不更新 | 斷言 user_status_changed payload user_id 正確 |
| 3233 | 286 | `_broadcast_user_status` | `"is_online"` → `"XXis_onlineXX"` | 缺 is_online，前端設為 undefined→上線者被標為離線 | 斷言 is_online 為布林且與事件一致 |
| 3078 | 303 | `_execute_offline` | `await asyncio.sleep(self._disconnect_debounce_s…` → `pass` | 離線 debounce 失效：重整/切房立即廣播離線與 user_left，重連又廣播加入，畫面閃爍 | disconnect 後未滿 debounce 秒前斷言未廣播 user_left/離線 |
| 3205 | 322 | `_execute_offline` | `==` → `!=` | 離線時處理到「其他」使用者的 pending room-leave，錯誤移除他人並以本人身分廣播離開 | 兩使用者都有 pending room-leave，A 離線後斷言 B 仍在 room_users |
| 3245 | 322 | `_execute_offline` | `0` → `1` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3189 | 330 | `_execute_offline` | `left_room_ids.append(rid)` → `pass` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3079 | 334 | `_execute_offline` | `saved_user_info` → `not (saved_user_info)` | 離線時不廣播或廣播成 is_online=True，其他人永遠看到其在線 | 離線 debounce 後斷言各房收到 is_online=False 與 user_left |
| 3145 | 336 | `_execute_offline` | `await self._broadcast_user_left(rid, saved_user…` → `pass` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3106 | 337 | `_execute_offline` | `await self._broadcast_user_status(user_id, save…` → `pass` | 離線時不廣播或廣播成 is_online=True，其他人永遠看到其在線 | 離線 debounce 後斷言各房收到 is_online=False 與 user_left |
| 3209 | 337 | `_execute_offline` | `False` → `True` | 離線時不廣播或廣播成 is_online=True，其他人永遠看到其在線 | 離線 debounce 後斷言各房收到 is_online=False 與 user_left |
| 3109 | 353 | `_execute_room_leave` | `await asyncio.sleep(self._room_rejoin_debounce_…` → `pass` | 房間 rejoin debounce 失效：重整後重連即廣播 user_joined，系統訊息洗版 | 斷線後在 debounce 內（已讓出事件迴圈）重連，斷言未廣播 user_joined |

## 低價值（low）

共 458 個。

### `app/auth/dependencies.py`

- #31 L38 `"WWW-Authenticate"` → `"XXWWW-AuthenticateXX"`：401 回應的 WWW-Authenticate 標頭鍵/值，僅 RFC 相容性，不影響認證結果
- #32 L38 `"Bearer"` → `"XXBearerXX"`：401 回應的 WWW-Authenticate 標頭鍵/值，僅 RFC 相容性，不影響認證結果
- #6 L44 `or` → `and`：需持合法簽章 token 才能缺欄位；伺服器簽發的 token 必含 sub 與 user_id

### `app/config.py`

- #64 L11 `"mongodb://localhost:27017"` → `"XXmongodb://localhost:…`：MongoDB 連線預設值，部署由 .env 覆寫，測試另有設定
- #65 L12 `"chatroom"` → `"XXchatroomXX"`：MongoDB 連線預設值，部署由 .env 覆寫，測試另有設定
- #67 L17 `480` → `481`：token 有效期 ±1 單位，調參常數
- #69 L18 `7` → `8`：token 有效期 ±1 單位，調參常數
- #71 L21 `"redis://localhost:6379/0"` → `"XXredis://localhost:63…`：REDIS_URL 預設值，.env.example 已覆寫
- #72 L23 `20` → `21`：Redis 連線池上限調參
- #73 L23 `20` → `0`：max_connections=0 時 redis-py 退回 100，僅連線池大小改變
- #76 L27 `60` → `61`：生產限流門檻 ±1，調參常數
- #78 L28 `1000` → `1001`：生產限流門檻 ±1，調參常數
- #79 L28 `1000` → `0`：生產 default 桶上限 0 只影響 / 等非 API 路徑
- #80 L29 `10` → `11`：生產限流門檻 ±1，調參常數
- #83 L35 `"nvidia"` → `"XXnvidiaXX"`：未知供應商仍走 nvidia 分支，僅錯誤訊息中的供應商名不同
- #84 L38 `"https://integrate.api.nvidia.com/v1"` → `"XXhttps://integrate.ap…`：AI 供應商端點/模型名稱預設值
- #85 L39 `"nvidia/nemotron-3-super-120b-a12b"` → `"XXnvidia/nemotron-3-su…`：AI 供應商端點/模型名稱預設值
- #86 L42 `"gemini-2.5-flash"` → `"XXgemini-2.5-flashXX"`：AI 供應商端點/模型名稱預設值
- #87 L44 `5` → `6`：@bot 每分鐘上限 ±1，調參常數
- #92 L52 `"*"` → `"XX*XX"`：CORS_ORIGINS 預設變無效來源為 fail-closed，瀏覽器經 BFF 不直連後端
- #93 L55 `"uploads"` → `"XXuploadsXX"`：上傳目錄預設值
- #94 L56 `True` → `False`：縮圖開關預設值，僅效能/體驗
- #95 L58 `".env"` → `"XX.envXX"`：env_file 名稱錯：本機 .env 不載入，缺 JWT_SECRET 會啟動即報錯（大聲失敗）
- #96 L58 `True` → `False`：環境變數大小寫敏感度，正常大寫變數仍可讀取

### `app/core/bot.py`

- #98 L25 `"bot@chatroom.app"` → `"XXbot@chatroom.appXX"`：僅改種子化 bot 帳號 email；bot 以 username 查找，無功能影響
- #105 L110 `6` → `7`：多輪歷史往返組數調參（6→7），僅影響 token 用量
- #107 L111 `10` → `11`：歷史時間窗調參（10→11 分鐘）
- #109 L112 `200` → `201`：歷史回答截斷字數調參（200→201）
- #141 L150 `>=` → `>`：時間窗邊界恰好相等才有差，實務不可觀察
- #137 L166 `"\n"` → `"XX\nXX"`：僅改 LLM prompt 內歷史換行格式

### `app/core/exceptions.py`

- #157 L29 `"WWW-Authenticate"` → `"XXWWW-AuthenticateXX"`：UnauthorizedError 的 WWW-Authenticate 鍵/值，僅 RFC 相容性
- #158 L29 `"Bearer"` → `"XXBearerXX"`：UnauthorizedError 的 WWW-Authenticate 鍵/值，僅 RFC 相容性

### `app/database/indexes.py`

- #221 L27 `"room_id"` → `"XXroom_idXX"`：訊息查詢用複合索引欄位錯，僅效能
- #222 L27 `"created_at"` → `"XXcreated_atXX"`：訊息查詢用複合索引欄位錯，僅效能
- #223 L29 `"room_id"` → `"XXroom_idXX"`：訊息查詢用複合索引欄位錯，僅效能
- #224 L29 `"seq"` → `"XXseqXX"`：訊息查詢用複合索引欄位錯，僅效能
- #225 L32 `"room_id"` → `"XXroom_idXX"`：去重索引變 client_id 全域唯一，隨機 ID 下行為近同，僅效能
- #231 L48 `"members"` → `"XXmembersXX"`：房間/通知查詢索引欄位錯，僅效能
- #232 L50 `"is_public"` → `"XXis_publicXX"`：房間/通知查詢索引欄位錯，僅效能
- #233 L50 `"created_at"` → `"XXcreated_atXX"`：房間/通知查詢索引欄位錯，僅效能
- #234 L56 `"user_id"` → `"XXuser_idXX"`：房間/通知查詢索引欄位錯，僅效能
- #235 L56 `"created_at"` → `"XXcreated_atXX"`：房間/通知查詢索引欄位錯，僅效能

### `app/database/mongodb.py`

- #256 L30 `await self.client.admin.command("ping")` → `pass`：啟動時不驗證 Mongo 連線，僅失去 fail-fast
- #248 L40 `self.client` → `not (self.client)`：僅影響 shutdown 清理與連線釋放
- #252 L41 `await self.client.close()` → `pass`：僅影響 shutdown 清理與連線釋放
- #253 L42 `self.client = None` → `pass`：僅影響 shutdown 清理與連線釋放
- #254 L43 `self.database = None` → `pass`：僅影響 shutdown 清理與連線釋放
- #241 L64 `await _db_manager.disconnect()` → `pass`：僅影響 shutdown 清理與連線釋放

### `app/database/redis_conn.py`

- #271 L30 `await self.redis_client.ping()` → `pass`：啟動不 ping，僅失去 fail-fast
- #263 L38 `self.redis_client` → `not (self.redis_client)`：僅影響 shutdown 清理
- #266 L39 `await self.redis_client.aclose()` → `pass`：僅影響 shutdown 清理
- #267 L40 `self.redis_client = None` → `pass`：僅影響 shutdown 清理
- #261 L61 `await _redis_manager.disconnect()` → `pass`：僅影響 shutdown 清理

### `app/main.py`

- #306 L53 `"1.0.0"` → `"XX1.0.0XX"`：OpenAPI 版本字串
- #307 L63 `"*"` → `"XX*XX"`：僅 DEBUG CORS 來源，且瀏覽器經 BFF 不直連後端
- #330 L67 `"*"` → `"XX*XX"`：生產 CORS 來源變無效，屬 fail-closed，BFF 不受影響
- #331 L69 `","` → `"XX,XX"`：生產 CORS 來源變無效，屬 fail-closed，BFF 不受影響
- #276 L71 `app.add_middleware( CORSMiddleware, all…` → `pass`：移除 CORS 為 fail-closed，瀏覽器經 BFF 伺服器端呼叫
- #309 L74 `True` → `False`：關閉 allow_credentials 為 fail-closed
- #332 L75 `"GET"` → `"XXGETXX"`：CORS 允許方法字串錯，fail-closed
- #333 L75 `"POST"` → `"XXPOSTXX"`：CORS 允許方法字串錯，fail-closed
- #334 L75 `"PUT"` → `"XXPUTXX"`：CORS 允許方法字串錯，fail-closed
- #335 L75 `"DELETE"` → `"XXDELETEXX"`：CORS 允許方法字串錯，fail-closed
- #336 L75 `"OPTIONS"` → `"XXOPTIONSXX"`：CORS 允許方法字串錯，fail-closed
- #337 L77 `"Accept"` → `"XXAcceptXX"`：CORS 允許標頭字串錯，fail-closed
- #338 L77 `"Authorization"` → `"XXAuthorizationXX"`：CORS 允許標頭字串錯，fail-closed
- #339 L77 `"Content-Type"` → `"XXContent-TypeXX"`：CORS 允許標頭字串錯，fail-closed
- #340 L77 `"X-Requested-With"` → `"XXX-Requested-WithXX"`：CORS 允許標頭字串錯，fail-closed
- #342 L84 `","` → `"XX,XX"`：多主機字串未切分，所有請求被拒，屬 fail-closed
- #277 L92 `security_config.development_mode = sett…` → `pass`：僅影響 DEBUG 下的寬鬆 CSP（Swagger），生產值不變
- #311 L96 `and` → `or`：預設環境下 custom_headers 已含同值 STS，僅 HSTS 停用設定被忽略
- #343 L96 `not` → ``：預設環境下 custom_headers 已含同值 STS，僅 HSTS 停用設定被忽略
- #322 L142 `"version"` → `"XXversionXX"`：根端點 version 欄位，僅資訊
- #324 L142 `"1.0.0"` → `"XX1.0.0XX"`：根端點 version 欄位，僅資訊
- #327 L151 `"infrastructure"` → `"XXinfrastructureXX"`：health 回應 infrastructure 鍵名

### `app/middleware/error_handler.py`

- #357 L38 `False` → `True`：建構子預設值，main 明確傳入 debug
- #359 L71 `await self._log_error(request, exc, err…` → `pass`：僅錯誤日誌
- #404 L79 `"timestamp"` → `"XXtimestampXX"`：錯誤回應附帶資訊欄位（timestamp/path/method）鍵名
- #405 L80 `"path"` → `"XXpathXX"`：錯誤回應附帶資訊欄位（timestamp/path/method）鍵名
- #406 L81 `"method"` → `"XXmethodXX"`：錯誤回應附帶資訊欄位（timestamp/path/method）鍵名
- #376 L90 `and` → `or`：僅 traceback 日誌條件
- #394 L90 `not` → ``：僅 traceback 日誌條件
- #419 L96 `"Content-Type"` → `"XXContent-TypeXX"`：Content-Type 鍵名錯，JSONResponse 仍自帶 application/json
- #420 L96 `"application/json; charset=utf-8"` → `"XXapplication/json; ch…`：Content-Type 值錯，BFF/客戶端未依此判斷
- #422 L133 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #429 L141 `"writeErrors"` → `"XXwriteErrorsXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #430 L149 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #431 L158 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #432 L166 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #396 L174 `self.debug` → `not (self.debug)`：僅 debug 回應少 error_type；生產 details 本就不顯示
- #424 L174 `"error_type"` → `"XXerror_typeXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #378 L186 `"method"` → `"XXmethodXX"`：日誌欄位鍵名
- #379 L187 `"url"` → `"XXurlXX"`：日誌欄位鍵名
- #380 L188 `"status_code"` → `"XXstatus_codeXX"`：日誌欄位鍵名
- #381 L189 `"error_code"` → `"XXerror_codeXX"`：日誌欄位鍵名
- #382 L190 `"error_message"` → `"XXerror_messageXX"`：日誌欄位鍵名
- #383 L191 `"timestamp"` → `"XXtimestampXX"`：日誌欄位鍵名
- #384 L192 `"user_agent"` → `"XXuser_agentXX"`：日誌欄位鍵名
- #397 L192 `"user-agent"` → `"XXuser-agentXX"`：日誌欄位鍵名
- #385 L193 `"client_ip"` → `"XXclient_ipXX"`：日誌欄位鍵名

### `app/middleware/rate_limiting.py`

- #513 L60 `60` → `61`：突發視窗 60→61 秒，調參
- #484 L69 `0` → `1`：429 回應的 Remaining 標頭值
- #485 L70 `-` → `+`：Retry-After/reset 秒數計算，僅提示值
- #517 L70 `60` → `61`：Retry-After/reset 秒數計算，僅提示值
- #518 L70 `60` → `0`：Retry-After/reset 秒數計算，僅提示值
- #519 L70 `%` → `*`：Retry-After/reset 秒數計算，僅提示值
- #543 L70 `60` → `61`：Retry-After/reset 秒數計算，僅提示值
- #486 L75 `0` → `1`：429 回應的 Remaining 標頭值
- #487 L76 `-` → `+`：Retry-After/reset 秒數計算，僅提示值
- #521 L76 `%` → `*`：Retry-After/reset 秒數計算，僅提示值
- #442 L83 `await self.redis.expire(key, window_siz…` → `pass`：key 不設 TTL，閒置 key 殘留 Redis，僅資源
- #523 L83 `+` → `-`：key TTL ±1~2 秒，影響可忽略
- #545 L83 `1` → `2`：key TTL ±1~2 秒，影響可忽略
- #458 L85 `-` → `+`：X-RateLimit-Remaining 標頭值
- #488 L85 `-` → `+`：X-RateLimit-Remaining 標頭值
- #489 L85 `1` → `2`：X-RateLimit-Remaining 標頭值
- #459 L86 `-` → `+`：X-RateLimit-Reset 計算
- #490 L86 `%` → `*`：X-RateLimit-Reset 計算
- #460 L99 `or` → `and`：傳入 settings 時改建新 Settings()，值相同；僅 settings=None 時崩潰
- #524 L116 `"/api/auth/login"` → `"XX/api/auth/loginXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #547 L117 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #550 L117 `60` → `61`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #551 L117 `60` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #548 L118 `"max_requests"` → `"XXmax_requestsXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #552 L118 `100` → `101`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #553 L118 `100` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #549 L119 `"burst"` → `"XXburstXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #554 L119 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #555 L119 `50` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #525 L121 `"/api/auth/register"` → `"XX/api/auth/registerXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #556 L122 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #559 L122 `300` → `301`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #560 L122 `300` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #557 L123 `"max_requests"` → `"XXmax_requestsXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #561 L123 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #562 L123 `50` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #558 L124 `"burst"` → `"XXburstXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #563 L124 `25` → `26`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #564 L124 `25` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #526 L127 `"/api/"` → `"XX/api/XX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #565 L127 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #566 L127 `"max_requests"` → `"XXmax_requestsXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #567 L127 `"burst"` → `"XXburstXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #568 L127 `60` → `61`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #569 L127 `60` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #570 L127 `200` → `201`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #571 L127 `200` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #572 L127 `100` → `101`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #573 L127 `100` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #527 L129 `"/api/files/upload"` → `"XX/api/files/uploadXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #574 L129 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #575 L129 `"max_requests"` → `"XXmax_requestsXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #576 L129 `"burst"` → `"XXburstXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #577 L129 `300` → `301`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #578 L129 `300` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #579 L129 `100` → `101`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #580 L129 `100` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #581 L129 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #582 L129 `50` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #528 L131 `"/ws"` → `"XX/wsXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #583 L131 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #584 L131 `"max_requests"` → `"XXmax_requestsXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #585 L131 `"burst"` → `"XXburstXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #586 L131 `60` → `61`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #587 L131 `60` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #588 L131 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #589 L131 `50` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #590 L131 `20` → `21`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #591 L131 `20` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #529 L133 `"default"` → `"XXdefaultXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #592 L133 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #593 L133 `"max_requests"` → `"XXmax_requestsXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #594 L133 `"burst"` → `"XXburstXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #595 L133 `3600` → `3601`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #596 L133 `3600` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #597 L133 `5000` → `5001`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #598 L133 `5000` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #599 L133 `500` → `501`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #600 L133 `500` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #449 L204 `self.rate_limits["default"]` → `None`：default 設定取值失敗→fail-open，僅影響 / 等非 API 路徑
- #500 L204 `"default"` → `"XXdefaultXX"`：default 設定取值失敗→fail-open，僅影響 / 等非 API 路徑
- #502 L211 `"/docs"` → `"XX/docsXX"`：文件/靜態路徑被納入限流，影響小
- #503 L211 `"/redoc"` → `"XX/redocXX"`：文件/靜態路徑被納入限流，影響小
- #504 L211 `"/openapi.json"` → `"XX/openapi.jsonXX"`：文件/靜態路徑被納入限流，影響小
- #505 L211 `"/static/"` → `"XX/static/XX"`：文件/靜態路徑被納入限流，影響小
- #474 L286 `response.headers["X-RateLimit-Limit"] =…` → `pass`：回應 X-RateLimit-* 資訊標頭
- #538 L286 `"X-RateLimit-Limit"` → `"XXX-RateLimit-LimitXX"`：回應 X-RateLimit-* 資訊標頭
- #475 L287 `response.headers["X-RateLimit-Remaining…` → `pass`：回應 X-RateLimit-* 資訊標頭
- #539 L287 `"X-RateLimit-Remaining"` → `"XXX-RateLimit-Remainin…`：回應 X-RateLimit-* 資訊標頭
- #476 L288 `response.headers["X-RateLimit-Reset"] =…` → `pass`：回應 X-RateLimit-* 資訊標頭
- #540 L288 `"X-RateLimit-Reset"` → `"XXX-RateLimit-ResetXX"`：回應 X-RateLimit-* 資訊標頭
- #541 L288 `+` → `-`：回應 X-RateLimit-* 資訊標頭
- #477 L289 `response.headers["X-RateLimit-Window"] …` → `pass`：回應 X-RateLimit-* 資訊標頭
- #542 L289 `"X-RateLimit-Window"` → `"XXX-RateLimit-WindowXX"`：回應 X-RateLimit-* 資訊標頭

### `app/middleware/security_headers.py`

- #675 L31 `31536000` → `31536001`：建構子預設值，main 明確傳入 hsts_max_age
- #676 L31 `31536000` → `0`：建構子預設值，main 明確傳入 hsts_max_age
- #688 L58 `"strict-origin-when-cross-origin"` → `"XXstrict-origin-when-c…`：基礎標頭值被 custom_headers 同鍵覆寫，僅關閉自訂標頭時生效
- #689 L61 `"geolocation=(), microphone=(), camera=…` → `"XXgeolocation=(), micr…`：基礎標頭值被 custom_headers 同鍵覆寫，僅關閉自訂標頭時生效
- #690 L75 `"default-src 'self'; " "script-src 'sel…` → `"XXdefault-src 'self'; …`：基礎 CSP 被 security_config 的 CSP 覆寫，僅關閉自訂標頭時生效
- #710 L110 `"on"` → `"XXonXX"`：X-Forwarded-SSL 偵測 HTTPS，僅影響 HSTS 是否送出
- #715 L110 `"x-forwarded-ssl"` → `"XXx-forwarded-sslXX"`：X-Forwarded-SSL 偵測 HTTPS，僅影響 HSTS 是否送出
- #719 L136 `500` → `501`：錯誤日誌截斷長度
- #720 L136 `500` → `0`：錯誤日誌截斷長度
- #721 L147 `"error"` → `"XXerrorXX"`：中介層例外時的 500 回應文字
- #722 L147 `"Internal server error"` → `"XXInternal server erro…`：中介層例外時的 500 回應文字

### `app/models/enums.py`

- #729 L25 `"admin"` → `"XXadminXX"`：目前無任何程式路徑指派 ADMIN，僅影響 DB 既有值/前端列舉契約

### `app/models/message.py`

- #748 L47 `64` → `65`：client_id 長度上限放寬 1 字元，無實質影響
- #756 L128 `100` → `101`：關鍵字上限放寬 1 字元，已 re.escape，無風險
- #745 L135 `20` → `21`：預設 page_size 20→21；前端總是明確帶 page_size
- #759 L135 `1` → `2`：page_size=1 被拒，邊界值實務少用
- #760 L135 `100` → `101`：page_size 上限放寬至 101，影響可忽略

### `app/models/room.py`

- #791 L13 `100` → `101`：名稱上限放寬 1 字且建立/讀取模型一致，無實質影響
- #793 L14 `500` → `501`：描述上限放寬 1 字且建立/讀取模型一致，無實質影響
- #776 L15 `True` → `False`：is_public 預設僅影響缺欄位的舊文件；create_room 一律明確設定
- #795 L18 `100` → `101`：預設容量 100→101 屬調校常數
- #799 L18 `1000` → `1001`：max_members 上限放寬 1 且建立/讀取模型一致，無實質影響
- #804 L32 `128` → `129`：密碼僅雜湊儲存，上限放寬 1 字無實質影響
- #817 L45 `128` → `129`：密碼僅雜湊儲存，上限放寬 1 字無實質影響

### `app/models/user.py`

- #837 L13 `50` → `51`：使用者名稱上限放寬 1 字，無實質影響
- #825 L17 `True` → `False`：is_active 預設僅影響缺欄位舊文件；建立時一律明確設 True
- #847 L96 `1` → `2`：密碼至少 6 字，1 字元現行密碼本就錯誤，僅 400→422

### `app/repositories/base.py`

- #923 L83 `1000` → `1001`：毫秒截斷誤差 ≤1ms，DB 與回傳值仍一致
- #924 L83 `1000` → `0`：時間戳被截到整秒，精度下降但排序有 _id 保底
- #936 L83 `1000` → `1001`：回傳物件微秒與 DB 毫秒不一致（差 <1ms）
- #859 L84 `document["created_at"] = now` → `pass`：created_at 改用模型值，未截斷毫秒，回傳與 DB 差 <1ms
- #895 L84 `"created_at"` → `"XXcreated_atXX"`：多寫垃圾欄位，created_at 未截斷毫秒
- #860 L85 `document["updated_at"] = now` → `pass`：updated_at 改用模型值，未截斷毫秒
- #896 L85 `"updated_at"` → `"XXupdated_atXX"`：多寫垃圾欄位，updated_at 未截斷毫秒
- #926 L99 `1000` → `1001`：updated_at 誤差 ≤1ms
- #912 L103 `"updated_at"` → `"XXupdated_atXX"`：remove_member 未更新 updated_at（改寫入垃圾欄位）
- #933 L159 `"id"` → `"XXidXX"`：rooms/users 文件多存 id:null；alias 優先，讀取不受影響

### `app/repositories/message_repository.py`

- #1008 L151 `"status"` → `"XXstatusXX"`：僅多存一個無用欄位 XXstatusXX，status 仍為 SENT，讀取忽略
- #1080 L182 `1000` → `0`：edited_at 截到整秒，失去毫秒精度
- #1095 L182 `1000` → `1001`：第一運算元 //1001：edited_at 最多早 1ms，僅時間精度
- #1056 L217 `1000` → `0`：軟刪除 edited_at 截到整秒
- #1081 L217 `1000` → `1001`：第一運算元 //1001：軟刪除 edited_at 最多早 1ms
- #1085 L224 `"edited"` → `"XXeditedXX"`：軟刪除不再標 edited=True；已刪訊息自列表過濾、前端移除，幾乎不可見
- #1087 L224 `True` → `False`：軟刪除不再標 edited=True；已刪訊息自列表過濾、前端移除，幾乎不可見
- #1086 L225 `"edited_at"` → `"XXedited_atXX"`：軟刪除不寫 edited_at；已刪訊息不顯示
- #1060 L276 `"created_at"` → `"XXcreated_atXX"`：改以 _id 排序；單程序 ObjectId 與建立時間同序，僅多 worker 同秒可能錯序
- #1040 L368 `"created_at"` → `"XXcreated_atXX"`：搜尋排序退化為 _id 排序，實務與 created_at 同序
- #1041 L381 `<` → `<=`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見
- #1071 L381 `+` → `-`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見
- #1042 L382 `>` → `>=`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見
- #1072 L382 `1` → `2`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見

### `app/repositories/notification_repository.py`

- #1128 L20 `"notifications"` → `"XXnotificationsXX"`：集合名僅影響 indexes.py 索引對應（效能）與既有資料遷移，新部署功能不變
- #1140 L94 `"created_at"` → `"XXcreated_atXX"`：find_many 追加 _id 降冪 tiebreaker，ObjectId 近似建立時間，排序幾乎不變（失去索引）
- #1157 L136 `"recent"` → `"XXrecentXX"`：facet 鍵改名使 recent_activity 恆為空；前端未使用此欄位
- #1174 L137 `"created_at"` → `"XXcreated_atXX"`：recent 依不存在欄位排序，取到非最新 5 筆；前端未使用 recent_activity
- #1165 L138 `5` → `6`：recent_activity 由 5 筆變 6 筆，調校常數且前端未使用
- #1132 L166 `"recent"` → `"XXrecentXX"`：讀錯鍵使 recent_activity 恆為空；前端未使用此欄位

### `app/repositories/room_repository.py`

- #1301 L100 `"created_at"` → `"XXcreated_atXX"`：改以 _id tiebreaker 排序，與 created_at 幾乎同序
- #1303 L123 `"created_at"` → `"XXcreated_atXX"`：改以 _id tiebreaker 排序，與 created_at 幾乎同序
- #1304 L133 `"created_at"` → `"XXcreated_atXX"`：改以 _id tiebreaker 排序，與 created_at 幾乎同序
- #1201 L190 `success` → `not (success)`：僅影響 log 輸出，回傳值不變
- #1203 L215 `success` → `not (success)`：僅影響 log 輸出，回傳值不變

### `app/security_config.py`

- #1593 L34 `self.hsts_include_subdomains` → `not (self.hsts_include_…`：HSTS 缺 includeSubDomains，僅子網域範圍
- #1601 L35 `parts.append("includeSubDomains")` → `pass`：HSTS 缺 includeSubDomains，僅子網域範圍
- #1622 L35 `"includeSubDomains"` → `"XXincludeSubDomainsXX"`：HSTS 缺 includeSubDomains，僅子網域範圍
- #1594 L37 `self.hsts_preload` → `not (self.hsts_preload)`：HSTS 缺 preload，僅影響 preload 清單資格
- #1602 L38 `parts.append("preload")` → `pass`：HSTS 缺 preload，僅影響 preload 清單資格
- #1623 L38 `"preload"` → `"XXpreloadXX"`：HSTS 缺 preload，僅影響 preload 清單資格
- #1604 L69 `self.csp_report_uri` → `not (self.csp_report_ur…`：report-uri 條件反轉，僅附加無效報告位址或少報告
- #1625 L84 `"X-Content-Type-Options"` → `"XXX-Content-Type-Optio…`：標頭鍵名錯，base_headers 仍補上正確標頭，只多一個無效標頭
- #1626 L85 `"X-Frame-Options"` → `"XXX-Frame-OptionsXX"`：標頭鍵名錯，base_headers 仍補上正確標頭，只多一個無效標頭
- #1631 L85 `"DENY"` → `"XXDENYXX"`：X-Frame-Options 值無效，但 CSP frame-ancestors 'none' 仍防護
- #1627 L86 `"X-XSS-Protection"` → `"XXX-XSS-ProtectionXX"`：標頭鍵名錯，base_headers 仍補上正確標頭，只多一個無效標頭
- #1632 L86 `"1; mode=block"` → `"XX1; mode=blockXX"`：X-XSS-Protection 已被現代瀏覽器忽略
- #1628 L87 `"Referrer-Policy"` → `"XXReferrer-PolicyXX"`：標頭鍵名錯，base_headers 仍補上正確標頭，只多一個無效標頭
- #1633 L87 `"strict-origin-when-cross-origin"` → `"XXstrict-origin-when-c…`：無效 Referrer-Policy 時瀏覽器預設即同一策略
- #1634 L89 `"geolocation=(), microphone=(), camera=…` → `"XXgeolocation=(), micr…`：Permissions-Policy 對 JSON API 回應無實質作用
- #1598 L96 `self.enable_hsts` → `not (self.enable_hsts)`：生產時 middleware base 仍送同值 STS，僅 HSTS 停用設定被忽略
- #1608 L97 `headers["Strict-Transport-Security"] = …` → `pass`：生產時 middleware base 仍送同值 STS，僅 HSTS 停用設定被忽略
- #1635 L97 `"Strict-Transport-Security"` → `"XXStrict-Transport-Sec…`：生產時 middleware base 仍送同值 STS，僅 HSTS 停用設定被忽略
- #1651 L115 `"SECURITY_ENABLE_HSTS"` → `"XXSECURITY_ENABLE_HSTS…`：環境變數名錯，該設定旋鈕失效但預設值不變
- #1649 L116 `"SECURITY_HSTS_MAX_AGE"` → `"XXSECURITY_HSTS_MAX_AG…`：環境變數名錯，該設定旋鈕失效但預設值不變
- #1615 L117 `==` → `!=`：HSTS 缺 includeSubDomains，僅子網域範圍
- #1653 L118 `"SECURITY_HSTS_INCLUDE_SUBDOMAINS"` → `"XXSECURITY_HSTS_INCLUD…`：環境變數名錯，該設定旋鈕失效但預設值不變
- #1654 L118 `"true"` → `"XXtrueXX"`：HSTS 缺 includeSubDomains，僅子網域範圍
- #1639 L120 `"true"` → `"XXtrueXX"`：HSTS 缺 includeSubDomains，僅子網域範圍
- #1616 L121 `==` → `!=`：HSTS 缺 preload，僅影響 preload 清單資格
- #1640 L121 `"true"` → `"XXtrueXX"`：HSTS 缺 preload，僅影響 preload 清單資格
- #1655 L121 `"SECURITY_HSTS_PRELOAD"` → `"XXSECURITY_HSTS_PRELOA…`：環境變數名錯，該設定旋鈕失效但預設值不變
- #1656 L121 `"true"` → `"XXtrueXX"`：HSTS 缺 preload，僅影響 preload 清單資格
- #1657 L122 `"SECURITY_ENABLE_CSP"` → `"XXSECURITY_ENABLE_CSPX…`：環境變數名錯，該設定旋鈕失效但預設值不變
- #1659 L123 `"SECURITY_CSP_REPORT_ONLY"` → `"XXSECURITY_CSP_REPORT_…`：環境變數名錯，該設定旋鈕失效但預設值不變
- #1642 L124 `"true"` → `"XXtrueXX"`：比較字串錯使 report-only 永遠開不了，預設不受影響
- #1643 L125 `"SECURITY_CSP_REPORT_URI"` → `"XXSECURITY_CSP_REPORT_…`：環境變數名錯，該設定旋鈕失效但預設值不變
- #1661 L126 `"SECURITY_ENABLE_HEADERS"` → `"XXSECURITY_ENABLE_HEAD…`：環境變數名錯，該設定旋鈕失效但預設值不變

### `app/services/ai_service.py`

- #1667 L26 `0.6` → `1.6`：AI temperature 調參
- #1668 L27 `2048` → `2049`：max_tokens 2048→2049 調參
- #1670 L28 `60.0` → `61.0`：外部呼叫逾時 60→61 秒調參
- #1697 L64 `0` → `1`：thinking_budget 0→1 調參（Gemini 專用）

### `app/services/message_service.py`

- #1801 L275 `>` → `>=`：gap 恰為 200 時改走 full reload（最新 50 條+清空），一致性仍成立
- #1844 L277 `50` → `51`：全量重載筆數 50→51 調參
- #1849 L386 `"timestamp"` → `"XXtimestampXX"`：WS 事件 timestamp 欄位改名，前端未使用
- #1852 L425 `"room_id"` → `"XXroom_idXX"`：message_deleted 的 room_id 改名；前端只用 message_id
- #1854 L427 `"timestamp"` → `"XXtimestampXX"`：WS 事件 timestamp 欄位改名，前端未使用

### `app/services/room_service.py`

- #1995 L51 `owner` → `not (owner)`：僅缺 owner_name 的舊房間走補填 fallback
- #2078 L52 `room_data["owner_name"] = owner.username` → `pass`：僅缺 owner_name 的舊房間走補填 fallback
- #2135 L52 `"owner_name"` → `"XXowner_nameXX"`：僅缺 owner_name 的舊房間走補填 fallback
- #2154 L97 `True` → `False`：send_event 已內部吞例外，僅改變記錄方式
- #2085 L99 `isinstance(result, Exception)` → `not (isinstance(result,…`：僅影響錯誤 log 輸出
- #2116 L192 `"creator_id"` → `"XXcreator_idXX"`：creator_id 欄位前端目前未使用
- #2102 L487 `<` → `<=`：僅在到期時間恰等於 now 時結果不同
- #2163 L544 `"room_id"` → `"XXroom_idXX"`：前端 user_left handler 未使用 room_id
- #2069 L573 `[]` → `None`：不存在房間經 HTTP 已被 require_room_membership 擋下；WS 路徑被 try 吞掉

### `app/services/user_service.py`

- #2178 L268 `await self.user_repo.update_last_login(…` → `pass`：last_login_at 只寫入，不對外暴露也無讀取
- #2216 L296 `or` → `and`：需合法簽章 refresh token 才會缺欄位；簽發者必含兩欄

### `app/utils/file_upload.py`

- #2363 L34 `"application/msword"` → `"XXapplication/mswordXX"`：.doc 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2364 L35 `"application/vnd.openxmlformats-officed…` → `"XXapplication/vnd.open…`：.docx 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2365 L36 `"text/plain"` → `"XXtext/plainXX"`：.txt 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2366 L37 `"text/markdown"` → `"XXtext/markdownXX"`：.md 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2388 L55 `"audio/mpeg"` → `"XXaudio/mpegXX"`：.mp3 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2389 L56 `"audio/wav"` → `"XXaudio/wavXX"`：.wav 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2390 L57 `"audio/ogg"` → `"XXaudio/oggXX"`：.ogg 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2391 L58 `"audio/mp4"` → `"XXaudio/mp4XX"`：.m4a 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2392 L59 `"audio/flac"` → `"XXaudio/flacXX"`：.flac 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2277 L75 `_MIME_TO_TYPE[_mime] = _file_type` → `pass`：移除 MIME 回退只會更嚴格；回退本身讓未知副檔名跳過 magic 檢查，不宜以測試固化
- #2445 L90 `0` → `1`：僅 GIF87a 舊格式被誤拒，GIF89a 仍通過，實務罕見
- #2467 L102 `0` → `1`：僅無 ID3 標籤的 MPEG-2 Layer III（\xff\xf3）MP3 被誤拒，實務罕見
- #2468 L102 `0` → `1`：僅無 ID3 標籤且帶 CRC 的 MPEG-2 Layer III（\xff\xf2）MP3 被誤拒，罕見
- #2298 L134 `self.upload_dir.mkdir(exist_ok=True)` → `pass`：僅全新環境 uploads 不存在時，匯入時子目錄 mkdir 失敗致啟動崩潰，部署即發現
- #2399 L183 `>` → `>=`：僅大小恰等於上限的檔案被拒，影響極小
- #2333 L188 `>` → `>=`：僅恰 255 字元檔名被拒；實際儲存使用系統產生檔名
- #2401 L188 `255` → `256`：允許 256 字元檔名；儲存檔名由系統產生，無實際影響
- #2403 L192 `"<"` → `"XX<XX"`：「<」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2404 L192 `">"` → `"XX>XX"`：「>」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2405 L192 `":"` → `"XX:XX"`：「:」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2406 L192 `'"'` → `"XX\"XX"`：「"」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2407 L192 `"\|"` → `"XX\|XX"`：「|」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2408 L192 `"?"` → `"XX?XX"`：「?」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2409 L192 `"*"` → `"XX*XX"`：「*」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2416 L216 `"%Y%m%d_%H%M%S"` → `"XX%Y%m%d_%H%M%SXX"`：僅檔名時間戳格式改變，仍唯一且安全
- #2477 L217 `8` → `9`：唯一碼多含一個「-」，僅外觀改變
- #2507 L233 `4096` → `0`：read(0) 使 hash 恆為空內容雜湊；hash 欄位無任何消費者（未去重/驗證）
- #2417 L234 `sha256_hash.update(chunk)` → `pass`：hash 恆為空內容雜湊；hash 欄位無任何消費者
- #2304 L235 `sha256_hash.hexdigest()` → `None`：hash 回 None；hash 欄位無任何消費者
- #2338 L275 `file_dir.mkdir(parents=True, exist_ok=T…` → `pass`：__init__ 已預建所有子目錄，僅執行期目錄被刪除時才有差異（防禦性）
- #2501 L275 `True` → `False`：僅 uploads 根目錄於執行期被刪除時才失敗（防禦性）
- #2480 L287 `"id"` → `"XXidXX"`：file id 為未持久化的隨機 uuid，前端未讀取
- #2482 L289 `"original_name"` → `"XXoriginal_nameXX"`：original_name 前端未讀取（BFF 自行補 originalName）
- #2484 L291 `"content_type"` → `"XXcontent_typeXX"`：content_type 欄位前端未讀取
- #2485 L292 `"size"` → `"XXsizeXX"`：BFF 以瀏覽器 file.size 覆寫 size，後端欄位未被使用
- #2486 L293 `"hash"` → `"XXhashXX"`：hash 欄位無任何消費者
- #2488 L295 `"relative_path"` → `"XXrelative_pathXX"`：relative_path 欄位無任何消費者
- #2490 L297 `"created_at"` → `"XXcreated_atXX"`：created_at 前端未讀取（BFF 另補 uploadedAt）

### `app/utils/image_processor.py`

- #2521 L13 `150` → `151`：縮圖尺寸 +1 像素，純調校常數
- #2523 L13 `150` → `151`：縮圖尺寸 +1 像素，純調校常數
- #2525 L13 `300` → `301`：縮圖尺寸 +1 像素，純調校常數
- #2527 L13 `300` → `301`：縮圖尺寸 +1 像素，純調校常數
- #2529 L13 `600` → `601`：縮圖尺寸 +1 像素，純調校常數
- #2531 L13 `600` → `601`：縮圖尺寸 +1 像素，純調校常數
- #2510 L18 `50_000_000` → `50000001`：像素上限 +1，邊界調校
- #2516 L24 `>` → `>=`：僅恰好 5 千萬像素的圖片被拒，邊界影響極小
- #2518 L41 `self.output_dir.mkdir(exist_ok=True)` → `pass`：僅全新環境 processed 不存在時啟動崩潰，部署即發現
- #2519 L45 `self.thumbnail_dir.mkdir(exist_ok=True)` → `pass`：僅全新環境 thumbnails 目錄不存在時縮圖靜默失敗（回 None），前端未用縮圖

### `app/utils/ws_ticket.py`

- #2685 L16 `30` → `31`：ticket TTL ±1 秒，調參

### `app/websocket/handlers.py`

- #2758 L59 `task.add_done_callback(_on_ai_task_done)` → `pass`：完成的背景 AI task 不移出強引用集合，僅記憶體累積與異常未記錄
- #2760 L65 `_background_ai_tasks.discard(task)` → `pass`：完成的背景 AI task 不移出強引用集合，僅記憶體累積與異常未記錄
- #2771 L66 `and` → `or`：僅影響背景任務異常是否記錄 log
- #2806 L66 `not` → ``：僅影響背景任務異常是否記錄 log
- #2807 L66 `is not` → `is`：僅影響背景任務異常是否記錄 log
- #2814 L85 `"status"` → `"XXstatusXX"`：payload status 欄位前端未使用
- #2816 L87 `"client_id"` → `"XXclient_idXX"`：ack 已先以 server id 確認樂觀訊息，廣播去重靠 id，client_id 僅備援
- #2864 L91 `"id"` → `"XXidXX"`：payload.user.id/username 前端未使用（改用 top-level 欄位）
- #2865 L92 `"username"` → `"XXusernameXX"`：payload.user.id/username 前端未使用（改用 top-level 欄位）
- #2773 L99 `payload["reply_to"] = msg.reply_to` → `pass`：前端只用 reply_to_message.username/content，reply_to 與預覽 id 未使用
- #2867 L99 `"reply_to"` → `"XXreply_toXX"`：前端只用 reply_to_message.username/content，reply_to 與預覽 id 未使用
- #2869 L101 `"id"` → `"XXidXX"`：前端只用 reply_to_message.username/content，reply_to 與預覽 id 未使用
- #2965 L140 `"type"` → `"XXtypeXX"`：welcome 事件前端為 no-op
- #2969 L140 `"welcome"` → `"XXwelcomeXX"`：welcome 事件前端為 no-op
- #2966 L141 `"message"` → `"XXmessageXX"`：welcome 事件前端為 no-op
- #2967 L142 `"timestamp"` → `"XXtimestampXX"`：welcome 事件前端為 no-op
- #2968 L143 `"room_id"` → `"XXroom_idXX"`：welcome 事件前端為 no-op
- #2875 L200 `await websocket.close(code=4000, reason…` → `pass`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3047 L200 `4000` → `4001`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3048 L200 `4000` → `0`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3049 L200 `"Internal server error"` → `"XXInternal server erro…`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3051 L235 `"mark_read"` → `"XXmark_readXX"`：mark_read 為舊別名，前端只送 notification_read
- #3073 L245 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2834 L265 `""` → `"XXXX"`：僅缺 content 鍵的畸形客戶端會送出固定字串，前端總是帶 content
- #3022 L282 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2974 L297 `"system"` → `"XXsystemXX"`：使用者送 system 改存 TEXT；前端從不送 system（反而較安全）
- #2977 L320 `"message_id"` → `"XXmessage_idXX"`：ack 缺 message_id 僅暫時使樂觀訊息 id 為空，隨後廣播以 client_id 取代修正
- #2979 L322 `"room_id"` → `"XXroom_idXX"`：ack 的 room_id 前端未使用
- #2980 L323 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2885 L360 `>` → `>=`：通知預覽截斷長度/省略號的外觀差異
- #2923 L360 `50` → `51`：通知預覽截斷長度/省略號的外觀差異
- #2924 L360 `50` → `0`：通知預覽截斷長度/省略號的外觀差異
- #2982 L361 `"..."` → `"XX...XX"`：通知預覽截斷長度/省略號的外觀差異
- #3052 L361 `50` → `51`：通知預覽截斷長度/省略號的外觀差異
- #3053 L361 `50` → `0`：通知預覽截斷長度/省略號的外觀差異
- #2886 L363 `0` → `1`：sent_count 只用於 log
- #2984 L376 `+=` → `-=`：sent_count 只用於 log
- #3027 L376 `1` → `2`：sent_count 只用於 log
- #3030 L411 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2985 L428 `60` → `61`：AI 限流視窗 60→61 秒調參
- #2932 L445 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2936 L457 `"message"` → `"XXmessageXX"`：bot_error 的 message 前端不使用
- #2937 L458 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2764 L464 `50` → `51`：@bot 歷史撈取筆數 50→51 調參
- #2987 L473 `0` → `1`：略過最新一則（即當前未配對提問），歷史視窗只位移一則
- #2892 L530 `"username"` → `"XXusernameXX"`：bot 串流預覽暫時缺名稱，落地正式訊息後即被取代
- #2893 L530 `"avatar"` → `"XXavatarXX"`：avatar 本為 None，缺鍵與 null 前端呈現相同
- #3058 L545 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2767 L594 `30` → `31`：/summary 撈取筆數 30→31 調參
- #2988 L626 `0` → `1`：摘要逐字稿略過最新一則（通常為 /summary 本身）
- #2856 L677 `False` → `True`：前端總是帶 is_typing，預設值未被使用
- #2945 L686 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2946 L687 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用（以 ctx.roomId 為準）
- #2950 L709 `"global_online_user_ids"` → `"XXglobal_online_user_i…`：get_users 指令前端從未送出，僅影響非前端客戶端
- #2951 L710 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2952 L711 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用（以 ctx.roomId 為準）
- #2901 L735 `"notification"` → `"XXnotificationXX"`：前端只送 read_type='room' 且不帶 notification_id，此分支差異前端觸發不到
- #2857 L742 `False` → `True`：前端只送 read_type='room' 且不帶 notification_id，此分支差異前端觸發不到
- #2858 L744 `and` → `or`：前端只送 read_type='room' 且不帶 notification_id，此分支差異前端觸發不到
- #2993 L768 `>=` → `>`：房間已讀 0 筆時 success=False 不廣播，但本無通知需同步
- #3034 L768 `0` → `1`：房間已讀 0 筆時 success=False 不廣播，但本無通知需同步
- #2995 L779 `>` → `>=`：read_type='all' 前端從不經 WS 送出
- #3036 L779 `0` → `1`：read_type='all' 前端從不經 WS 送出
- #2908 L786 `"data"` → `"XXdataXX"`：read_status_response 在前端為 no-op
- #2958 L787 `"read_type"` → `"XXread_typeXX"`：read_status_response 在前端為 no-op
- #2959 L788 `"notification_id"` → `"XXnotification_idXX"`：read_status_response 在前端為 no-op
- #2960 L789 `"target_room_id"` → `"XXtarget_room_idXX"`：read_status_response 在前端為 no-op
- #2961 L790 `"timestamp"` → `"XXtimestampXX"`：read_status_response 在前端為 no-op
- #2999 L804 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2803 L874 `50` → `51`：歷史筆數 50→51 調參
- #3012 L904 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #3013 L905 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用（以 ctx.roomId 為準）
- #3045 L919 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用

### `app/websocket/manager.py`

- #3086 L38 `3.0` → `4.0`：離線/重入房 debounce 秒數調參
- #3087 L45 `5.0` → `6.0`：離線/重入房 debounce 秒數調參
- #3120 L73 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3090 L74 `pending_task.cancel()` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3123 L81 `pending_room_task.cancel()` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3241 L127 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用
- #3199 L138 `True` → `False`：前端以 global_online_user_ids 覆寫 is_active，此欄位無效果
- #3221 L138 `"is_active"` → `"XXis_activeXX"`：前端以 global_online_user_ids 覆寫 is_active，此欄位無效果
- #3225 L148 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 前端未使用
- #3226 L149 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用
- #3227 L150 `"online_only"` → `"XXonline_onlyXX"`：online_only 旗標前端未使用
- #3229 L150 `True` → `False`：online_only 旗標前端未使用
- #3133 L193 `and` → `or`：and→or 只在不一致狀態下觸發 KeyError 或多排一次無害 room-leave
- #3182 L229 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3203 L265 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用
- #3232 L285 `"user"` → `"XXuserXX"`：user_status_changed 的 user 物件前端未使用
- #3234 L287 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 前端未使用
- #3142 L295 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3077 L299 `self._pending_offline[user_id] = task` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3105 L318 `self._pending_offline.pop(user_id, None)` → `pass`：已完成 task 殘留在 _pending_offline，僅記憶體保留，後續邏輯檢查 done() 無害
- #3206 L324 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3186 L325 `task.cancel()` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3146 L343 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3210 L358 `in` → `not in`：僅在 cancel 競態才走到的分支，一般流程結果相同
- #3110 L375 `self._pending_room_leave.pop(room_key, …` → `pass`：已完成 room-leave task 殘留，離線時可能對舊房多送一次 user_left
- #3111 L391 `and` → `or`：使用者不在連線表時由靜默略過變 KeyError，皆在上層 catch-all 內
- #3165 L544 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 前端未使用

## 等價變異體（equivalent）

共 110 個。

### `app/auth/dependencies.py`

- #26 L73 `0` → `1`：user dict 來自 UserInDB.model_dump，必含 token_version，預設值用不到
- #28 L95 `True` → `False`：user dict 來自 UserInDB.model_dump，必含 is_active，預設值用不到

### `app/config.py`

- #90 L48 `"http://localhost:5173"` → `"XXhttp://localhost:517…`：FRONTEND_URL 在 app 內沒有任何讀取點

### `app/database/mongodb.py`

- #247 L23 `"chatroom"` → `"XXchatroomXX"`：所有呼叫端皆明確傳入 database_name，預設值不會被使用
- #245 L57 `"chatroom"` → `"XXchatroomXX"`：所有呼叫端皆明確傳入 database_name，預設值不會被使用

### `app/database/redis_conn.py`

- #274 L26 `True` → `False`：改回 bytes：json.loads 接受 bytes、計數為 int，所有使用點結果相同

### `app/main.py`

- #308 L66 `"*"` → `"XX*XX"`：'*'.split(',') 即 ['*']，兩分支結果完全相同
- #341 L84 `"*"` → `"XX*XX"`：'*' 時 split 得 ['*']，TrustedHost 全放行，與不掛等效
- #303 L103 `"http"` → `"XXhttpXX"`：FastAPI.middleware 忽略 middleware_type 參數

### `app/middleware/rate_limiting.py`

- #479 L53 `0` → `1`：分數為 Unix 時間戳，清除範圍下限 0 或 1 結果相同
- #482 L65 `0` → `1`：burst_size 為假時 burst_requests 不會被讀取（短路）
- #493 L174 `""` → `"XXXX"`：無 Authorization 時預設字串都不以 'Bearer ' 開頭，結果相同
- #497 L180 `"unknown"` → `"XXunknownXX"`：僅 request.client 為空時的桶名字串，分桶行為一致
- #469 L221 `and` → `or`：limiter 與 redis_client 總是同時被設定，and/or 判斷結果相同

### `app/middleware/security_headers.py`

- #705 L124 `"Server"` → `"XXServerXX"`：app 內沒有任何層預先設定 Server 標頭，覆寫與否結果相同

### `app/models/message.py`

- #751 L64 `"_id"` → `"XX_idXX"`：populate_by_name 且 _normalize_id 已補 id 鍵，alias 改名後 id 照常填入
- #754 L103 `True` → `False`：FastAPI 回應驗證本就傳 from_attributes=True，模型設定無影響
- #762 L146 `True` → `False`：巢狀欄位直接傳同類實例，pydantic 不需 from_attributes；無屬性驗證路徑

### `app/models/notification.py`

- #772 L58 `"_id"` → `"XX_idXX"`：_normalize_id 同時補 id 鍵且 populate_by_name=True，alias 從未用於序列化
- #774 L62 `True` → `False`：文件必含 _id 鍵，靠 alias 即可填入 id；程式中無以欄位名 id 建構
- #775 L81 `True` → `False`：NotificationResponse 僅以 **dict 或同類實例建構，from_attributes 不生效

### `app/models/room.py`

- #777 L24 `isinstance(v, str)` → `not (isinstance(v, str))`：StrEnum 本身即 str，兩分支最終皆被驗證為同一枚舉值
- #819 L51 `"_id"` → `"XX_idXX"`：_normalize_id 恆補 id 鍵且 populate_by_name，alias 從未被使用
- #821 L62 `True` → `False`：改 populate_by_name 會使現有測試失敗，故此為 arbitrary_types_allowed，無作用
- #779 L71 `0` → `1`：member_count 一律由 _prepare_room_data 覆寫，預設值不會被用到
- #780 L72 `False` → `True`：has_password 一律由 _prepare_room_data 覆寫
- #781 L73 `False` → `True`：is_member 一律由 _convert_to_summary/_response 明確設定
- #822 L77 `True` → `False`：回應模型無任何 alias 欄位，populate_by_name 無作用
- #823 L77 `True` → `False`：FastAPI 驗證回應時自帶 from_attributes=True，程式無其他 ORM 驗證

### `app/models/user.py`

- #845 L56 `True` → `False`：UserResponse 無 alias 欄位，populate_by_name 無作用
- #846 L56 `True` → `False`：FastAPI 驗證時強制 from_attributes=True，程式無其他物件驗證
- #828 L75 `"bearer"` → `"XXbearerXX"`：AuthResponse 所有建構點皆明確傳入 token_type
- #829 L90 `"bearer"` → `"XXbearerXX"`：RefreshResponse 由 service dict 建構，必含 token_type

### `app/repositories/base.py`

- #906 L28 `"id"` → `"XXidXX"`：寫入時皆 exclude id，文件從不帶 id 欄位，是否覆寫結果相同
- #850 L30 `document` → `None`：所有呼叫端皆忽略回傳值（就地修改 dict）
- #874 L58 `100` → `101`：所有 find_many 呼叫端皆明確傳入 limit
- #875 L58 `100` → `0`：所有 find_many 呼叫端皆明確傳入 limit
- #907 L64 `"_id"` → `"XX_idXX"`：無呼叫端以 _id 排序，恆追加 tiebreaker 與原行為相同
- #861 L91 `str(result.inserted_id)` → `None`：所有呼叫端皆忽略 insert_one 回傳值
- #938 L99 `1000` → `1001`：k*1001 微秒經 BSON 取毫秒後值不變，且更新後皆重新讀取
- #900 L110 `and` → `or`：無呼叫端使用 upsert，upserted_id 恆為 None

### `app/repositories/message_repository.py`

- #950 L151 `message_dict["status"] = MessageStatus.…` → `pass`：model_dump 已含預設 status=SENT，唯一呼叫端不傳其他狀態，覆寫值相同
- #1079 L182 `1000` → `1001`：第二運算元 1000→1001：微秒 ms*1001 經 MongoDB 毫秒截斷後與原值相同
- #1055 L217 `1000` → `1001`：第二運算元 1000→1001：寫入 MongoDB 毫秒截斷後值相同
- #987 L240 `20` → `21`：repo 預設 limit 從未使用：所有呼叫端（service 兩處）皆明確傳 limit

### `app/repositories/notification_repository.py`

- #1122 L71 `20` → `21`：唯一呼叫端 NotificationService 一律明確傳 limit，預設值永不使用
- #1180 L142 `1` → `2`：MongoDB $project 非零整數一律視為包含，2 與 1 語意相同
- #1181 L143 `1` → `2`：MongoDB $project 非零整數一律視為包含，2 與 1 語意相同
- #1182 L144 `1` → `2`：MongoDB $project 非零整數一律視為包含，2 與 1 語意相同
- #1158 L153 `1` → `2`：$facet 恆輸出單一文件，to_list 長度 1 或 2 結果相同

### `app/repositories/room_repository.py`

- #1229 L98 `20` → `21`：Service 一律明確傳入 skip/limit，預設值不被使用
- #1232 L105 `20` → `21`：Service 一律明確傳入 limit
- #1235 L113 `20` → `21`：Service 一律明確傳入 limit
- #1238 L128 `20` → `21`：Service 一律明確傳入 limit
- #1241 L141 `20` → `21`：Service 一律明確傳入 limit
- #1243 L142 `True` → `False`：Service 一律以位置參數明確傳入 public_only
- #1300 L211 `""` → `"XXXX"`：$unset 忽略欄位值內容

### `app/repositories/user_repository.py`

- #1329 L73 `False` → `True`：所有呼叫端都明確傳入 bump_token_version，預設值不被使用
- #1356 L111 `1` → `2`：版本只做相等比較且不對外暴露，+2 與 +1 行為相同

### `app/security_config.py`

- #1582 L12 `True` → `False`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1583 L13 `31536000` → `31536001`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1584 L13 `31536000` → `0`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1585 L14 `True` → `False`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1586 L15 `True` → `False`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1587 L18 `True` → `False`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1588 L19 `False` → `True`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1589 L23 `True` → `False`：load_security_config 明確傳入所有欄位，類別預設值不被使用
- #1590 L24 `True` → `False`：hide_server_header 全專案沒有讀取點
- #1591 L25 `"FastAPI"` → `"XXFastAPIXX"`：custom_server_header 全專案沒有讀取點
- #1592 L28 `False` → `True`：development_mode 在 main.py 被 settings.DEBUG 覆寫
- #1597 L82 `headers.update( { "X-Content-Type-Optio…` → `pass`：middleware base_headers 提供相同的五個標頭與值
- #1660 L123 `"false"` → `"XXfalseXX"`：預設 'XXfalseXX' 仍不等於 'true'，結果同為 False
- #1620 L128 `==` → `!=`：hide_server_header 全專案沒有讀取點
- #1645 L128 `"true"` → `"XXtrueXX"`：hide_server_header 全專案沒有讀取點
- #1663 L128 `"SECURITY_HIDE_SERVER"` → `"XXSECURITY_HIDE_SERVER…`：hide_server_header 全專案沒有讀取點
- #1664 L128 `"true"` → `"XXtrueXX"`：hide_server_header 全專案沒有讀取點
- #1646 L129 `"SECURITY_SERVER_HEADER"` → `"XXSECURITY_SERVER_HEAD…`：custom_server_header 全專案沒有讀取點
- #1647 L129 `"FastAPI"` → `"XXFastAPIXX"`：custom_server_header 全專案沒有讀取點
- #1621 L130 `==` → `!=`：development_mode 在 main.py 被 settings.DEBUG 覆寫
- #1665 L130 `"SECURITY_DEVELOPMENT_MODE"` → `"XXSECURITY_DEVELOPMENT…`：development_mode 在 main.py 被 settings.DEBUG 覆寫
- #1666 L130 `"false"` → `"XXfalseXX"`：development_mode 在 main.py 被 settings.DEBUG 覆寫
- #1648 L131 `"true"` → `"XXtrueXX"`：development_mode 在 main.py 被 settings.DEBUG 覆寫

### `app/services/message_service.py`

- #1796 L237 `0` → `1`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1797 L238 `20` → `21`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1798 L238 `20` → `0`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1837 L301 `"_id"` → `"XX_idXX"`：model_dump() 只產生 id 鍵，'_id' 與 'XX_idXX' 皆不在 dict，分支永不執行

### `app/services/room_service.py`

- #1963 L45 `room_data["id"] = room.id if room.id el…` → `pass`：model_dump 已含 id，且 room.id 實務上恆非空
- #2073 L45 `"id"` → `"XXidXX"`：多出的鍵被 Pydantic 忽略，id 仍來自 model_dump
- #2110 L45 `"_id"` → `"XX_idXX"`：僅 room.id 為空時才求值，實務不可達
- #2111 L45 `""` → `"XXXX"`：僅 room.id 為空時才求值，實務不可達
- #1964 L46 `room_data.pop("_id", None)` → `pass`：model_dump 不含 _id 鍵，pop 本為 no-op
- #2074 L46 `"_id"` → `"XX_idXX"`：model_dump 不含 _id 鍵，pop 本為 no-op
- #2066 L557 `50` → `51`：所有呼叫端皆明確傳入 limit
- #2067 L557 `50` → `0`：所有呼叫端皆明確傳入 limit

### `app/services/user_service.py`

- #2222 L42 `"_id"` → `"XX_idXX"`：model_dump 預設不用 alias，鍵為 id 而非 _id，此分支原本就是死碼

### `app/utils/file_upload.py`

- #2398 L72 `True` → `False`：四類副檔名與 MIME 清單長度一致，strict 僅在長度不符時才有作用
- #2267 L109 `16` → `17`：最深簽章僅到 offset 12，讀 16 或 17 bytes 比對結果相同
- #2326 L138 `(self.upload_dir / file_type).mkdir(exi…` → `pass`：save_file 以 mkdir(parents=True) 再建目錄，預建子目錄冗餘、無可觀察差異
- #2412 L197 `"file_type"` → `"XXfile_typeXX"`：validation_info 的 file_type 鍵從未被讀取（save_file 用回傳的 file_type）
- #2415 L200 `"size"` → `"XXsizeXX"`：validation_info 的 size 鍵從未被讀取
- #2506 L233 `4096` → `4097`：SHA-256 結果與讀取 chunk 大小無關

### `app/utils/user_cache.py`

- #2667 L13 `"user_cache"` → `"XXuser_cacheXX"`：前綴只經 _cache_key 一致使用，別處無硬編碼
- #2680 L55 `False` → `True`：ensure_ascii 只影響跳脫，json.loads 還原結果相同

### `app/utils/ws_ticket.py`

- #2684 L15 `"ws_ticket:"` → `"XXws_ticket:XX"`：建立與驗證使用同一前綴常數，無外部依賴

### `app/websocket/handlers.py`

- #2759 L60 `task` → `None`：_spawn_ai_task 回傳值無任何呼叫端使用
- #2918 L266 `"text"` → `"XXtextXX"`：預設值只在缺鍵時用；'xxtextxx' 與 'text' 皆落入 else→TEXT
- #3025 L349 `10000` → `10001`：max_members 上限 1000，切片 [:10000] 與 [:10001] 結果相同

### `app/websocket/manager.py`

- #3171 L138 `user_data["is_active"] = True` → `pass`：user_info 由 _get_user_info 建立已含 is_active=True，copy 後重設相同值
- #3103 L316 `self.active_connections.pop(user_id, No…` → `pass`：此時 active_connections 不會有空 dict（各處皆刪鍵），pop 為 no-op
- #3185 L324 `and` → `or`：task 必非 None；對已完成 task 呼叫 cancel() 為 no-op，行為相同

## 從未被任何測試執行的函數

共 96 個函數、623 個變異體：這些函數在整個測試套件中一行都沒有被執行過，任何改動都不會被發現。括號內為該函數的變異體數。

- `app/auth/dependencies.py`：`require_room_membership`（8）
- `app/core/bot.py`：`ensure_bot_user`（7）、`get_bot_user_id`（1）
- `app/core/fastapi_integration.py`：`create_ai_service`（1）、`create_file_service`（1）、`create_room_repository`（1）
- `app/main.py`：`lifespan`（6）
- `app/repositories/base.py`：`delete`（2）、`delete_many`（1）、`update_many`（15）
- `app/repositories/message_repository.py`：`count_after_seq`（6）、`delete_by_room_id`（2）、`get_after_seq`（11）、`get_by_client_id`（4）、`get_reply_previews`（8）、`next_room_seq`（8）
- `app/repositories/room_repository.py`：`get_by_invite_code`（3）、`update_member_role`（5）
- `app/repositories/user_repository.py`：`get_by_ids`（10）
- `app/routers/ai.py`：`get_ai_status`（2）
- `app/routers/auth.py`：`change_password`（5）
- `app/routers/files.py`：`download_file`（6）、`get_thumbnail`（4）、`upload_image_only`（3）、`upload_single_file`（2）
- `app/routers/invitations.py`：`validate_invitation`（4）
- `app/routers/messages.py`：`create_message`（3）、`delete_message`（5）、`get_message`（2）、`get_room_messages`（10）、`search_room_messages`（2）、`update_message`（3）
- `app/routers/notifications.py`：`clear_all_notifications`（5）、`delete_notification`（5）、`get_notification_stats`（3）、`get_notifications`（10）、`get_unread_notifications`（9）、`mark_all_notifications_read`（5）、`mark_notification_read`（5）
- `app/routers/rooms.py`：`create_room`（3）、`delete_room`（5）、`get_my_rooms`（10）、`get_room`（4）、`get_room_members`（9）、`get_room_messages`（10）、`get_rooms`（14）、`join_room`（4）、`leave_room`（4）、`send_room_message`（4）、`update_room`（3）
- `app/routers/ws_ticket.py`：`create_websocket_ticket`（3）
- `app/services/ai_service.py`：`is_available`（2）
- `app/services/file_service.py`：`_attach_uploader`（6）、`_save_file`（5）、`_try_generate_thumbnails`（2）、`_try_get_image_info`（2）、`_validate_filename`（3）、`_validate_path_within`（3）、`resolve_download`（12）、`resolve_thumbnail`（9）、`upload_file`（11）、`upload_image`（12）
- `app/services/notification_service.py`：`_broadcast_stats_update`（9）、`clear_user_notifications`（2）、`create_notification`（1）、`delete_notification`（5）、`get_notification_stats`（1）、`get_user_notifications`（4）、`mark_all_as_read`（9）、`mark_as_read`（5）、`mark_room_notifications_as_read`（12）、`send_real_time_notification`（38）
- `app/services/room_service.py`：`get_room_for_user`（7）、`get_user_rooms`（4）
- `app/services/user_service.py`：`change_password`（8）
- `app/utils/file_upload.py`：`get_file_upload_manager`（1）、`get_mime_type`（2）、`upload_file`（6）
- `app/utils/image_processor.py`：`create_multiple_thumbnails`（7）、`create_thumbnail`（10）、`get_image_info`（47）、`get_image_processor`（1）、`open_image`（6）、`resize_image`（17）
- `app/utils/ws_ticket.py`：`create_ws_ticket`（6）、`validate_ws_ticket`（5）
- `app/websocket/auth.py`：`_get_user_info`（23）、`authenticate_websocket`（9）、`authenticate_websocket_by_ticket`（2）、`extract_token_from_query`（7）、`websocket_auth_middleware`（8）
- `app/websocket/handlers.py`：`send_gap_messages`（9）
- `app/websocket/manager.py`：`broadcast_message`（8）、`get_global_online_user_ids`（1）、`handle_ping`（4）
- `app/websocket/routes.py`：`websocket_endpoint`（6）
