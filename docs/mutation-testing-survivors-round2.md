# 變異測試附錄（第二輪，修正後）：存活變異體與未覆蓋函數明細

本文件為 [變異測試報告](mutation-testing-report.md) 第〇節的附錄，列出修正與補測後重跑時仍存活的變異體與從未被執行的函數。
第一輪（修正前）的明細見 [mutation-testing-survivors.md](mutation-testing-survivors.md)，第三輪見 [mutation-testing-survivors-round3.md](mutation-testing-survivors-round3.md)。編號為本輪 `gen` 產生的編號，與第一輪不同。

分類沿用第一輪的定義：程式碼未變的存活者延用第一輪的判讀；本輪才出現的存活者（多為原本從未執行、這次才被執行到的程式碼）為人工判讀。

## 目錄

- [高風險](#高風險high)
- [中風險](#中風險medium)
- [低價值](#低價值low)
- [等價變異體](#等價變異體equivalent)
- [從未被任何測試執行的函數](#從未被任何測試執行的函數)

## 高風險（high）

共 18 個。

### `app/config.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 89 | 47 | `<class Settings>` | `False` → `True` | 安全預設翻轉：未設 DEBUG 時生產即 DEBUG（CORS*、寬鬆限流、錯誤細節外洩） | 移除 DEBUG 環境變數並以 _env_file=None 建 Settings，斷言 DEBUG is False |

### `app/database/redis_conn.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 276 | 20 | `connect` | `is` → `is not` | Redis 永不連線且不報錯：限流 fail-open 全停用、WS ticket 全 500 | init_redis 後斷言 get_redis() 可 ping；Redis 缺席時測試應失敗非 skip |
| 271 | 56 | `init_redis` | `await _redis_manager.connect()` → `pass` | init_redis 不連線：限流靜默停用、WS ticket 500、bot 限流失效 | init_redis 後斷言 get_redis().ping() 為 True |

### `app/services/message_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1826 | 299 | `sync_messages_since` | `0` → `1` | 大 gap 全量重載 skip=1：清空後少了最新一則，客戶端靜默漏訊息 | gap>200 時斷言回傳訊息包含最新 seq 且 full_reload=True |
| 1828 | 299 | `sync_messages_since` | `50` → `0` | 全量重載 limit=0 拋錯→退回無 full_reload 的歷史，中間數百則靜默漏掉 | gap>200 時斷言回傳 50 筆且 full_reload=True |

### `app/websocket/handlers.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2790 | 86 | `_format_message_payload` | `"seq"` → `"XXseqXX"` | 即時訊息缺 seq：客戶端無法追蹤最大序號，重連 gap 補發基準錯誤，空房情境會漏訊息 | 斷言 chat 廣播與 ack 的 seq 等於 create_message 回傳 seq |
| 2848 | 150 | `handle_websocket_connection` | `"last_seq"` → `"XXlast_seqXX"` | 重連 last_seq 參數永遠讀不到，只送最近 50 則，斷線期間超過 50 則即漏 | 帶 last_seq=5 連線，斷言走 send_gap_messages 而非歷史 |
| 2798 | 151 | `handle_websocket_connection` | `and` → `or` | 無 last_seq（首次連線/空房）時 None.isdigit() 例外→連線被關閉，空房無法即時聊天 | query 無 last_seq 與 last_seq=abc 時斷言送出 message_history 且連線不關閉 |
| 2799 | 152 | `handle_websocket_connection` | `await send_gap_messages(user_id, room_id, int(l…` → `pass` | 重連帶 last_seq 時不補發 gap，斷線期間訊息永久遺失於即時視圖 | 帶 last_seq 連線，斷言收到 message_sync 含 seq>last_seq 訊息 |
| 2852 | 227 | `handle_message` | `"message"` → `"XXmessageXX"` | 前端送 type:'message'，別名失效後所有 WS 聊天訊息被當未知類型，無法發送 | handle_message 以 type='message' 斷言呼叫 handle_chat_message |
| 2856 | 268 | `handle_chat_message` | `"client_id"` → `"XXclient_idXX"` | 讀不到 client_id：冪等去重失效、ack 無 client_id 致前端重試→重複訊息 | WS 帶 client_id，斷言 MessageCreate 與 ack 的 client_id 相同 |
| 2757 | 314 | `handle_chat_message` | `await connection_manager.send_personal_message(…` → `pass` | ack 未送/無法辨識/缺 client_id：前端 10 秒後標記失敗並重試，每則訊息顯示發送失敗 | 斷言發送成功後送出 type=ack，含正確 client_id/message_id/seq |
| 2950 | 318 | `handle_chat_message` | `"type"` → `"XXtypeXX"` | ack 未送/無法辨識/缺 client_id：前端 10 秒後標記失敗並重試，每則訊息顯示發送失敗 | 斷言發送成功後送出 type=ack，含正確 client_id/message_id/seq |
| 2956 | 318 | `handle_chat_message` | `"ack"` → `"XXackXX"` | ack 未送/無法辨識/缺 client_id：前端 10 秒後標記失敗並重試，每則訊息顯示發送失敗 | 斷言發送成功後送出 type=ack，含正確 client_id/message_id/seq |
| 2951 | 319 | `handle_chat_message` | `"client_id"` → `"XXclient_idXX"` | 讀不到 client_id：冪等去重失效、ack 無 client_id 致前端重試→重複訊息 | WS 帶 client_id，斷言 MessageCreate 與 ack 的 client_id 相同 |
| 2864 | 398 | `handle_chat_message` | `is_summary_command(content)` → `not (is_summary_command(conte…` | 非 @bot 的每則文字訊息都觸發 AI 摘要（成本暴增、bot 洗版），/summary 反而無效 | 一般訊息斷言未 spawn 摘要；'/summary' 斷言 spawn handle_summary_command |
| 2961 | 428 | `_check_bot_rate_limit` | `60` → `0` | window_size=0：清空所有紀錄且 now%0 例外 fail-open，@bot 限流完全失效 | 以真實（fake）Redis 連續呼叫超過上限，斷言 _check_bot_rate_limit 回 False |

### `app/websocket/manager.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 3187 | 365 | `_execute_room_leave` | `not` → `` | 使用者切走房間後若房內仍有人，整個 room_users 被刪，其餘在線成員收不到任何廣播 | A、B 同房，A 斷線 debounce 後斷言 B 仍收得到 broadcast_to_room 訊息 |

## 中風險（medium）

共 190 個。

### `app/config.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 77 | 27 | `<class Settings>` | `60` → `0` | 生產 /api/ 每分鐘上限變 0（.env 未覆寫），所有一般 API 請求皆 429 | Settings(DEBUG=False) 建 middleware，斷言 /api/ 上限為 60 |
| 81 | 29 | `<class Settings>` | `10` → `0` | burst=0 使生產 /api/ 突發限制停用，有效上限由每分 10 次放寬為 60 次 | 以生產設定斷言 /api/ burst=10，且同分鐘第 11 次請求回 429 |
| 88 | 44 | `<class Settings>` | `5` → `0` | @bot 上限預設 0（.env 未覆寫），每次 @bot/summary 皆被限流 | 預設設定下 _check_bot_rate_limit 第 1 次允許、第 6 次拒絕 |

### `app/core/bot.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 130 | 117 | `_as_utc` | `dt.tzinfo` → `not (dt.tzinfo)` | DB 的 naive 時間與 aware 比較拋 TypeError，fail-open 使 @bot 多輪記憶恆空 | 以 naive datetime 呼叫 build_bot_history，斷言仍配出歷史 |
| 140 | 147 | `build_bot_history` | `continue` → `break` | 遇到第一則非文字訊息即中斷，之後（較新）的 @bot 往返全部遺失 | 圖片訊息夾在兩組 @bot 往返中間，斷言兩組都進入歷史 |

### `app/core/exceptions.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 159 | 16 | `__init__` | `super().__init__(message)` → `pass` | Exception.args 為空，WS handler 以 str(e) 回傳的錯誤訊息變空字串 | WS 送空白/超長訊息，斷言 error payload 的 message 為具體中文訊息 |

### `app/core/fastapi_integration.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 178 | 113 | `get_health_check_info` | `await db.command("ping")` → `pass` | 不 ping Mongo：DB 斷線時健康檢查仍報 connected | get_database 回傳 command 會拋錯的 db，斷言 mongodb=disconnected |
| 200 | 113 | `get_health_check_info` | `"ping"` → `"XXpingXX"` | ping 指令名錯，健康檢查永遠 unhealthy，探針誤判重啟 | test_healthy 斷言 db.command 以 'ping' 被 await |
| 180 | 123 | `get_health_check_info` | `await client.ping()` → `pass` | 不 ping Redis：Redis 斷線時健康檢查仍報 connected | get_redis 回傳 ping 會拋錯的 client，斷言 redis=disconnected |

### `app/database/redis_conn.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 281 | 22 | `connect` | `self.redis_client = redis.from_url( settings.RE…` → `pass` | client 未賦值，ping None 拋錯，生產啟動直接失敗（測試吞掉） | init_redis 後斷言 _redis_manager.redis_client 非 None 且可 ping |
| 284 | 25 | `connect` | `"utf-8"` → `"XXutf-8XX"` | 非法編碼使首個 Redis 指令失敗，生產啟動崩潰（conftest 吞掉） | init_redis 後斷言 _redis_manager.redis_client 非 None 且可 ping |

### `app/main.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 286 | 61 | `<module>` | `settings.DEBUG` → `not (settings.DEBUG)` | 生產忽略 CORS_ORIGINS，改為 * 並允許 credentials | DEBUG=False 且指定 CORS_ORIGINS 重建 app，惡意 Origin 不得回 ACAO |
| 312 | 66 | `<module>` | `==` → `!=` | 生產忽略 CORS_ORIGINS，改為 * 並允許 credentials | DEBUG=False 且指定 CORS_ORIGINS 重建 app，惡意 Origin 不得回 ACAO |
| 306 | 81 | `<module>` | `not` → `` | 生產環境（DEBUG=False）才註冊 TrustedHost，測試固定 DEBUG=True | 以 DEBUG=False 重新載入 app.main，斷言 TrustedHostMiddleware 已註冊 |
| 321 | 84 | `<module>` | `!=` → `==` | 生產未掛 TrustedHostMiddleware，ALLOWED_HOSTS 設定失效 | DEBUG=False、ALLOWED_HOSTS=api.x 重建 app，偽造 Host 應回 400 |
| 307 | 86 | `<module>` | `allowed_hosts` → `not (allowed_hosts)` | 生產未掛 TrustedHostMiddleware，ALLOWED_HOSTS 設定失效 | DEBUG=False、ALLOWED_HOSTS=api.x 重建 app，偽造 Host 應回 400 |
| 313 | 87 | `<module>` | `app.add_middleware(TrustedHostMiddleware, allow…` → `pass` | 生產未掛 TrustedHostMiddleware，ALLOWED_HOSTS 設定失效 | DEBUG=False、ALLOWED_HOSTS=api.x 重建 app，偽造 Host 應回 400 |
| 290 | 112 | `<module>` | `app.add_middleware(GlobalErrorHandler, debug=se…` → `pass` | 移除全域錯誤處理：DuplicateKey 變 500、Redis 錯誤不回 503、格式改變 | 經 app 觸發 DuplicateKeyError，斷言 409 與 DUPLICATE_KEY_ERROR |
| 295 | 131 | `<module>` | `app.include_router(notifications.router, prefix…` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 296 | 132 | `<module>` | `app.include_router(files.router, prefix="/api")` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |
| 299 | 137 | `<module>` | `app.include_router(websocket_routes.router)` → `pass` | 整個 router 未註冊，該功能 API 全 404（僅 /api/auth 有 HTTP 測試） | 路由冒煙測試：斷言 app.routes 含 /api/rooms、/api/ws-ticket、/ws 等路徑 |

### `app/middleware/error_handler.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 385 | 86 | `handle_error` | `and` → `or` | 非 debug 模式也回傳錯誤細節 / 例外訊息，生產環境資訊外洩 | debug=False 時 500 / DuplicateKeyError 回應不含 details |
| 387 | 90 | `handle_error` | `and` → `or` | 非 debug 模式也回傳錯誤細節 / 例外訊息，生產環境資訊外洩 | debug=False 時 500 / DuplicateKeyError 回應不含 details |

### `app/middleware/rate_limiting.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 525 | 60 | `is_allowed` | `60` → `0` | burst 視窗 60 秒改 0 秒，burst 限制只計同一秒 | 跨秒連發後仍被 burst 擋下（凍結 time.time） |

### `app/models/message.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 766 | 71 | `<class MessageInDB>` | `False` → `True` | edited 預設變 True：所有新訊息存成已編輯，前端每則顯示「（已編輯）」 | 建立訊息後斷言回應與 DB 的 edited is False |

### `app/models/notification.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 781 | 88 | `serialize_datetime` | `format_datetime_for_json(dt)` → `None` | 通知 created_at/updated_at/read_at 在 API 回應與 WS 推播中全變 null | model_dump 後 created_at 應為 ISO 字串而非 None |

### `app/repositories/base.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 907 | 64 | `find_many` | `not in` → `in` | 不再追加 _id tiebreaker，同時間戳資料分頁順序不穩定 | 插入同 created_at 多筆，斷言依 _id 降冪且分頁不重疊 |
| 893 | 103 | `update_one` | `update["$set"] = {"updated_at": now}` → `pass` | remove_member 不再更新 updated_at；非成員離開由 200 變 400 | remove_member 後 updated_at 變大；非成員 leave 行為明確斷言 |

### `app/repositories/message_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1087 | 50 | `next_room_seq` | `"counters"` → `"XXcountersXX"` | seq 計數器文件位置改變，上線後既有房間序號從 1 重來並與舊訊息重號 | next_room_seq 後 counters 中存在 _id=room_seq:{room_id} 且 seq 相符 |
| 1056 | 51 | `next_room_seq` | `"_id"` → `"XX_idXX"` | seq 計數器文件位置改變，上線後既有房間序號從 1 重來並與舊訊息重號 | next_room_seq 後 counters 中存在 _id=room_seq:{room_id} 且 seq 相符 |
| 960 | 95 | `get_with_reply` | `message.reply_to` → `not (message.reply_to)` | 有 reply_to 時不取預覽：GET 單則訊息與 @bot 回覆廣播缺引用區塊 | test_get_with_reply 斷言 reply_to_message.content/username 正確 |
| 982 | 97 | `get_with_reply` | `reply_msg` → `not (reply_msg)` | 被回覆訊息存在時預覽為 None；不存在時 None.id 拋 AttributeError | 斷言有效 reply 帶預覽、被回覆訊息不存在時回傳 None 預覽不拋錯 |
| 993 | 188 | `update` | `is not` → `is` | 只改 content 時把 metadata 設成 null（API 可清掉檔案資訊），給 metadata 反被忽略 | 編輯帶 metadata 的訊息只改 content，斷言 metadata 保留 |
| 1027 | 343 | `search_messages` | `"status"` → `"XXstatusXX"` | 搜尋結果包含已軟刪除訊息（佔位內容） | 刪除一則後搜尋其內容/佔位字，結果不應含該則 |
| 1014 | 355 | `search_messages` | `or` → `and` | 只帶 start_date 或 end_date 時日期篩選整個被忽略 | 只帶 start_date 搜尋，斷言較早訊息被排除 |
| 1086 | 396 | `delete_by_room_id` | `"room_id"` → `"XXroom_idXX"` | 刪除房間時不再刪除該房訊息，留下孤兒資料 | 刪除房間後 messages collection 中該房訊息數為 0 |

### `app/repositories/notification_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1127 | 46 | `update` | `is not` → `is` | 單筆標記已讀時 read_at 不寫入，通知仍顯示未有閱讀時間 | mark_as_read 後 get_by_id 斷言 status=read 且 read_at 不為 None |
| 1129 | 48 | `update` | `is not` → `is` | 單筆標記已讀時 read_at 不寫入，通知仍顯示未有閱讀時間 | mark_as_read 後 get_by_id 斷言 status=read 且 read_at 不為 None |
| 1197 | 132 | `get_stats` | `1` → `2` | 通知未讀數與類型統計加倍 | test_get_stats 改為精確相等斷言 |
| 1199 | 134 | `get_stats` | `1` → `2` | 通知未讀數與類型統計加倍 | test_get_stats 改為精確相等斷言 |
| 1192 | 141 | `get_stats` | `0` → `1` | recent 內含 ObjectId _id，GET /notifications/stats 序列化失敗回 500 | API 測試：有通知時 GET /notifications/stats 回 200，recent 項目不含 _id |

### `app/repositories/room_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1315 | 108 | `get_user_rooms` | `"updated_at"` → `"XXupdated_atXX"` | 「我的房間」不再依最近更新時間排序 | 較舊房間更新後應排在 get_user_rooms 第一筆 |
| 1318 | 160 | `search_rooms` | `"name"` → `"XXnameXX"` | 搜尋結果不再依名稱字母序排列 | search_rooms 斷言結果依 name 升冪 |

### `app/routers/invitations.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1446 | 29 | `validate_invitation` | `"valid"` → `"XXvalidXX"` | BFF 以 result.valid 判斷邀請碼是否有效，改壞後邀請流程失效（第二輪結束後已補斷言，逐一驗證已殺死） | 邀請碼驗證回應的 valid 為 True |
| 1447 | 29 | `validate_invitation` | `True` → `False` | BFF 以 result.valid 判斷邀請碼是否有效，改壞後邀請流程失效（第二輪結束後已補斷言，逐一驗證已殺死） | 邀請碼驗證回應的 valid 為 True |

### `app/security_config.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1624 | 58 | `get_csp_header` | `"default-src 'self'; " "script-src 'self'; " "s…` → `"XXdefault-src 'self'; script…` | 生產 CSP 字串毀損，default-src 指令失效 | 斷言生產 get_csp_header() 以 "default-src 'self';" 開頭 |

### `app/services/ai_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1645 | 27 | `<module>` | `2048` → `0` | max_tokens=0：供應商拒絕或空回覆，@bot 與 /summary 全數失敗 | 斷言兩供應商模型 settings 的 max_tokens 等於常數且 >0 |
| 1672 | 64 | `_build_gemini_model` | `"thinking_budget"` → `"XXthinking_budgetXX"` | Gemini thinking_budget 失效：思考 token 吃掉額度截斷回覆或 SDK 拒收 | 斷言 Gemini 模型 google_thinking_config 為 thinking_budget=0 |
| 1671 | 159 | `stream_reply` | `True` → `False` | stream_text(delta=False) 回傳累積全文，handler 再累加→預覽與落地回覆重複亂碼 | 以多 chunk 串流 FunctionModel 斷言 yield 的片段串接等於完整回覆 |

### `app/services/message_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1759 | 64 | `validate_message_content` | `>` → `>=` | 長度檢查 >→>=：恰好 2000 字元訊息被拒，與 Pydantic max_length=2000 不一致 | validate_message_content 2000 字元通過、2001 字元拋 AppError |
| 1750 | 314 | `_format_with_avatars` | `unique_user_ids` → `not (unique_user_ids)` | 有訊息時不查使用者，歷史/同步訊息頭像全為 None | test_get_room_messages 斷言 avatar 等於使用者頭像 |
| 1784 | 326 | `_format_with_avatars` | `msg_dict["avatar"] = avatar_map.get(msg.user_id)` → `pass` | 歷史/gap 補發訊息頭像遺失（avatar 一律 None） | 使用者有 avatar 時，get_room_messages 與 sync 回傳 avatar 正確 |
| 1821 | 326 | `_format_with_avatars` | `"avatar"` → `"XXavatarXX"` | 歷史/gap 補發訊息頭像遺失（avatar 一律 None） | 使用者有 avatar 時，get_room_messages 與 sync 回傳 avatar 正確 |
| 1786 | 341 | `_attach_reply_previews` | `reply_ids` → `not (reply_ids)` | 訊息列表 reply_to_message 引用預覽遺失 | 列表中回覆訊息斷言 reply_to_message.content 為被回覆內容 |
| 1825 | 346 | `_attach_reply_previews` | `r.reply_to` → `not (r.reply_to)` | 訊息列表 reply_to_message 引用預覽遺失 | 列表中回覆訊息斷言 reply_to_message.content 為被回覆內容 |
| 1791 | 379 | `update_message` | `is not` → `is` | 編輯跳過 strip/空白檢查；只改 metadata/status 時 None.strip 造成 500 | PUT 內容 '   ' 應 400；只帶 metadata 應 200 |
| 1792 | 380 | `update_message` | `update_data.content = self.validate_message_con…` → `pass` | 編輯路徑不驗證內容：純空白可通過、前後空白未去除，與 HTTP/WS 發送規則不一致 | update_message 內容為空白應拋 AppError，且儲存值已 strip |

### `app/services/notification_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1896 | 63 | `_create_notification_business_logic` | `or` → `and` | or→and：有 metadata 時被換成 {}，訊息通知遺失 message_id/room_name 等跳轉資訊 | 發送訊息通知後 DB metadata 應含 message_id、room_id |

### `app/services/room_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2068 | 60 | `_convert_to_summary` | `False` → `True` | WS room_created/updated 對所有人帶 is_member=True，前端誤判已加入 | _convert_to_summary 無 user_id 時 is_member is False |
| 1987 | 122 | `_notify_room_change` | `updated_room` → `not (updated_room)` | 房間存在時不廣播 room_updated，列表人數不即時更新 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2126 | 124 | `_notify_room_change` | `"type"` → `"XXtypeXX"` | room_updated 事件缺 type，被前端 guard 丟棄 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2127 | 124 | `_notify_room_change` | `"room"` → `"XXroomXX"` | room_updated 事件缺 room 欄位，前端判為無效資料 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2128 | 124 | `_notify_room_change` | `"room_updated"` → `"XXroom_updatedXX"` | 事件 type 變成未知值，被前端丟棄 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2074 | 125 | `_notify_room_change` | `await self._broadcast_room_event(message)` → `pass` | room_updated 完全不廣播 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2076 | 164 | `create_room` | `or` → `and` | 公開邀請制房未給邀請碼時不產生→無人能加入 | 公開 INVITE 房未給 code 時應自動產生 invite_code |
| 2099 | 164 | `create_room` | `==` → `!=` | 公開房選擇邀請制時不產生邀請碼，結果無人能加入 | 建立公開邀請制房間時回應含 invite_code |
| 2101 | 204 | `create_room` | `"type"` → `"XXtypeXX"` | room_created 事件缺 type，被前端丟棄 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 2104 | 204 | `create_room` | `"room_created"` → `"XXroom_createdXX"` | room_created 事件 type 變未知值，被前端丟棄 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 2102 | 205 | `create_room` | `"room"` → `"XXroomXX"` | room_created 事件缺 room，前端無法加入列表 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 1994 | 208 | `create_room` | `await self._broadcast_room_event(message, exclu…` → `pass` | 新房間不即時廣播給其他線上使用者 | create_room 斷言他人收到 type=room_created 且含 room 摘要 |
| 1966 | 339 | `update_room` | `await self._notify_room_change(room_id)` → `pass` | update_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 1970 | 475 | `join_room` | `await self._notify_room_change(room_id)` → `pass` | join_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2093 | 545 | `leave_room` | `not` → `` | user_left 的 user 錯置：線上者丟 username、離線者缺 id | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2138 | 546 | `leave_room` | `"id"` → `"XXidXX"` | 離線者離開時 user 缺 id，前端無法自成員列表移除 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2050 | 547 | `leave_room` | `await self._connection_manager.broadcast_to_roo…` → `pass` | 其他成員收不到 user_left，成員列表殘留 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2146 | 550 | `leave_room` | `"type"` → `"XXtypeXX"` | user_left 缺 type，被前端丟棄 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2151 | 550 | `leave_room` | `"user_left"` → `"XXuser_leftXX"` | user_left type 變未知值，被前端丟棄 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2147 | 551 | `leave_room` | `"user"` → `"XXuserXX"` | user_left 缺 user，前端 handler 取 user.id 失敗 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2148 | 552 | `leave_room` | `"timestamp"` → `"XXtimestampXX"` | 缺 timestamp→前端不顯示「離開了聊天室」系統訊息 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2150 | 554 | `leave_room` | `"removed"` → `"XXremovedXX"` | 缺 removed→離開者僅標為離線而非自成員列表移除 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 2152 | 554 | `leave_room` | `True` → `False` | removed=False→離開者僅標為離線而非自成員列表移除 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 1975 | 561 | `leave_room` | `await self._notify_room_change(room_id)` → `pass` | leave_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2052 | 566 | `get_room_members` | `0` → `1` | WS 通知走預設 skip→members[0]（房主）收不到訊息通知 | get_room_members(room_id) 預設應含第一位成員 |

### `app/utils/file_upload.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2323 | 21 | `<module>` | `"image/jpeg"` → `"XXimage/jpegXX"` | .jpg 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2324 | 22 | `<module>` | `"image/jpeg"` → `"XXimage/jpegXX"` | .jpg 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2325 | 23 | `<module>` | `"image/png"` → `"XXimage/pngXX"` | .png 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2327 | 25 | `<module>` | `"image/webp"` → `"XXimage/webpXX"` | .webp 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2330 | 28 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2401 | 28 | `<module>` | `10` → `11` | 圖片上限由 10MB 放寬為 11MB | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2403 | 28 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2337 | 33 | `<module>` | `"application/pdf"` → `"XXapplication/pdfXX"` | .pdf 下載 Content-Type 變成錯誤字串，瀏覽器內嵌顯示失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2289 | 39 | `<module>` | `"max_size"` → `"XXmax_sizeXX"` | 文件 max_size 鍵不存在：非空文件上傳 KeyError 回 500 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2290 | 39 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2342 | 39 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2343 | 39 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2344 | 39 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2405 | 39 | `<module>` | `50` → `51` | 文件上限由 50MB 放寬為 51MB | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2406 | 39 | `<module>` | `50` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2407 | 39 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2408 | 39 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2350 | 44 | `<module>` | `"video/mp4"` → `"XXvideo/mp4XX"` | .mp4 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2352 | 46 | `<module>` | `"video/x-msvideo"` → `"XXvideo/x-msvideoXX"` | .avi 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2353 | 47 | `<module>` | `"video/x-matroska"` → `"XXvideo/x-matroskaXX"` | .mkv 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2354 | 48 | `<module>` | `"video/webm"` → `"XXvideo/webmXX"` | .webm 下載 Content-Type 變成錯誤字串，瀏覽器影片播放失敗（MIME 回退變嚴格無害） | 參數化斷言 get_mime_type(ext) 與 resolve_download 回傳正確 MIME |
| 2293 | 50 | `<module>` | `"max_size"` → `"XXmax_sizeXX"` | 文件 max_size 鍵不存在：非空文件上傳 KeyError 回 500 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2294 | 50 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2355 | 50 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2356 | 50 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2357 | 50 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2409 | 50 | `<module>` | `100` → `101` | 影片上限由 100MB 放寬為 101MB | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2410 | 50 | `<module>` | `100` → `0` | 影片上限變 0，所有非空影片被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2411 | 50 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2412 | 50 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2297 | 61 | `<module>` | `"max_size"` → `"XXmax_sizeXX"` | 文件 max_size 鍵不存在：非空文件上傳 KeyError 回 500 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2298 | 61 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2368 | 61 | `<module>` | `*` → `/` | *→/ 使文件上限變 50 位元組，幾乎所有文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2369 | 61 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2370 | 61 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2414 | 61 | `<module>` | `20` → `0` | 音檔上限變 0，所有非空音檔被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2415 | 61 | `<module>` | `1024` → `1025` | 圖片上限 10MB 放寬約 10KB，超過規格的檔案被接受 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2416 | 61 | `<module>` | `1024` → `0` | 文件上限變 0，所有非空文件被拒 | 邊界測試：各類型 size=上限 通過、上限+1 拒絕（UploadFile 帶 size） |
| 2253 | 73 | `<module>` | `_EXT_TO_MIME[_ext] = _mime` → `pass` | 副檔名→MIME 表清空：所有下載 Content-Type 變 octet-stream，圖片/PDF 無法內嵌 | 斷言 get_mime_type 對 .png/.pdf 回 image/png、application/pdf |
| 2301 | 130 | `__init__` | `"uploads"` → `"XXuploadsXX"` | 上傳寫入 XXuploadsXX，但下載依 settings.UPLOAD_DIR=uploads，所有檔案下載 404 | 上傳後以 resolve_download 取回同檔；manager 目錄應等於 settings.UPLOAD_DIR |
| 2385 | 193 | `validate_file` | `"\\"` → `"XX\\XX"` | 反斜線（路徑分隔字元）不再被拒；儲存用產生檔名未實際穿越，但縱深防禦失效 | 參數化：含 / \ < > : 等字元的檔名 validate_file 應拋 FileUploadError |
| 2386 | 193 | `validate_file` | `"/"` → `"XX/XX"` | 「/」不再被拒，../ 形式檔名被接受；儲存用產生檔名未實際穿越，縱深防禦失效 | 參數化：含 / \ < > : 等字元的檔名 validate_file 應拋 FileUploadError |
| 2462 | 295 | `save_file` | `"path"` → `"XXpathXX"` | 缺 path 鍵：產生縮圖時 KeyError，所有圖片上傳回 500（檔案已落地成孤兒） | FileService 用真 FileUploadManager 上傳 PNG 應成功並含 thumbnails |

### `app/utils/image_processor.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2489 | 13 | `<module>` | `"medium"` → `"XXmediumXX"` | medium 鍵消失：create_thumbnail 預設值 KeyError 未被捕捉，所有圖片上傳回 500 | 對真實圖片呼叫 create_multiple_thumbnails，三種尺寸皆產生 |
| 2490 | 13 | `<module>` | `"large"` → `"XXlargeXX"` | large 鍵改名：縮圖 API size=large 回 400，large 縮圖改用 300px | 上傳圖片後 resolve_thumbnail(size=large) 成功且縮圖寬高≤600 |
| 2497 | 13 | `<module>` | `150` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2499 | 13 | `<module>` | `150` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2501 | 13 | `<module>` | `300` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2503 | 13 | `<module>` | `300` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2505 | 13 | `<module>` | `600` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2507 | 13 | `<module>` | `600` → `0` | 縮圖尺寸含 0：Pillow ZeroDivisionError 未被 fail-open 捕捉，所有圖片上傳回 500 | 真實圖片跑 create_multiple_thumbnails，斷言各尺寸縮圖存在且尺寸正確 |
| 2509 | 39 | `__init__` | `"processed"` → `"XXprocessedXX"` | 輸出目錄改名，但 resolve_thumbnail 寫死 processed/thumbnails，縮圖恆 404 | 產生縮圖後 resolve_thumbnail 能找到同檔（兩處路徑應同源） |
| 2520 | 44 | `__init__` | `"thumbnails"` → `"XXthumbnailsXX"` | 縮圖子目錄改名，與 resolve_thumbnail 寫死路徑不一致，縮圖 API 恆 404 | 產生縮圖後 resolve_thumbnail 能找到同檔（兩處路徑應同源） |

### `app/websocket/handlers.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2784 | 78 | `_format_message_payload` | `"room_id"` → `"XXroom_idXX"` | 即時訊息缺 room_id：bot 預覽無法收掉、getMaxSeq 忽略即時訊息使重連 last_seq 過舊 | 斷言 _format_message_payload 輸出含 room_id 等完整前端 Message 欄位 |
| 2785 | 79 | `_format_message_payload` | `"user_id"` → `"XXuser_idXX"` | 即時訊息缺 user_id：自己訊息判斷、分組與 bot 預覽替換失效 | 斷言廣播 payload user_id 等於發送者 |
| 2786 | 82 | `_format_message_payload` | `"username"` → `"XXusernameXX"` | 即時訊息 payload 缺 username，其他人看到的訊息沒有名字 | 對 _format_message_payload 做完整 payload 斷言 |
| 2787 | 83 | `_format_message_payload` | `"content"` → `"XXcontentXX"` | 即時訊息缺 content，所有人即時看到空白訊息 | 斷言廣播 payload content 等於已 strip 內容 |
| 2788 | 84 | `_format_message_payload` | `"message_type"` → `"XXmessage_typeXX"` | 即時訊息缺 message_type，圖片/檔案無法渲染 | image 訊息廣播 payload message_type=='image' |
| 2792 | 88 | `_format_message_payload` | `"created_at"` → `"XXcreated_atXX"` | 即時訊息缺 created_at：前端排序 NaN、時間顯示 Invalid Date | 斷言廣播 payload created_at 存在且可解析 |
| 2793 | 89 | `_format_message_payload` | `"metadata"` → `"XXmetadataXX"` | 即時訊息缺 metadata：檔案名稱/大小/類型不顯示 | file 訊息廣播 payload metadata 等於送出 metadata |
| 2794 | 90 | `_format_message_payload` | `"user"` → `"XXuserXX"` | 即時訊息缺 user 物件：前端頭像 fallback 失敗 | 斷言 payload['user'] 含 id/username/avatar |
| 2840 | 92 | `_format_message_payload` | `"username"` → `"XXusernameXX"` | 即時訊息 payload 缺 username，其他人看到的訊息沒有名字 | 對 _format_message_payload 做完整 payload 斷言 |
| 2841 | 93 | `_format_message_payload` | `"avatar"` → `"XXavatarXX"` | payload.user.avatar 缺失且無 top-level avatar，即時訊息頭像消失 | 斷言 payload['user']['avatar'] 等於傳入 avatar |
| 2892 | 266 | `handle_chat_message` | `"message_type"` → `"XXmessage_typeXX"` | 讀不到 message_type，WS 送出的圖片/檔案一律存成 TEXT | WS 送 message_type='image'，斷言 create_message 收到 IMAGE |
| 2810 | 270 | `handle_chat_message` | `"metadata"` → `"XXmetadataXX"` | 讀不到 metadata：檔案/圖片訊息的檔名、大小、MIME 永久遺失 | WS 帶 metadata 送 file 訊息，斷言持久化 metadata 相同 |
| 2858 | 293 | `handle_chat_message` | `"image"` → `"XXimageXX"` | image/file 類型比對失效，圖片或檔案訊息存成 TEXT | 參數化 image/file，斷言 msg_type 對應 IMAGE/FILE |
| 2894 | 295 | `handle_chat_message` | `"file"` → `"XXfileXX"` | image/file 類型比對失效，圖片或檔案訊息存成 TEXT | 參數化 image/file，斷言 msg_type 對應 IMAGE/FILE |
| 2953 | 321 | `handle_chat_message` | `"seq"` → `"XXseqXX"` | ack 缺 seq：自己訊息永遠沒有 seq，重連 last_seq 基準偏舊 | 斷言 ack.seq 等於 created_message.seq |
| 2896 | 329 | `handle_chat_message` | `"avatar"` → `"XXavatarXX"` | 即時訊息頭像讀錯鍵，一律 None | user_info 帶 avatar 時斷言廣播 payload user.avatar 相同 |
| 3001 | 349 | `handle_chat_message` | `10000` → `0` | 成員切片 limit=0 回空，任何成員都收不到新訊息通知 | 3 人房發訊息，斷言 send_message_notification 被呼叫 2 次 |
| 2900 | 361 | `handle_chat_message` | `+` → `-` | str - str TypeError 被 fail-open 吞掉，超過 50 字的訊息不發任何通知 | 51 字訊息斷言通知被送出且預覽為前 50 字+... |
| 2901 | 365 | `handle_chat_message` | `!=` → `==` | 通知只發給發送者自己，其他成員都收不到 | 斷言通知對象為除發送者外的所有成員，且不含發送者 |
| 2910 | 456 | `_broadcast_bot_error` | `"room_id"` → `"XXroom_idXX"` | bot_error 缺 room_id，前端無法收掉 streaming 預覽，卡在打字中 | 串流失敗時斷言 bot_error payload room_id 正確 |
| 2740 | 464 | `<module>` | `50` → `0` | 撈取 limit=0→to_list ValueError，fail-open 使 @bot 多輪記憶恆空 | 斷言 _load_bot_history 以 >0 的 limit 撈取並回非空歷史 |
| 2741 | 523 | `handle_bot_mention` | `_bot_streaming_rooms.add(room_id)` → `pass` | 同房並發鎖從未加上，兩個 @bot 同時串流混入同一預覽並雙倍呼叫 AI | 串流中（stream 阻塞）同房第二次 @bot 應收到「正在回覆中」錯誤 |
| 3030 | 542 | `handle_bot_mention` | `"room_id"` → `"XXroom_idXX"` | bot_typing 缺 room_id，前端直接丟棄，串流預覽完全不顯示 | 斷言 bot_typing payload 含 room_id/user/content |
| 2743 | 594 | `<module>` | `30` → `0` | /summary 撈取 limit=0→ValueError，摘要指令永遠失敗 | 斷言 summary 以 limit=SUMMARY_MESSAGE_LIMIT(>0) 撈取並成功落地 |
| 2918 | 684 | `handle_typing_indicator` | `"user"` → `"XXuserXX"` | typing 事件缺 user，前端解構 TypeError，打字指示器失效 | 斷言 typing 廣播 payload user 等於 user_info |
| 2779 | 874 | `send_recent_messages` | `50` → `0` | 預設 limit=0→ValueError，連線時歷史載入失敗並跳「無法載入歷史訊息」 | 連線後斷言收到 message_history 含最近訊息 |

### `app/websocket/manager.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 3214 | 125 | `connect` | `"user"` → `"XXuserXX"` | user_joined 缺 user，前端 TypeError 丟棄事件，成員列表不更新 | 斷言 user_joined payload user 等於 user_info |
| 3215 | 126 | `connect` | `"timestamp"` → `"XXtimestampXX"` | 上線事件缺 timestamp 或在線狀態旗標錯誤，前端在線列表 / 系統訊息錯誤 | 對 user_joined / room_users / 狀態廣播做 payload 斷言 |
| 3174 | 138 | `connect` | `True` → `False` | 上線事件缺 timestamp 或在線狀態旗標錯誤，前端在線列表 / 系統訊息錯誤 | 對 user_joined / room_users / 狀態廣播做 payload 斷言 |
| 3199 | 147 | `connect` | `"global_online_user_ids"` → `"XXglobal_online_user_idsXX"` | room_users 缺 global_online_user_ids，前端退回房內邏輯，在別房在線者顯示離線 | 斷言連線後 room_users 含 global_online_user_ids 且含其他房在線者 |
| 3200 | 148 | `connect` | `"timestamp"` → `"XXtimestampXX"` | 上線事件缺 timestamp 或在線狀態旗標錯誤，前端在線列表 / 系統訊息錯誤 | 對 user_joined / room_users / 狀態廣播做 payload 斷言 |
| 3050 | 154 | `connect` | `await self._broadcast_user_status( user_id, use…` → `pass` | 上線時不通知其他房間 user_status_changed，其他房看不到其上線 | 使用者在 A 房時連 B 房，斷言 A 房收到 is_online=True |
| 3148 | 155 | `connect` | `True` → `False` | 上線事件缺 timestamp 或在線狀態旗標錯誤，前端在線列表 / 系統訊息錯誤 | 對 user_joined / room_users / 狀態廣播做 payload 斷言 |
| 3156 | 224 | `force_disconnect` | `self._schedule_offline(user_id)` → `pass` | 被踢/房間刪除後未排程離線，該使用者全域永遠顯示在線 | force_disconnect 唯一房間後推進時間，斷言 global_online_users 不含該使用者 |
| 3051 | 259 | `_broadcast_user_left` | `await self.broadcast_to_room( room_id, { "type"…` → `pass` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3175 | 262 | `_broadcast_user_left` | `"type"` → `"XXtypeXX"` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3179 | 262 | `_broadcast_user_left` | `"user_left"` → `"XXuser_leftXX"` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3176 | 263 | `_broadcast_user_left` | `"user"` → `"XXuserXX"` | user_left 缺 user，前端 TypeError 丟棄事件 | 斷言 user_left payload user 等於離線者資訊 |
| 3177 | 264 | `_broadcast_user_left` | `"timestamp"` → `"XXtimestampXX"` | user_joined/user_left 缺 timestamp，前端不產生「加入/離開聊天室」系統訊息 | 斷言 user_joined/user_left payload 含 ISO timestamp |
| 3116 | 279 | `_broadcast_user_status` | `continue` → `break` | 遇到排除房間即 break，排序在後的房間收不到上下線通知 | 使用者在三房，排除房在中間，斷言另兩房都收到 user_status_changed |
| 3074 | 280 | `_broadcast_user_status` | `await self.broadcast_to_room( rid, { "type": "u…` → `pass` | user_status_changed 不送/無法辨識，跨房在線狀態不同步 | 斷言其他房收到 type=user_status_changed |
| 3205 | 283 | `_broadcast_user_status` | `"type"` → `"XXtypeXX"` | user_status_changed 不送/無法辨識，跨房在線狀態不同步 | 斷言其他房收到 type=user_status_changed |
| 3210 | 283 | `_broadcast_user_status` | `"user_status_changed"` → `"XXuser_status_changedXX"` | user_status_changed 不送/無法辨識，跨房在線狀態不同步 | 斷言其他房收到 type=user_status_changed |
| 3206 | 284 | `_broadcast_user_status` | `"user_id"` → `"XXuser_idXX"` | 缺 user_id，前端直接 return，狀態不更新 | 斷言 user_status_changed payload user_id 正確 |
| 3208 | 286 | `_broadcast_user_status` | `"is_online"` → `"XXis_onlineXX"` | 缺 is_online，前端設為 undefined→上線者被標為離線 | 斷言 is_online 為布林且與事件一致 |
| 3053 | 303 | `_execute_offline` | `await asyncio.sleep(self._disconnect_debounce_s…` → `pass` | 離線 debounce 失效：重整/切房立即廣播離線與 user_left，重連又廣播加入，畫面閃爍 | disconnect 後未滿 debounce 秒前斷言未廣播 user_left/離線 |
| 3180 | 322 | `_execute_offline` | `==` → `!=` | 離線時處理到「其他」使用者的 pending room-leave，錯誤移除他人並以本人身分廣播離開 | 兩使用者都有 pending room-leave，A 離線後斷言 B 仍在 room_users |
| 3220 | 322 | `_execute_offline` | `0` → `1` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3164 | 330 | `_execute_offline` | `left_room_ids.append(rid)` → `pass` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3054 | 334 | `_execute_offline` | `saved_user_info` → `not (saved_user_info)` | 離線時不廣播或廣播成 is_online=True，其他人永遠看到其在線 | 離線 debounce 後斷言各房收到 is_online=False 與 user_left |
| 3120 | 336 | `_execute_offline` | `await self._broadcast_user_left(rid, saved_user…` → `pass` | 使用者離線時 user_left 不送/無法辨識，房內不顯示離開與系統訊息 | 離線 debounce 後斷言剩餘成員收到 type=user_left 且 user 正確 |
| 3081 | 337 | `_execute_offline` | `await self._broadcast_user_status(user_id, save…` → `pass` | 離線時不廣播或廣播成 is_online=True，其他人永遠看到其在線 | 離線 debounce 後斷言各房收到 is_online=False 與 user_left |
| 3184 | 337 | `_execute_offline` | `False` → `True` | 離線時不廣播或廣播成 is_online=True，其他人永遠看到其在線 | 離線 debounce 後斷言各房收到 is_online=False 與 user_left |
| 3084 | 353 | `_execute_room_leave` | `await asyncio.sleep(self._room_rejoin_debounce_…` → `pass` | 房間 rejoin debounce 失效：重整後重連即廣播 user_joined，系統訊息洗版 | 斷線後在 debounce 內（已讓出事件迴圈）重連，斷言未廣播 user_joined |

## 低價值（low）

共 387 個。

### `app/auth/dependencies.py`

- #31 L38 `"WWW-Authenticate"` → `"XXWWW-AuthenticateXX"`：401 回應的 WWW-Authenticate 標頭鍵/值，僅 RFC 相容性，不影響認證結果
- #32 L38 `"Bearer"` → `"XXBearerXX"`：401 回應的 WWW-Authenticate 標頭鍵/值，僅 RFC 相容性，不影響認證結果
- #33 L48 `"WWW-Authenticate"` → `"XXWWW-AuthenticateXX"`：401 回應的 WWW-Authenticate 標頭鍵/值，僅 RFC 相容性，不影響認證結果
- #34 L48 `"Bearer"` → `"XXBearerXX"`：401 回應的 WWW-Authenticate 標頭鍵/值，僅 RFC 相容性，不影響認證結果
- #35 L77 `"WWW-Authenticate"` → `"XXWWW-AuthenticateXX"`：版本不符時 401 回應的 WWW-Authenticate 標頭
- #36 L77 `"Bearer"` → `"XXBearerXX"`：版本不符時 401 回應的 WWW-Authenticate 標頭

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
- #106 L71 `".env"` → `"XX.envXX"`：env_file 名稱錯：本機 .env 不載入，缺 JWT_SECRET 會啟動即報錯（大聲失敗）
- #107 L71 `True` → `False`：縮圖開關預設值，僅效能/體驗

### `app/core/bot.py`

- #109 L25 `"bot@chatroom.app"` → `"XXbot@chatroom.appXX"`：僅改種子化 bot 帳號 email；bot 以 username 查找，無功能影響
- #116 L110 `6` → `7`：多輪歷史往返組數調參（6→7），僅影響 token 用量
- #118 L111 `10` → `11`：歷史時間窗調參（10→11 分鐘）
- #120 L112 `200` → `201`：歷史回答截斷字數調參（200→201）
- #152 L150 `>=` → `>`：時間窗邊界恰好相等才有差，實務不可觀察
- #148 L166 `"\n"` → `"XX\nXX"`：僅改 LLM prompt 內歷史換行格式

### `app/core/exceptions.py`

- #168 L29 `"WWW-Authenticate"` → `"XXWWW-AuthenticateXX"`：UnauthorizedError 的 WWW-Authenticate 鍵/值，僅 RFC 相容性
- #169 L29 `"Bearer"` → `"XXBearerXX"`：UnauthorizedError 的 WWW-Authenticate 鍵/值，僅 RFC 相容性

### `app/database/mongodb.py`

- #267 L30 `await self.client.admin.command("ping")` → `pass`：啟動時不驗證 Mongo 連線，僅失去 fail-fast
- #259 L40 `self.client` → `not (self.client)`：僅影響 shutdown 清理與連線釋放
- #263 L41 `await self.client.close()` → `pass`：僅影響 shutdown 清理與連線釋放
- #264 L42 `self.client = None` → `pass`：僅影響 shutdown 清理與連線釋放
- #265 L43 `self.database = None` → `pass`：僅影響 shutdown 清理與連線釋放
- #252 L64 `await _db_manager.disconnect()` → `pass`：僅影響 shutdown 清理與連線釋放

### `app/database/redis_conn.py`

- #282 L30 `await self.redis_client.ping()` → `pass`：啟動不 ping，僅失去 fail-fast
- #274 L38 `self.redis_client` → `not (self.redis_client)`：僅影響 shutdown 清理
- #277 L39 `await self.redis_client.aclose()` → `pass`：僅影響 shutdown 清理
- #278 L40 `self.redis_client = None` → `pass`：僅影響 shutdown 清理
- #272 L61 `await _redis_manager.disconnect()` → `pass`：僅影響 shutdown 清理

### `app/main.py`

- #317 L53 `"1.0.0"` → `"XX1.0.0XX"`：OpenAPI 版本字串
- #318 L63 `"*"` → `"XX*XX"`：CORS / TrustedHost 萬用字元字串，改壞會 fail-closed
- #319 L66 `"*"` → `"XX*XX"`：CORS / TrustedHost 萬用字元字串，改壞會 fail-closed
- #341 L67 `"*"` → `"XX*XX"`：CORS / TrustedHost 萬用字元字串，改壞會 fail-closed
- #342 L69 `","` → `"XX,XX"`：生產 CORS 來源變無效，屬 fail-closed，BFF 不受影響
- #287 L71 `app.add_middleware( CORSMiddleware, all…` → `pass`：移除 CORS 為 fail-closed，瀏覽器經 BFF 伺服器端呼叫
- #320 L74 `True` → `False`：關閉 allow_credentials 為 fail-closed
- #343 L75 `"GET"` → `"XXGETXX"`：CORS 允許方法字串錯，fail-closed
- #344 L75 `"POST"` → `"XXPOSTXX"`：CORS 允許方法字串錯，fail-closed
- #345 L75 `"PUT"` → `"XXPUTXX"`：CORS 允許方法字串錯，fail-closed
- #346 L75 `"DELETE"` → `"XXDELETEXX"`：CORS 允許方法字串錯，fail-closed
- #347 L75 `"OPTIONS"` → `"XXOPTIONSXX"`：CORS 允許方法字串錯，fail-closed
- #348 L77 `"Accept"` → `"XXAcceptXX"`：CORS 允許標頭字串錯，fail-closed
- #349 L77 `"Authorization"` → `"XXAuthorizationXX"`：CORS 允許標頭字串錯，fail-closed
- #350 L77 `"Content-Type"` → `"XXContent-TypeXX"`：CORS 允許標頭字串錯，fail-closed
- #351 L77 `"X-Requested-With"` → `"XXX-Requested-WithXX"`：CORS 允許標頭字串錯，fail-closed
- #352 L84 `"*"` → `"XX*XX"`：CORS / TrustedHost 萬用字元字串，改壞會 fail-closed
- #353 L84 `","` → `"XX,XX"`：生產 CORS 來源變無效，屬 fail-closed，BFF 不受影響
- #288 L92 `security_config.development_mode = sett…` → `pass`：僅影響 DEBUG 下的寬鬆 CSP（Swagger），生產值不變
- #322 L96 `and` → `or`：預設環境下 custom_headers 已含同值 STS，僅 HSTS 停用設定被忽略
- #354 L96 `not` → ``：HSTS 開關的 DEBUG 判斷，custom_headers 仍會帶入 HSTS
- #333 L142 `"version"` → `"XXversionXX"`：根端點 version 欄位，僅資訊
- #335 L142 `"1.0.0"` → `"XX1.0.0XX"`：根端點 version 欄位，僅資訊
- #338 L151 `"infrastructure"` → `"XXinfrastructureXX"`：health 回應 infrastructure 鍵名

### `app/middleware/error_handler.py`

- #368 L38 `False` → `True`：建構子預設值，main 明確傳入 debug
- #370 L71 `await self._log_error(request, exc, err…` → `pass`：僅錯誤日誌
- #415 L79 `"timestamp"` → `"XXtimestampXX"`：錯誤回應附帶資訊欄位（timestamp/path/method）鍵名
- #416 L80 `"path"` → `"XXpathXX"`：錯誤回應附帶資訊欄位（timestamp/path/method）鍵名
- #417 L81 `"method"` → `"XXmethodXX"`：錯誤回應附帶資訊欄位（timestamp/path/method）鍵名
- #405 L90 `not` → ``：僅 traceback 日誌條件
- #430 L96 `"Content-Type"` → `"XXContent-TypeXX"`：Content-Type 鍵名錯，JSONResponse 仍自帶 application/json
- #431 L96 `"application/json; charset=utf-8"` → `"XXapplication/json; ch…`：Content-Type 值錯，BFF/客戶端未依此判斷
- #433 L133 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #440 L141 `"writeErrors"` → `"XXwriteErrorsXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #441 L149 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #442 L158 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #443 L166 `"error"` → `"XXerrorXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #407 L174 `self.debug` → `not (self.debug)`：僅 debug 回應少 error_type；生產 details 本就不顯示
- #435 L174 `"error_type"` → `"XXerror_typeXX"`：僅 debug 模式顯示的 details 內容/鍵名
- #389 L186 `"method"` → `"XXmethodXX"`：日誌欄位鍵名
- #390 L187 `"url"` → `"XXurlXX"`：日誌欄位鍵名
- #391 L188 `"status_code"` → `"XXstatus_codeXX"`：日誌欄位鍵名
- #392 L189 `"error_code"` → `"XXerror_codeXX"`：日誌欄位鍵名
- #393 L190 `"error_message"` → `"XXerror_messageXX"`：日誌欄位鍵名
- #394 L191 `"timestamp"` → `"XXtimestampXX"`：日誌欄位鍵名
- #395 L192 `"user_agent"` → `"XXuser_agentXX"`：日誌欄位鍵名
- #408 L192 `"user-agent"` → `"XXuser-agentXX"`：日誌欄位鍵名
- #396 L193 `"client_ip"` → `"XXclient_ipXX"`：日誌欄位鍵名

### `app/middleware/rate_limiting.py`

- #524 L60 `60` → `61`：突發視窗 60→61 秒，調參
- #528 L70 `60` → `61`：突發視窗 60→61 秒，調參
- #555 L70 `60` → `61`：突發視窗 60→61 秒，調參
- #498 L75 `0` → `1`：429 回應的說明欄位與 Remaining 標頭內容
- #499 L76 `-` → `+`：Retry-After/reset 秒數計算，僅提示值
- #532 L76 `%` → `*`：Retry-After/reset 秒數計算，僅提示值
- #453 L83 `await self.redis.expire(key, window_siz…` → `pass`：key 不設 TTL，閒置 key 殘留 Redis，僅資源
- #534 L83 `+` → `-`：key TTL ±1~2 秒，影響可忽略
- #557 L83 `1` → `2`：key TTL ±1~2 秒，影響可忽略
- #502 L86 `%` → `*`：Retry-After/reset 秒數計算，僅提示值
- #559 L117 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #562 L117 `60` → `61`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #563 L117 `60` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #564 L118 `100` → `101`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #566 L119 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #568 L122 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #571 L122 `300` → `301`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #572 L122 `300` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #573 L123 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #575 L124 `25` → `26`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #577 L127 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #580 L127 `60` → `61`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #581 L127 `60` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #582 L127 `200` → `201`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #584 L127 `100` → `101`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #586 L129 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #589 L129 `300` → `301`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #590 L129 `300` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #591 L129 `100` → `101`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #593 L129 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #595 L131 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #598 L131 `60` → `61`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #599 L131 `60` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #600 L131 `50` → `51`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #602 L131 `20` → `21`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #604 L133 `"window"` → `"XXwindowXX"`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #607 L133 `3600` → `3601`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #608 L133 `3600` → `0`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #609 L133 `5000` → `5001`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #611 L133 `500` → `501`：DEBUG 專用寬鬆限流表的鍵/數值，生產不使用
- #666 L203 `"default"` → `"XXdefaultXX"`：default 設定取值失敗→fail-open，僅影響 / 等非 API 路徑
- #661 L235 `False` → `True`：初始化失敗改回 True 後同樣在 dispatch 被 fail-open，結果相同只差 log
- #671 L273 `"message"` → `"XXmessageXX"`：429 回應的說明欄位與 Remaining 標頭內容
- #672 L274 `"retry_after"` → `"XXretry_afterXX"`：429 回應的說明欄位與 Remaining 標頭內容
- #677 L280 `"X-RateLimit-Limit"` → `"XXX-RateLimit-LimitXX"`：回應 X-RateLimit-* 資訊標頭
- #679 L282 `"X-RateLimit-Reset"` → `"XXX-RateLimit-ResetXX"`：回應 X-RateLimit-* 資訊標頭
- #683 L282 `+` → `-`：回應 X-RateLimit-* 資訊標頭
- #680 L283 `"X-RateLimit-Window"` → `"XXX-RateLimit-WindowXX"`：回應 X-RateLimit-* 資訊標頭
- #488 L293 `response.headers["X-RateLimit-Reset"] =…` → `pass`：回應 X-RateLimit-* 資訊標頭
- #553 L293 `+` → `-`：回應 X-RateLimit-* 資訊標頭

### `app/middleware/security_headers.py`

- #689 L31 `31536000` → `31536001`：建構子預設值，main 明確傳入 hsts_max_age
- #690 L31 `31536000` → `0`：建構子預設值，main 明確傳入 hsts_max_age
- #702 L58 `"strict-origin-when-cross-origin"` → `"XXstrict-origin-when-c…`：基礎標頭值被 custom_headers 同鍵覆寫，僅關閉自訂標頭時生效
- #703 L61 `"geolocation=(), microphone=(), camera=…` → `"XXgeolocation=(), micr…`：基礎標頭值被 custom_headers 同鍵覆寫，僅關閉自訂標頭時生效
- #704 L75 `"default-src 'self'; " "script-src 'sel…` → `"XXdefault-src 'self'; …`：基礎 CSP 被 security_config 的 CSP 覆寫，僅關閉自訂標頭時生效
- #724 L110 `"on"` → `"XXonXX"`：X-Forwarded-SSL 偵測 HTTPS，僅影響 HSTS 是否送出
- #729 L110 `"x-forwarded-ssl"` → `"XXx-forwarded-sslXX"`：X-Forwarded-SSL 偵測 HTTPS，僅影響 HSTS 是否送出
- #733 L136 `500` → `501`：錯誤日誌截斷長度
- #734 L136 `500` → `0`：錯誤日誌截斷長度
- #735 L147 `"error"` → `"XXerrorXX"`：中介層例外時的 500 回應文字
- #736 L147 `"Internal server error"` → `"XXInternal server erro…`：中介層例外時的 500 回應文字

### `app/models/user.py`

- #839 L17 `True` → `False`：is_active 預設僅影響缺欄位舊文件；建立時一律明確設 True
- #860 L101 `1` → `2`：密碼至少 6 字，1 字元現行密碼本就錯誤，僅 400→422

### `app/repositories/base.py`

- #936 L83 `1000` → `1001`：毫秒截斷誤差 ≤1ms，DB 與回傳值仍一致
- #937 L83 `1000` → `0`：時間戳被截到整秒，精度下降但排序有 _id 保底
- #949 L83 `1000` → `1001`：毫秒截斷誤差 ≤1ms，DB 與回傳值仍一致
- #872 L84 `document["created_at"] = now` → `pass`：created_at 改用模型值，未截斷毫秒，回傳與 DB 差 <1ms
- #908 L84 `"created_at"` → `"XXcreated_atXX"`：多寫垃圾欄位，created_at 未截斷毫秒
- #909 L85 `"updated_at"` → `"XXupdated_atXX"`：多寫垃圾欄位，updated_at 未截斷毫秒
- #939 L99 `1000` → `1001`：時間戳截斷到毫秒的常數，只影響次毫秒精度
- #951 L99 `1000` → `1001`：時間戳截斷到毫秒的常數，只影響次毫秒精度
- #925 L103 `"updated_at"` → `"XXupdated_atXX"`：remove_member 未更新 updated_at（改寫入垃圾欄位）
- #876 L148 `result.deleted_count` → `None`：刪除數量回傳值，呼叫端未使用
- #946 L159 `"id"` → `"XXidXX"`：rooms/users 文件多存 id:null；alias 優先，讀取不受影響

### `app/repositories/message_repository.py`

- #1021 L151 `"status"` → `"XXstatusXX"`：僅多存一個無用欄位 XXstatusXX，status 仍為 SENT，讀取忽略
- #1092 L182 `1000` → `1001`：時間戳截斷到毫秒的常數，只影響次毫秒精度
- #1093 L182 `1000` → `0`：edited_at 截到整秒，失去毫秒精度
- #1108 L182 `1000` → `1001`：時間戳截斷到毫秒的常數，只影響次毫秒精度
- #1068 L217 `1000` → `1001`：時間戳截斷到毫秒的常數，只影響次毫秒精度
- #1069 L217 `1000` → `0`：軟刪除 edited_at 截到整秒
- #1094 L217 `1000` → `1001`：時間戳截斷到毫秒的常數，只影響次毫秒精度
- #1098 L224 `"edited"` → `"XXeditedXX"`：軟刪除不再標 edited=True；已刪訊息自列表過濾、前端移除，幾乎不可見
- #1100 L224 `True` → `False`：軟刪除不再標 edited=True；已刪訊息自列表過濾、前端移除，幾乎不可見
- #1099 L225 `"edited_at"` → `"XXedited_atXX"`：軟刪除不寫 edited_at；已刪訊息不顯示
- #1073 L276 `"created_at"` → `"XXcreated_atXX"`：改以 _id 排序；單程序 ObjectId 與建立時間同序，僅多 worker 同秒可能錯序
- #1053 L368 `"created_at"` → `"XXcreated_atXX"`：搜尋排序退化為 _id 排序，實務與 created_at 同序
- #1054 L381 `<` → `<=`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見
- #1084 L381 `+` → `-`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見
- #1055 L382 `>` → `>=`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見
- #1085 L382 `1` → `2`：has_next/has_prev 被唯一呼叫端 router 丟棄（只回 messages），對外不可見
- #979 L399 `deleted_count` → `None`：刪除數量回傳值，呼叫端未使用

### `app/repositories/notification_repository.py`

- #1153 L94 `"created_at"` → `"XXcreated_atXX"`：find_many 追加 _id 降冪 tiebreaker，ObjectId 近似建立時間，排序幾乎不變（失去索引）
- #1170 L136 `"recent"` → `"XXrecentXX"`：facet 鍵改名使 recent_activity 恆為空；前端未使用此欄位
- #1187 L137 `"created_at"` → `"XXcreated_atXX"`：recent 依不存在欄位排序，取到非最新 5 筆；前端未使用 recent_activity
- #1178 L138 `5` → `6`：recent_activity 由 5 筆變 6 筆，調校常數且前端未使用
- #1145 L166 `"recent"` → `"XXrecentXX"`：facet 鍵改名使 recent_activity 恆為空；前端未使用此欄位

### `app/repositories/room_repository.py`

- #1314 L100 `"created_at"` → `"XXcreated_atXX"`：改以 _id tiebreaker 排序，與 created_at 幾乎同序
- #1316 L123 `"created_at"` → `"XXcreated_atXX"`：改以 _id tiebreaker 排序，與 created_at 幾乎同序
- #1317 L133 `"created_at"` → `"XXcreated_atXX"`：改以 _id tiebreaker 排序，與 created_at 幾乎同序
- #1214 L190 `success` → `not (success)`：僅影響 log 輸出，回傳值不變
- #1216 L215 `success` → `not (success)`：僅影響 log 輸出，回傳值不變

### `app/routers/auth.py`

- #1390 L148 `{"message": "密碼修改成功"}` → `None`：成功回應的提示訊息欄位，前端不依賴
- #1412 L148 `"message"` → `"XXmessageXX"`：成功回應的提示訊息欄位，前端不依賴

### `app/routers/messages.py`

- #1463 L44 `0` → `1`：分頁 / 搜尋查詢參數的預設值與邊界
- #1464 L45 `50` → `51`：分頁 / 搜尋查詢參數的預設值與邊界
- #1470 L45 `1` → `2`：分頁 / 搜尋查詢參數的預設值與邊界
- #1471 L45 `100` → `101`：分頁 / 搜尋查詢參數的預設值與邊界
- #1473 L47 `1` → `2`：分頁 / 搜尋查詢參數的預設值與邊界
- #1453 L123 `{"message": "訊息刪除成功"}` → `None`：成功回應的提示訊息欄位，前端不依賴
- #1468 L123 `"message"` → `"XXmessageXX"`：成功回應的提示訊息欄位，前端不依賴

### `app/routers/rooms.py`

- #1532 L47 `"/"` → `"XX/XX"`：帶結尾斜線的重複路由，前端使用無斜線版本
- #1546 L51 `50` → `51`：分頁 / 搜尋查詢參數的預設值與邊界
- #1570 L51 `1` → `2`：分頁 / 搜尋查詢參數的預設值與邊界
- #1571 L51 `100` → `101`：分頁 / 搜尋查詢參數的預設值與邊界
- #1573 L52 `100` → `101`：分頁 / 搜尋查詢參數的預設值與邊界
- #1551 L72 `50` → `51`：分頁 / 搜尋查詢參數的預設值與邊界
- #1576 L72 `1` → `2`：分頁 / 搜尋查詢參數的預設值與邊界
- #1577 L72 `100` → `101`：分頁 / 搜尋查詢參數的預設值與邊界
- #1524 L134 `{"message": "聊天室刪除成功"}` → `None`：成功回應的提示訊息欄位，前端不依賴
- #1557 L134 `"message"` → `"XXmessageXX"`：成功回應的提示訊息欄位，前端不依賴
- #1526 L183 `{"message": message}` → `None`：成功回應的提示訊息欄位，前端不依賴
- #1561 L183 `"message"` → `"XXmessageXX"`：成功回應的提示訊息欄位，前端不依賴
- #1563 L190 `50` → `51`：分頁 / 搜尋查詢參數的預設值與邊界
- #1580 L190 `1` → `2`：分頁 / 搜尋查詢參數的預設值與邊界
- #1581 L190 `100` → `101`：分頁 / 搜尋查詢參數的預設值與邊界
- #1566 L203 `50` → `51`：分頁 / 搜尋查詢參數的預設值與邊界
- #1584 L203 `1` → `2`：分頁 / 搜尋查詢參數的預設值與邊界
- #1585 L203 `100` → `101`：分頁 / 搜尋查詢參數的預設值與邊界
- #1587 L205 `1` → `2`：分頁 / 搜尋查詢參數的預設值與邊界

### `app/security_config.py`

- #1623 L47 `"default-src 'self' 'unsafe-inline' 'un…` → `"XXdefault-src 'self' '…`：開發模式（DEBUG）的寬鬆 CSP 字串
- #1632 L86 `"X-XSS-Protection"` → `"XXX-XSS-ProtectionXX"`：標頭鍵名錯，base_headers 仍補上正確標頭，只多一個無效標頭
- #1637 L86 `"1; mode=block"` → `"XX1; mode=blockXX"`：X-XSS-Protection 已被現代瀏覽器忽略
- #1639 L89 `"geolocation=(), microphone=(), camera=…` → `"XXgeolocation=(), micr…`：Permissions-Policy 對 JSON API 回應無實質作用

### `app/services/ai_service.py`

- #1643 L26 `0.6` → `1.6`：AI temperature 調參
- #1644 L27 `2048` → `2049`：max_tokens 2048→2049 調參
- #1646 L28 `60.0` → `61.0`：外部呼叫逾時 60→61 秒調參
- #1673 L64 `0` → `1`：thinking_budget 0→1 調參（Gemini 專用）

### `app/services/message_service.py`

- #1782 L297 `>` → `>=`：gap 恰為 200 時改走 full reload（最新 50 條+清空），一致性仍成立
- #1827 L299 `50` → `51`：全量重載筆數 50→51 調參
- #1832 L408 `"timestamp"` → `"XXtimestampXX"`：WS 事件 timestamp 欄位改名，前端未使用
- #1835 L447 `"room_id"` → `"XXroom_idXX"`：message_deleted 的 room_id 改名；前端只用 message_id
- #1837 L449 `"timestamp"` → `"XXtimestampXX"`：WS 事件 timestamp 欄位改名，前端未使用

### `app/services/room_service.py`

- #1980 L51 `owner` → `not (owner)`：僅缺 owner_name 的舊房間走補填 fallback
- #2065 L52 `room_data["owner_name"] = owner.username` → `pass`：僅缺 owner_name 的舊房間走補填 fallback
- #2123 L52 `"owner_name"` → `"XXowner_nameXX"`：僅缺 owner_name 的舊房間走補填 fallback
- #2141 L111 `True` → `False`：send_event 已內部吞例外，僅改變記錄方式
- #2073 L113 `isinstance(result, Exception)` → `not (isinstance(result,…`：僅影響錯誤 log 輸出
- #2129 L163 `16` → `17`：隨機邀請碼 / ticket 的位元組長度
- #2103 L206 `"creator_id"` → `"XXcreator_idXX"`：creator_id 欄位前端目前未使用
- #2149 L553 `"room_id"` → `"XXroom_idXX"`：前端 user_left handler 未使用 room_id
- #2056 L582 `[]` → `None`：不存在房間經 HTTP 已被 require_room_membership 擋下；WS 路徑被 try 吞掉

### `app/services/user_service.py`

- #2164 L249 `await self.user_repo.update_last_login(…` → `pass`：last_login_at 只寫入，不對外暴露也無讀取
- #2199 L277 `or` → `and`：refresh token 缺 sub 仍可換發；需持有有效簽章，無法偽造

### `app/utils/file_upload.py`

- #2338 L34 `"application/msword"` → `"XXapplication/mswordXX"`：.doc 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2339 L35 `"application/vnd.openxmlformats-officed…` → `"XXapplication/vnd.open…`：.docx 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2340 L36 `"text/plain"` → `"XXtext/plainXX"`：.txt 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2341 L37 `"text/markdown"` → `"XXtext/markdownXX"`：.md 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2363 L55 `"audio/mpeg"` → `"XXaudio/mpegXX"`：.mp3 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2364 L56 `"audio/wav"` → `"XXaudio/wavXX"`：.wav 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2365 L57 `"audio/ogg"` → `"XXaudio/oggXX"`：.ogg 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2366 L58 `"audio/mp4"` → `"XXaudio/mp4XX"`：.m4a 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2367 L59 `"audio/flac"` → `"XXaudio/flacXX"`：.flac 以附件下載，Content-Type 錯誤影響有限；MIME 回退僅變嚴格
- #2274 L132 `self.upload_dir.mkdir(exist_ok=True)` → `pass`：僅全新環境 uploads 不存在時，匯入時子目錄 mkdir 失敗致啟動崩潰，部署即發現
- #2374 L184 `>` → `>=`：僅大小恰等於上限的檔案被拒，影響極小
- #2308 L189 `>` → `>=`：僅大小恰等於上限的檔案被拒，影響極小
- #2376 L189 `255` → `256`：允許 256 字元檔名；儲存檔名由系統產生，無實際影響
- #2378 L193 `"<"` → `"XX<XX"`：「<」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2379 L193 `">"` → `"XX>XX"`：「>」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2380 L193 `":"` → `"XX:XX"`：「:」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2381 L193 `'"'` → `"XX\"XX"`：「"」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2382 L193 `"\|"` → `"XX\|XX"`：「|」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2383 L193 `"?"` → `"XX?XX"`：「?」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2384 L193 `"*"` → `"XX*XX"`：「*」不再被拒；原始檔名只存於前端未讀取的 original_name，儲存用產生檔名
- #2391 L217 `"%Y%m%d_%H%M%S"` → `"XX%Y%m%d_%H%M%SXX"`：僅檔名時間戳格式改變，仍唯一且安全
- #2452 L218 `8` → `9`：唯一碼多含一個「-」，僅外觀改變
- #2313 L276 `file_dir.mkdir(parents=True, exist_ok=T…` → `pass`：__init__ 已預建所有子目錄，僅執行期目錄被刪除時才有差異（防禦性）
- #2476 L276 `True` → `False`：僅 uploads 根目錄於執行期被刪除時才失敗（防禦性）
- #2455 L288 `"id"` → `"XXidXX"`：file id 為未持久化的隨機 uuid，前端未讀取
- #2457 L290 `"original_name"` → `"XXoriginal_nameXX"`：original_name 前端未讀取（BFF 自行補 originalName）
- #2459 L292 `"content_type"` → `"XXcontent_typeXX"`：content_type 欄位前端未讀取
- #2463 L296 `"relative_path"` → `"XXrelative_pathXX"`：relative_path 欄位無任何消費者
- #2465 L298 `"created_at"` → `"XXcreated_atXX"`：created_at 前端未讀取（BFF 另補 uploadedAt）

### `app/utils/image_processor.py`

- #2496 L13 `150` → `151`：縮圖尺寸 +1 像素，純調校常數
- #2498 L13 `150` → `151`：縮圖尺寸 +1 像素，純調校常數
- #2500 L13 `300` → `301`：縮圖尺寸 +1 像素，純調校常數
- #2502 L13 `300` → `301`：縮圖尺寸 +1 像素，純調校常數
- #2504 L13 `600` → `601`：縮圖尺寸 +1 像素，純調校常數
- #2506 L13 `600` → `601`：縮圖尺寸 +1 像素，純調校常數
- #2485 L18 `50_000_000` → `50000001`：像素上限 +1，邊界調校
- #2491 L24 `>` → `>=`：僅恰好 5 千萬像素的圖片被拒，邊界影響極小
- #2493 L41 `self.output_dir.mkdir(exist_ok=True)` → `pass`：僅全新環境 processed 不存在時啟動崩潰，部署即發現
- #2494 L45 `self.thumbnail_dir.mkdir(exist_ok=True)` → `pass`：僅全新環境 thumbnails 目錄不存在時縮圖靜默失敗（回 None），前端未用縮圖

### `app/utils/ws_ticket.py`

- #2666 L31 `32` → `33`：隨機邀請碼 / ticket 的位元組長度

### `app/websocket/auth.py`

- #2717 L39 `True` → `False`：使用者文件與 token 一律帶 is_active / token_version，預設值不會用到
- #2728 L45 `0` → `1`：使用者文件與 token 一律帶 is_active / token_version，預設值不會用到
- #2730 L92 `0` → `1`：使用者文件與 token 一律帶 is_active / token_version，預設值不會用到

### `app/websocket/handlers.py`

- #2733 L59 `task.add_done_callback(_on_ai_task_done)` → `pass`：完成的背景 AI task 不移出強引用集合，僅記憶體累積與異常未記錄
- #2735 L65 `_background_ai_tasks.discard(task)` → `pass`：完成的背景 AI task 不移出強引用集合，僅記憶體累積與異常未記錄
- #2746 L66 `and` → `or`：僅影響背景任務異常是否記錄 log
- #2781 L66 `not` → ``：僅影響背景任務異常是否記錄 log
- #2782 L66 `is not` → `is`：僅影響背景任務異常是否記錄 log
- #2789 L85 `"status"` → `"XXstatusXX"`：payload status 欄位前端未使用
- #2791 L87 `"client_id"` → `"XXclient_idXX"`：ack 已先以 server id 確認樂觀訊息，廣播去重靠 id，client_id 僅備援
- #2839 L91 `"id"` → `"XXidXX"`：payload.user.id/username 前端未使用（改用 top-level 欄位）
- #2748 L99 `payload["reply_to"] = msg.reply_to` → `pass`：前端只用 reply_to_message.username/content，reply_to 與預覽 id 未使用
- #2842 L99 `"reply_to"` → `"XXreply_toXX"`：前端只用 reply_to_message.username/content，reply_to 與預覽 id 未使用
- #2844 L101 `"id"` → `"XXidXX"`：payload.user.id/username 前端未使用（改用 top-level 欄位）
- #2940 L140 `"type"` → `"XXtypeXX"`：welcome 事件前端為 no-op
- #2944 L140 `"welcome"` → `"XXwelcomeXX"`：welcome 事件前端為 no-op
- #2941 L141 `"message"` → `"XXmessageXX"`：welcome 事件前端為 no-op
- #2942 L142 `"timestamp"` → `"XXtimestampXX"`：welcome 事件前端為 no-op
- #2943 L143 `"room_id"` → `"XXroom_idXX"`：welcome 事件前端為 no-op
- #2850 L200 `await websocket.close(code=4000, reason…` → `pass`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3022 L200 `4000` → `4001`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3023 L200 `4000` → `0`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3024 L200 `"Internal server error"` → `"XXInternal server erro…`：內部錯誤時的關閉碼/原因；伺服器乾淨關閉前端一律不重連，無差異
- #3026 L235 `"mark_read"` → `"XXmark_readXX"`：mark_read 為舊別名，前端只送 notification_read
- #3048 L245 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2809 L265 `""` → `"XXXX"`：僅缺 content 鍵的畸形客戶端會送出固定字串，前端總是帶 content
- #2997 L282 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2949 L297 `"system"` → `"XXsystemXX"`：使用者送 system 改存 TEXT；前端從不送 system（反而較安全）
- #2952 L320 `"message_id"` → `"XXmessage_idXX"`：ack 缺 message_id 僅暫時使樂觀訊息 id 為空，隨後廣播以 client_id 取代修正
- #2954 L322 `"room_id"` → `"XXroom_idXX"`：ack 的 room_id 前端未使用
- #2955 L323 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2860 L360 `>` → `>=`：通知預覽截斷長度/省略號的外觀差異
- #2898 L360 `50` → `51`：通知預覽截斷長度/省略號的外觀差異
- #2899 L360 `50` → `0`：通知預覽截斷長度/省略號的外觀差異
- #2957 L361 `"..."` → `"XX...XX"`：通知預覽截斷長度/省略號的外觀差異
- #3027 L361 `50` → `51`：通知預覽截斷長度/省略號的外觀差異
- #3028 L361 `50` → `0`：通知預覽截斷長度/省略號的外觀差異
- #2861 L363 `0` → `1`：sent_count 只用於 log
- #2959 L376 `+=` → `-=`：sent_count 只用於 log
- #3002 L376 `1` → `2`：sent_count 只用於 log
- #3005 L411 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2960 L428 `60` → `61`：AI 限流視窗 60→61 秒調參
- #2907 L445 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2911 L457 `"message"` → `"XXmessageXX"`：bot_error 的 message 前端不使用
- #2912 L458 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2739 L464 `50` → `51`：@bot 歷史撈取筆數 50→51 調參
- #2962 L473 `0` → `1`：略過最新一則（即當前未配對提問），歷史視窗只位移一則
- #2867 L530 `"username"` → `"XXusernameXX"`：bot 串流預覽暫時缺名稱，落地正式訊息後即被取代
- #2868 L530 `"avatar"` → `"XXavatarXX"`：avatar 本為 None，缺鍵與 null 前端呈現相同
- #3033 L545 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2742 L594 `30` → `31`：/summary 撈取筆數 30→31 調參
- #2963 L626 `0` → `1`：摘要逐字稿略過最新一則（通常為 /summary 本身）
- #2831 L677 `False` → `True`：前端總是帶 is_typing，預設值未被使用
- #2920 L686 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2921 L687 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用（以 ctx.roomId 為準）
- #2925 L709 `"global_online_user_ids"` → `"XXglobal_online_user_i…`：get_users 指令前端從未送出，僅影響非前端客戶端
- #2926 L710 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2927 L711 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用（以 ctx.roomId 為準）
- #2876 L735 `"notification"` → `"XXnotificationXX"`：前端只送 read_type='room' 且不帶 notification_id，此分支差異前端觸發不到
- #2832 L742 `False` → `True`：前端只送 read_type='room' 且不帶 notification_id，此分支差異前端觸發不到
- #2833 L744 `and` → `or`：前端只送 read_type='room' 且不帶 notification_id，此分支差異前端觸發不到
- #2968 L768 `>=` → `>`：房間已讀 0 筆時 success=False 不廣播，但本無通知需同步
- #3009 L768 `0` → `1`：房間已讀 0 筆時 success=False 不廣播，但本無通知需同步
- #2970 L779 `>` → `>=`：read_type='all' 前端從不經 WS 送出
- #3011 L779 `0` → `1`：房間已讀 0 筆時 success=False 不廣播，但本無通知需同步
- #2883 L786 `"data"` → `"XXdataXX"`：read_status_response 在前端為 no-op
- #2933 L787 `"read_type"` → `"XXread_typeXX"`：read_status_response 在前端為 no-op
- #2934 L788 `"notification_id"` → `"XXnotification_idXX"`：read_status_response 在前端為 no-op
- #2935 L789 `"target_room_id"` → `"XXtarget_room_idXX"`：read_status_response 在前端為 no-op
- #2936 L790 `"timestamp"` → `"XXtimestampXX"`：read_status_response 在前端為 no-op
- #2974 L804 `"timestamp"` → `"XXtimestampXX"`：read_status_response 在前端為 no-op
- #2778 L874 `50` → `51`：歷史筆數 50→51 調參
- #2987 L904 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用
- #2988 L905 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用（以 ctx.roomId 為準）
- #3020 L919 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 欄位改名，前端未使用

### `app/websocket/manager.py`

- #3061 L38 `3.0` → `4.0`：離線/重入房 debounce 秒數調參
- #3062 L45 `5.0` → `6.0`：離線/重入房 debounce 秒數調參
- #3095 L73 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3065 L74 `pending_task.cancel()` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3098 L81 `pending_room_task.cancel()` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3216 L127 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用
- #3196 L138 `"is_active"` → `"XXis_activeXX"`：前端以 global_online_user_ids 覆寫 is_active，此欄位無效果
- #3201 L149 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用
- #3202 L150 `"online_only"` → `"XXonline_onlyXX"`：online_only 旗標前端未使用
- #3204 L150 `True` → `False`：在線列表的 online_only 標記，前端未使用
- #3108 L193 `and` → `or`：and→or 只在不一致狀態下觸發 KeyError 或多排一次無害 room-leave
- #3157 L229 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3178 L265 `"room_id"` → `"XXroom_idXX"`：事件 room_id 前端未使用
- #3207 L285 `"user"` → `"XXuserXX"`：user_status_changed 的 user 物件前端未使用
- #3209 L287 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 前端未使用
- #3117 L295 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3052 L299 `self._pending_offline[user_id] = task` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3080 L318 `self._pending_offline.pop(user_id, None)` → `pass`：已完成 task 殘留在 _pending_offline，僅記憶體保留，後續邏輯檢查 done() 無害
- #3181 L324 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3161 L325 `task.cancel()` → `pass`：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3121 L343 `not` → ``：pending task 未取消/未追蹤，僅快速斷線重連時在線狀態提早變化
- #3185 L358 `in` → `not in`：僅在 cancel 競態才走到的分支，一般流程結果相同
- #3085 L375 `self._pending_room_leave.pop(room_key, …` → `pass`：已完成 room-leave task 殘留，離線時可能對舊房多送一次 user_left
- #3086 L391 `and` → `or`：使用者不在連線表時由靜默略過變 KeyError，皆在上層 catch-all 內
- #3140 L544 `"timestamp"` → `"XXtimestampXX"`：事件 timestamp 前端未使用

## 等價變異體（equivalent）

共 91 個。

### `app/auth/dependencies.py`

- #26 L73 `0` → `1`：user dict 來自 UserInDB.model_dump，必含 token_version，預設值用不到
- #28 L95 `True` → `False`：user dict 來自 UserInDB.model_dump，必含 is_active，預設值用不到
- #3 L126 `current_user` → `None`：唯一使用此依賴的路由都不讀取其回傳值

### `app/config.py`

- #90 L48 `"http://localhost:5173"` → `"XXhttp://localhost:517…`：FRONTEND_URL 在 app 內沒有任何讀取點

### `app/database/mongodb.py`

- #258 L23 `"chatroom"` → `"XXchatroomXX"`：所有呼叫端皆明確傳入 database_name，預設值不會被使用
- #256 L57 `"chatroom"` → `"XXchatroomXX"`：所有呼叫端皆明確傳入 database_name，預設值不會被使用

### `app/database/redis_conn.py`

- #285 L26 `True` → `False`：改回 bytes：json.loads 接受 bytes、計數為 int，所有使用點結果相同

### `app/main.py`

- #314 L103 `"http"` → `"XXhttpXX"`：FastAPI.middleware 忽略 middleware_type 參數

### `app/middleware/rate_limiting.py`

- #491 L53 `0` → `1`：zremrangebyscore 下限 0 改 1，時間戳記遠大於 1
- #494 L65 `0` → `1`：所有路徑設定都有 burst，else 分支不會執行
- #505 L174 `""` → `"XXXX"`：無 Authorization 時預設字串都不以 'Bearer ' 開頭，結果相同
- #481 L226 `and` → `or`：limiter 與 redis_client 總是同時被設定，and/or 判斷結果相同

### `app/middleware/security_headers.py`

- #719 L124 `"Server"` → `"XXServerXX"`：app 內沒有任何層預先設定 Server 標頭，覆寫與否結果相同

### `app/models/message.py`

- #765 L64 `"_id"` → `"XX_idXX"`：populate_by_name 且 _normalize_id 已補 id 鍵，alias 改名後 id 照常填入
- #768 L103 `True` → `False`：FastAPI 回應驗證本就傳 from_attributes=True，模型設定無影響
- #776 L146 `True` → `False`：巢狀欄位直接傳同類實例，pydantic 不需 from_attributes；無屬性驗證路徑

### `app/models/notification.py`

- #786 L58 `"_id"` → `"XX_idXX"`：_normalize_id 同時補 id 鍵且 populate_by_name=True，alias 從未用於序列化
- #788 L62 `True` → `False`：文件必含 _id 鍵，靠 alias 即可填入 id；程式中無以欄位名 id 建構
- #789 L81 `True` → `False`：NotificationResponse 僅以 **dict 或同類實例建構，from_attributes 不生效

### `app/models/room.py`

- #791 L24 `isinstance(v, str)` → `not (isinstance(v, str))`：StrEnum 本身即 str，兩分支最終皆被驗證為同一枚舉值
- #833 L51 `"_id"` → `"XX_idXX"`：_normalize_id 恆補 id 鍵且 populate_by_name，alias 從未被使用
- #835 L62 `True` → `False`：改 populate_by_name 會使現有測試失敗，故此為 arbitrary_types_allowed，無作用
- #793 L71 `0` → `1`：member_count 一律由 _prepare_room_data 覆寫，預設值不會被用到
- #794 L72 `False` → `True`：has_password 一律由 _prepare_room_data 覆寫
- #795 L73 `False` → `True`：has_password 一律由 _prepare_room_data 覆寫
- #836 L77 `True` → `False`：回應模型無任何 alias 欄位，populate_by_name 無作用
- #837 L77 `True` → `False`：回應模型無任何 alias 欄位，populate_by_name 無作用

### `app/models/user.py`

- #858 L61 `True` → `False`：UserResponse 無 alias 欄位，populate_by_name 無作用
- #859 L61 `True` → `False`：UserResponse 無 alias 欄位，populate_by_name 無作用
- #842 L80 `"bearer"` → `"XXbearerXX"`：AuthResponse 所有建構點皆明確傳入 token_type
- #843 L95 `"bearer"` → `"XXbearerXX"`：RefreshResponse 由 service dict 建構，必含 token_type

### `app/repositories/base.py`

- #919 L28 `"id"` → `"XXidXX"`：寫入時皆 exclude id，文件從不帶 id 欄位，是否覆寫結果相同
- #863 L30 `document` → `None`：所有呼叫端皆忽略回傳值（就地修改 dict）
- #887 L58 `100` → `101`：所有 find_many 呼叫端皆明確傳入 limit
- #888 L58 `100` → `0`：所有 find_many 呼叫端皆明確傳入 limit
- #920 L64 `"_id"` → `"XX_idXX"`：無呼叫端以 _id 排序，恆追加 tiebreaker 與原行為相同
- #948 L65 `"_id"` → `"XX_idXX"`：無呼叫端以 _id 排序，恆追加 tiebreaker 與原行為相同
- #874 L91 `str(result.inserted_id)` → `None`：所有呼叫端皆忽略 insert_one 回傳值
- #913 L110 `and` → `or`：無呼叫端使用 upsert，upserted_id 恆為 None

### `app/repositories/message_repository.py`

- #963 L151 `message_dict["status"] = MessageStatus.…` → `pass`：model_dump 已含預設 status=SENT，唯一呼叫端不傳其他狀態，覆寫值相同
- #1000 L240 `20` → `21`：repo 預設 limit 從未使用：所有呼叫端（service 兩處）皆明確傳 limit

### `app/repositories/notification_repository.py`

- #1135 L71 `20` → `21`：唯一呼叫端 NotificationService 一律明確傳 limit，預設值永不使用
- #1193 L142 `1` → `2`：$project 中 1 與 2 皆為包含欄位
- #1194 L143 `1` → `2`：$project 中 1 與 2 皆為包含欄位
- #1195 L144 `1` → `2`：$project 中 1 與 2 皆為包含欄位
- #1171 L153 `1` → `2`：$facet 只會回傳一筆文件

### `app/repositories/room_repository.py`

- #1242 L98 `20` → `21`：Service 一律明確傳入 skip/limit，預設值不被使用
- #1245 L105 `20` → `21`：Service 一律明確傳入 limit
- #1248 L113 `20` → `21`：Service 一律明確傳入 limit
- #1251 L128 `20` → `21`：Service 一律明確傳入 limit
- #1254 L141 `20` → `21`：Service 一律明確傳入 limit
- #1256 L142 `True` → `False`：Service 一律以位置參數明確傳入 public_only
- #1313 L211 `""` → `"XXXX"`：$unset 忽略欄位值內容

### `app/services/message_service.py`

- #1777 L259 `0` → `1`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1778 L260 `20` → `21`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1779 L260 `20` → `0`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1820 L323 `"_id"` → `"XX_idXX"`：model_dump() 只產生 id 鍵，'_id' 與 'XX_idXX' 皆不在 dict，分支永不執行

### `app/services/room_service.py`

- #1946 L45 `room_data["id"] = room.id if room.id el…` → `pass`：model_dump 已含 id，且 room.id 實務上恆非空
- #2060 L45 `"id"` → `"XXidXX"`：多出的鍵被 Pydantic 忽略，id 仍來自 model_dump
- #2097 L45 `"_id"` → `"XX_idXX"`：僅 room.id 為空時才求值，實務不可達
- #2098 L45 `""` → `"XXXX"`：僅 room.id 為空時才求值，實務不可達
- #1947 L46 `room_data.pop("_id", None)` → `pass`：model_dump 不含 _id 鍵，pop 本為 no-op
- #2061 L46 `"_id"` → `"XX_idXX"`：僅 room.id 為空時才求值，實務不可達
- #1985 L89 `<` → `<=`：過期時間與現在時間完全相等（微秒級）的邊界
- #2008 L273 `0` → `1`：唯一呼叫端（GET /rooms/my）一律明確傳入 skip
- #2009 L273 `20` → `21`：唯一呼叫端一律明確傳入 limit
- #2010 L273 `20` → `0`：唯一呼叫端一律明確傳入 limit
- #2053 L566 `50` → `51`：所有呼叫端皆明確傳入 limit
- #2054 L566 `50` → `0`：所有呼叫端皆明確傳入 limit
- #2120 L596 `"_id"` → `"XX_idXX"`：model_dump 輸出 id 而非 _id，此分支為死碼
- #2096 L598 `user.id` → `not (user.id)`：model_dump 已含 id，此補值分支為死碼
- #2121 L599 `user_dict["id"] = str(user.id)` → `pass`：model_dump 已含 id，此補值分支為死碼
- #2153 L599 `"id"` → `"XXidXX"`：model_dump 已含 id，此補值分支為死碼

### `app/services/user_service.py`

- #2205 L42 `"_id"` → `"XX_idXX"`：model_dump 預設不用 alias，鍵為 id 而非 _id，此分支原本就是死碼

### `app/utils/file_upload.py`

- #2373 L71 `True` → `False`：四類副檔名與 MIME 清單長度一致，strict 僅在長度不符時才有作用
- #2244 L107 `16` → `17`：最深簽章僅到 offset 12，讀 16 或 17 bytes 比對結果相同
- #2302 L136 `(self.upload_dir / file_type).mkdir(exi…` → `pass`：save_file 以 mkdir(parents=True) 再建目錄，預建子目錄冗餘、無可觀察差異
- #2387 L198 `"file_type"` → `"XXfile_typeXX"`：validation_info 的 file_type 鍵從未被讀取（save_file 用回傳的 file_type）
- #2390 L201 `"size"` → `"XXsizeXX"`：validation_info 的 size 鍵從未被讀取
- #2481 L234 `4096` → `4097`：SHA-256 結果與讀取 chunk 大小無關

### `app/utils/user_cache.py`

- #2642 L13 `"user_cache"` → `"XXuser_cacheXX"`：前綴只經 _cache_key 一致使用，別處無硬編碼
- #2655 L55 `False` → `True`：ensure_ascii 只影響跳脫，json.loads 還原結果相同

### `app/utils/ws_ticket.py`

- #2659 L15 `"ws_ticket:"` → `"XXws_ticket:XX"`：建立與驗證使用同一前綴常數，無外部依賴

### `app/websocket/auth.py`

- #2723 L56 `"is_active"` → `"XXis_activeXX"`：停用帳號已在前面被拒，回傳的 is_active 恆為 True
- #2724 L56 `True` → `False`：使用者文件一律有 is_active，預設值不會用到；停用帳號已在前面被拒

### `app/websocket/handlers.py`

- #2734 L60 `task` → `None`：_spawn_ai_task 回傳值無任何呼叫端使用
- #2893 L266 `"text"` → `"XXtextXX"`：預設值只在缺鍵時用；'xxtextxx' 與 'text' 皆落入 else→TEXT
- #3000 L349 `10000` → `10001`：max_members 上限 1000，切片 [:10000] 與 [:10001] 結果相同

### `app/websocket/manager.py`

- #3146 L138 `user_data["is_active"] = True` → `pass`：user_info 由 _get_user_info 建立已含 is_active=True，copy 後重設相同值
- #3078 L316 `self.active_connections.pop(user_id, No…` → `pass`：此時 active_connections 不會有空 dict（各處皆刪鍵），pop 為 no-op
- #3160 L324 `and` → `or`：task 必非 None；對已完成 task 呼叫 cancel() 為 no-op，行為相同

## 從未被任何測試執行的函數

共 59 個函數、404 個變異體。括號內為該函數的變異體數。

- `app/core/bot.py`：`ensure_bot_user`（7）、`get_bot_user_id`（1）
- `app/core/fastapi_integration.py`：`create_ai_service`（1）、`create_file_service`（1）
- `app/main.py`：`lifespan`（6）
- `app/repositories/base.py`：`delete`（2）、`update_many`（15）
- `app/repositories/message_repository.py`：`count_after_seq`（6）、`get_after_seq`（11）、`get_by_client_id`（4）、`get_reply_previews`（8）
- `app/repositories/room_repository.py`：`update_member_role`（5）
- `app/routers/ai.py`：`get_ai_status`（2）
- `app/routers/files.py`：`download_file`（6）、`get_thumbnail`（4）、`upload_image_only`（3）、`upload_single_file`（2）
- `app/routers/notifications.py`：`clear_all_notifications`（5）、`delete_notification`（5）、`get_notification_stats`（3）、`get_notifications`（10）、`get_unread_notifications`（9）、`mark_all_notifications_read`（5）、`mark_notification_read`（5）
- `app/services/ai_service.py`：`is_available`（2）
- `app/services/file_service.py`：`_attach_uploader`（6）、`_save_file`（5）、`_try_generate_thumbnails`（2）、`_try_get_image_info`（2）、`_validate_filename`（3）、`_validate_path_within`（3）、`resolve_download`（12）、`resolve_thumbnail`（9）、`upload_file`（11）、`upload_image`（12）
- `app/services/notification_service.py`：`_broadcast_stats_update`（9）、`clear_user_notifications`（2）、`create_notification`（1）、`delete_notification`（5）、`get_notification_stats`（1）、`get_user_notifications`（4）、`mark_all_as_read`（9）、`mark_as_read`（5）、`mark_room_notifications_as_read`（12）、`send_real_time_notification`（38）
- `app/utils/file_upload.py`：`get_file_upload_manager`（1）、`get_mime_type`（2）、`upload_file`（6）
- `app/utils/image_processor.py`：`create_multiple_thumbnails`（7）、`create_thumbnail`（10）、`get_image_info`（47）、`get_image_processor`（1）、`open_image`（6）、`resize_image`（17）
- `app/websocket/handlers.py`：`send_gap_messages`（9）
- `app/websocket/manager.py`：`broadcast_message`（8）、`get_global_online_user_ids`（1）、`handle_ping`（4）
- `app/websocket/routes.py`：`websocket_endpoint`（6）
