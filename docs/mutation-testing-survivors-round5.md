# 變異測試附錄（第五輪）：存活變異體與未覆蓋函數明細

本文件為 [變異測試報告](mutation-testing-report.md)「第五輪」一節的附錄，列出第五輪（補上通知 HTTP API、即時推播與批次已讀測試後）重跑時仍存活的變異體與從未被執行的函數。
前四輪的明細見 [第一輪](mutation-testing-survivors.md)、[第二輪](mutation-testing-survivors-round2.md)、[第三輪](mutation-testing-survivors-round3.md)、[第四輪](mutation-testing-survivors-round4.md)。編號為本輪 `gen` 產生的編號，與前四輪不同。

分類沿用第一輪的定義：程式碼未變的存活者延用第四輪的判讀（依檔案、函數、運算子、變異前後內容與行序配對）；本輪才出現的存活者與複核後改判的存活者為人工判讀。

## 目錄

- [高風險](#高風險high)
- [中風險](#中風險medium)
- [低價值](#低價值low)
- [等價變異體](#等價變異體equivalent)
- [從未被任何測試執行的函數](#從未被任何測試執行的函數)

## 高風險（high）

共 0 個。

## 中風險（medium）

共 40 個。

### `app/core/bot.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 140 | 147 | `build_bot_history` | `continue` → `break` | 遇到第一則非文字訊息即中斷，之後（較新）的 @bot 往返全部遺失 | 圖片訊息夾在兩組 @bot 往返中間，斷言兩組都進入歷史 |

### `app/core/exceptions.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 159 | 16 | `__init__` | `super().__init__(message)` → `pass` | Exception.args 為空，WS handler 以 str(e) 回傳的錯誤訊息變空字串 | WS 送空白/超長訊息，斷言 error payload 的 message 為具體中文訊息 |

### `app/core/fastapi_integration.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 178 | 113 | `get_health_check_info` | `await db.command("ping")` → `pass` | 不 ping Mongo：DB 斷線時健康檢查仍報 connected | get_database 回傳 command 會拋錯的 db，斷言 mongodb=disconnected |
| 180 | 123 | `get_health_check_info` | `await client.ping()` → `pass` | 不 ping Redis：Redis 斷線時健康檢查仍報 connected | get_redis 回傳 ping 會拋錯的 client，斷言 redis=disconnected |

### `app/main.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 290 | 112 | `<module>` | `app.add_middleware(GlobalErrorHandler, debug=se…` → `pass` | 移除全域錯誤處理：DuplicateKey 變 500、Redis 錯誤不回 503、格式改變 | 經 app 觸發 DuplicateKeyError，斷言 409 與 DUPLICATE_KEY_ERROR |
| 291 | 127 | `<module>` | `app.include_router(ai.router, prefix="/api")` → `pass` | AI router 未註冊，/api/ai/* 全部 404 | 對 /api/ai 路由做存在性測試 |

### `app/middleware/error_handler.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 385 | 86 | `handle_error` | `and` → `or` | 非 debug 模式也回傳錯誤細節 / 例外訊息，生產環境資訊外洩 | debug=False 時 500 / DuplicateKeyError 回應不含 details |
| 387 | 90 | `handle_error` | `and` → `or` | 非 debug 模式也回傳錯誤細節 / 例外訊息，生產環境資訊外洩 | debug=False 時 500 / DuplicateKeyError 回應不含 details |

### `app/models/message.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 773 | 71 | `<class MessageInDB>` | `False` → `True` | edited 預設變 True：所有新訊息存成已編輯，前端每則顯示「（已編輯）」 | 建立訊息後斷言回應與 DB 的 edited is False |

### `app/repositories/message_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1094 | 50 | `next_room_seq` | `"counters"` → `"XXcountersXX"` | seq 計數器文件位置改變，上線後既有房間序號從 1 重來並與舊訊息重號 | next_room_seq 後 counters 中存在 _id=room_seq:{room_id} 且 seq 相符 |
| 1063 | 51 | `next_room_seq` | `"_id"` → `"XX_idXX"` | seq 計數器文件位置改變，上線後既有房間序號從 1 重來並與舊訊息重號 | next_room_seq 後 counters 中存在 _id=room_seq:{room_id} 且 seq 相符 |
| 1066 | 71 | `get_by_client_id` | `"room_id"` → `"XXroom_idXX"` | get_by_client_id 查不存在的欄位：重送同一 client_id 時找不到既有訊息，冪等快速路徑失效，撞唯一索引後也無法回傳既有訊息 | 真實 DB：同 client_id 重送回傳同一筆 |
| 1067 | 71 | `get_by_client_id` | `"client_id"` → `"XXclient_idXX"` | get_by_client_id 查不存在的欄位：重送同一 client_id 時找不到既有訊息，冪等快速路徑失效，撞唯一索引後也無法回傳既有訊息 | 真實 DB：同 client_id 重送回傳同一筆 |
| 1000 | 188 | `update` | `is not` → `is` | 只改 content 時把 metadata 設成 null（API 可清掉檔案資訊），給 metadata 反被忽略 | 編輯帶 metadata 的訊息只改 content，斷言 metadata 保留 |
| 1086 | 321 | `get_after_seq` | `"status"` → `"XXstatusXX"` | 斷線補發包含已軟刪除的訊息，重連後已刪除訊息以佔位內容重新出現，與列表 API 不一致 | 補發結果不含已刪除訊息 |
| 1034 | 343 | `search_messages` | `"status"` → `"XXstatusXX"` | 搜尋結果包含已軟刪除訊息（佔位內容） | 刪除一則後搜尋其內容/佔位字，結果不應含該則 |
| 1021 | 355 | `search_messages` | `or` → `and` | 只帶 start_date 或 end_date 時日期篩選整個被忽略 | 只帶 start_date 搜尋，斷言較早訊息被排除 |

### `app/repositories/room_repository.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1325 | 112 | `get_user_rooms` | `"updated_at"` → `"XXupdated_atXX"` | 「我的房間」不再依最近更新時間排序 | 較舊房間更新後應排在 get_user_rooms 第一筆 |
| 1328 | 164 | `search_rooms` | `"name"` → `"XXnameXX"` | 搜尋結果不再依名稱字母序排列 | search_rooms 斷言結果依 name 升冪 |

### `app/security_config.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1634 | 58 | `get_csp_header` | `"default-src 'self'; " "script-src 'self'; " "s…` → `"XXdefault-src 'self'; script…` | 生產 CSP 字串毀損，default-src 指令失效 | 斷言生產 get_csp_header() 以 "default-src 'self';" 開頭 |

### `app/services/ai_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1682 | 159 | `stream_reply` | `True` → `False` | stream_text(delta=False) 回傳累積全文，handler 再累加→預覽與落地回覆重複亂碼 | 以多 chunk 串流 FunctionModel 斷言 yield 的片段串接等於完整回覆 |

### `app/services/message_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 1780 | 64 | `validate_message_content` | `>` → `>=` | 長度檢查 >→>=：恰好 2000 字元訊息被拒，與 Pydantic max_length=2000 不一致 | validate_message_content 2000 字元通過、2001 字元拋 AppError |
| 1809 | 345 | `_attach_reply_previews` | `reply_ids` → `not (reply_ids)` | 訊息列表 reply_to_message 引用預覽遺失 | 列表中回覆訊息斷言 reply_to_message.content 為被回覆內容 |
| 1848 | 350 | `_attach_reply_previews` | `r.reply_to` → `not (r.reply_to)` | 訊息列表 reply_to_message 引用預覽遺失 | 列表中回覆訊息斷言 reply_to_message.content 為被回覆內容 |
| 1814 | 383 | `update_message` | `is not` → `is` | 編輯跳過 strip/空白檢查；只改 metadata/status 時 None.strip 造成 500 | PUT 內容 '   ' 應 400；只帶 metadata 應 200 |
| 1815 | 384 | `update_message` | `update_data.content = self.validate_message_con…` → `pass` | 編輯路徑不驗證內容：純空白可通過、前後空白未去除，與 HTTP/WS 發送規則不一致 | update_message 內容為空白應拋 AppError，且儲存值已 strip |

### `app/services/room_service.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2093 | 60 | `_convert_to_summary` | `False` → `True` | WS room_created/updated 對所有人帶 is_member=True，前端誤判已加入 | _convert_to_summary 無 user_id 時 is_member is False |
| 2155 | 130 | `_notify_room_change` | `"room"` → `"XXroomXX"` | room_updated 事件缺 room 欄位，前端判為無效資料 | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 1989 | 355 | `update_room` | `await self._notify_room_change(room_id)` → `pass` | update_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 1993 | 491 | `join_room` | `await self._notify_room_change(room_id)` → `pass` | join_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |
| 2168 | 562 | `leave_room` | `"id"` → `"XXidXX"` | 離線者離開時 user 缺 id，前端無法自成員列表移除 | leave_room 斷言 user_left 的 type/user.id/timestamp/removed |
| 1998 | 577 | `leave_room` | `await self._notify_room_change(room_id)` → `pass` | leave_room 後不廣播 room_updated | join/leave/update 後斷言 send_event 收到 type=room_updated 與 room |

### `app/utils/file_upload.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2332 | 130 | `__init__` | `"uploads"` → `"XXuploadsXX"` | 上傳寫入 XXuploadsXX，但下載依 settings.UPLOAD_DIR=uploads，所有檔案下載 404 | 上傳後以 resolve_download 取回同檔；manager 目錄應等於 settings.UPLOAD_DIR |

### `app/utils/image_processor.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2540 | 39 | `__init__` | `"processed"` → `"XXprocessedXX"` | 輸出目錄改名，但 resolve_thumbnail 寫死 processed/thumbnails，縮圖恆 404 | 產生縮圖後 resolve_thumbnail 能找到同檔（兩處路徑應同源） |
| 2552 | 63 | `open_image` | `_ensure_pixel_limit(img)` → `pass` | 縮圖路徑的開圖不檢查像素上限：上傳超大圖片時解碼耗盡記憶體；Pillow 預設在約 1.8 億像素才拒絕 | 以超過 5 千萬像素的圖片呼叫 create_thumbnail 斷言被拒 |

### `app/websocket/handlers.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 2841 | 270 | `handle_chat_message` | `"metadata"` → `"XXmetadataXX"` | 讀不到 metadata：檔案/圖片訊息的檔名、大小、MIME 永久遺失 | WS 帶 metadata 送 file 訊息，斷言持久化 metadata 相同 |
| 2889 | 293 | `handle_chat_message` | `"image"` → `"XXimageXX"` | image/file 類型比對失效，圖片或檔案訊息存成 TEXT | 參數化 image/file，斷言 msg_type 對應 IMAGE/FILE |
| 2925 | 295 | `handle_chat_message` | `"file"` → `"XXfileXX"` | image/file 類型比對失效，圖片或檔案訊息存成 TEXT | 參數化 image/file，斷言 msg_type 對應 IMAGE/FILE |
| 2772 | 523 | `handle_bot_mention` | `_bot_streaming_rooms.add(room_id)` → `pass` | 同房並發鎖從未加上，兩個 @bot 同時串流混入同一預覽並雙倍呼叫 AI | 串流中（stream 阻塞）同房第二次 @bot 應收到「正在回覆中」錯誤 |

### `app/websocket/manager.py`

| # | 行 | 函數 | 變異 | 為何重要 | 建議補的測試 |
|---|---:|---|---|---|---|
| 3186 | 224 | `force_disconnect` | `self._schedule_offline(user_id)` → `pass` | 被踢/房間刪除後未排程離線，該使用者全域永遠顯示在線 | force_disconnect 唯一房間後推進時間，斷言 global_online_users 不含該使用者 |

## 低價值（low）

共 40 個。

### `app/core/bot.py`

- #153 L60 `32` → `33`：bot 帳號隨機密碼熵 256→264 位元
- #154 L60 `32` → `0`：bot 帳號密碼來源變成空字串；但登入表單拒絕空密碼（422），無法以此登入，屬縱深防禦

### `app/database/mongodb.py`

- #269 L49 `"Database not connected. Call connect()…` → `"XXDatabase not connect…`：未連線時的錯誤訊息文字

### `app/database/redis_conn.py`

- #283 L46 `"Redis not connected. Call connect() fi…` → `"XXRedis not connected.…`：未連線時的錯誤訊息文字

### `app/middleware/rate_limiting.py`

- #511 L197 `"unknown"` → `"XXunknownXX"`：request.client 為 None 時的分桶名稱

### `app/repositories/base.py`

- #951 L122 `1000` → `0`：update_many 的 updated_at 截到整秒，精度下降
- #904 L124 `update["$set"]["updated_at"] = now` → `pass`：update_many 帶 $set 時不刷新 updated_at（如全部已讀），只影響通知的 updated_at
- #935 L124 `"updated_at"` → `"XXupdated_atXX"`：update_many 的 updated_at 寫進垃圾欄位

### `app/repositories/message_repository.py`

- #1079 L273 `"seq"` → `"XXseqXX"`：before_seq 分頁改以不存在欄位排序，退回 _id tiebreaker；單一寫入者下 _id 與 seq 同序
- #1083 L299 `"status"` → `"XXstatusXX"`：gap 大小估算把已刪除訊息算進去，只影響是否改走全量重載的門檻

### `app/routers/files.py`

- #1449 L37 `"medium"` → `"XXmediumXX"`：縮圖預設尺寸；前端未使用縮圖
- #1450 L46 `"image/png"` → `"XXimage/pngXX"`：縮圖回應的 media_type；前端未使用縮圖

### `app/routers/notifications.py`

- #1509 L21 `100` → `101`：已有測試殺死、但完整重跑的測試選擇沒選到：limit=101 的請求在 FastAPI 驗證階段就回 422，不執行路由函數本體，覆蓋率對應不到 test_paging_bounds 的這個案例（check_kill 以整個測試檔驗證為 killed）
- #1512 L42 `100` → `101`：同 #1509：未讀通知 limit 上限 100→101，test_limit_bounds 的 101 案例會殺死它，但工具的測試選擇沒選到

### `app/services/file_service.py`

- #1702 L78 `await asyncio.to_thread( self._image_pr…` → `None`：圖片上傳回應的 image_info；前端未使用
- #1745 L123 `"image"` → `"XXimageXX"`：一般上傳不為圖片產生縮圖；前端未使用縮圖
- #1710 L141 `file_info["image_info"] = await self._t…` → `pass`：圖片上傳回應的 image_info；前端未使用
- #1748 L141 `"image_info"` → `"XXimage_infoXX"`：圖片上傳回應的 image_info；前端未使用
- #1693 L143 `self._attach_uploader(file_info, curren…` → `pass`：圖片上傳回應缺 uploaded_by / user_id；BFF 不使用
- #1731 L144 `"message"` → `"XXmessageXX"`：圖片上傳回應的 message 欄位名

### `app/services/room_service.py`

- #2157 L169 `16` → `17`：邀請碼 token_urlsafe(16→17) 只改變長度（22→23 字元），兩者都不可猜；前後端都不檢查長度
- #2173 L172 `16` → `17`：邀請碼 token_urlsafe(16→17) 只改變長度（22→23 字元），兩者都不可猜；前後端都不檢查長度
- #2159 L341 `16` → `17`：改私人時產生的邀請碼 token_urlsafe(16→17) 只改變長度（22→23 字元），兩者都不可猜；前後端都不檢查長度

### `app/utils/file_upload.py`

- #2330 L78 `"application/octet-stream"` → `"XXapplication/octet-st…`：未知副檔名的預設 MIME；下載端只允許白名單副檔名

### `app/utils/image_processor.py`

- #2568 L67 `!=` → `==`：RGB 轉換條件反轉：非 RGB 圖片的縮圖可能存檔失敗，上傳仍成功（縮圖為 graceful degradation）
- #2569 L92 `hasattr(img, "_getexif")` → `not (hasattr(img, "_get…`：EXIF 讀取條件；image_info 前端未使用
- #2592 L92 `"_getexif"` → `"XX_getexifXX"`：EXIF 讀取條件；image_info 前端未使用
- #2578 L94 `exif` → `not (exif)`：EXIF 讀取條件；image_info 前端未使用
- #2579 L145 `"filename"` → `"XXfilenameXX"`：image_info 欄位名；前端未使用
- #2580 L146 `"format"` → `"XXformatXX"`：image_info 欄位名；前端未使用
- #2581 L147 `"mode"` → `"XXmodeXX"`：image_info 欄位名；前端未使用
- #2583 L149 `"width"` → `"XXwidthXX"`：image_info 欄位名；前端未使用
- #2584 L150 `"height"` → `"XXheightXX"`：image_info 欄位名；前端未使用
- #2585 L151 `"file_size"` → `"XXfile_sizeXX"`：image_info 欄位名；前端未使用
- #2586 L152 `"exif"` → `"XXexifXX"`：image_info 欄位名；前端未使用
- #2588 L274 `85` → `86`：縮圖 JPEG 品質 / optimize 參數，只影響縮圖畫質與大小
- #2589 L274 `85` → `0`：縮圖 JPEG 品質 / optimize 參數，只影響縮圖畫質與大小
- #2590 L274 `True` → `False`：縮圖 JPEG 品質 / optimize 參數，只影響縮圖畫質與大小

### `app/utils/ws_ticket.py`

- #2697 L31 `32` → `33`：ws ticket token_urlsafe(32→33) 只把熵從 256 位元變 264 位元，沒有任何地方檢查長度

### `app/websocket/manager.py`

- #3160 L454 `"sender"` → `"XXsenderXX"`：broadcast_message 的 sender 欄位：所有呼叫端都傳 sender_id=None，sender 恆為 {}，前端也不讀此欄位

## 等價變異體（equivalent）

共 106 個。

### `app/auth/dependencies.py`

- #26 L73 `0` → `1`：user dict 來自 UserInDB.model_dump，必含 token_version，預設值用不到
- #28 L95 `True` → `False`：user dict 來自 UserInDB.model_dump，必含 is_active，預設值用不到
- #3 L126 `current_user` → `None`：唯一使用此依賴的路由都不讀取其回傳值

### `app/database/mongodb.py`

- #258 L23 `"chatroom"` → `"XXchatroomXX"`：所有呼叫端皆明確傳入 database_name，預設值不會被使用
- #256 L57 `"chatroom"` → `"XXchatroomXX"`：所有呼叫端皆明確傳入 database_name，預設值不會被使用

### `app/database/redis_conn.py`

- #285 L26 `True` → `False`：改回 bytes：json.loads 接受 bytes、計數為 int，所有使用點結果相同

### `app/main.py`

- #319 L66 `"*"` → `"XX*XX"`：TrustedHostMiddleware(allowed_hosts=["*"]) 等同放行所有 host，與不加此中介層相同
- #352 L84 `"*"` → `"XX*XX"`：TrustedHostMiddleware(allowed_hosts=["*"]) 等同放行所有 host，與不加此中介層相同
- #314 L103 `"http"` → `"XXhttpXX"`：FastAPI.middleware 忽略 middleware_type 參數

### `app/middleware/rate_limiting.py`

- #494 L53 `0` → `1`：zremrangebyscore 下界 0→1：分數為 epoch 秒，不會落在 0~1
- #497 L65 `0` → `1`：burst_size 為 None 時 burst_requests 0→1，但後續判斷以 burst_size 短路，值不被使用
- #666 L74 `1` → `2`：zrangebyscore num=1→2：多取一筆時 blocking[0] 仍是同一筆
- #507 L191 `""` → `"XXXX"`：無 Authorization 時預設字串都不以 'Bearer ' 開頭，結果相同
- #671 L220 `"default"` → `"XXdefaultXX"`：只有路徑以 default 開頭才會比對到；HTTP 路徑必以 / 開頭，且命中時取到的仍是 default 設定
- #484 L243 `and` → `or`：limiter 與 redis_client 總是同時被設定，and/or 判斷結果相同

### `app/middleware/security_headers.py`

- #726 L124 `"Server"` → `"XXServerXX"`：app 內沒有任何層預先設定 Server 標頭，覆寫與否結果相同

### `app/models/message.py`

- #772 L64 `"_id"` → `"XX_idXX"`：populate_by_name 且 _normalize_id 已補 id 鍵，alias 改名後 id 照常填入
- #775 L103 `True` → `False`：FastAPI 回應驗證本就傳 from_attributes=True，模型設定無影響
- #783 L146 `True` → `False`：巢狀欄位直接傳同類實例，pydantic 不需 from_attributes；無屬性驗證路徑

### `app/models/notification.py`

- #793 L58 `"_id"` → `"XX_idXX"`：_normalize_id 同時補 id 鍵且 populate_by_name=True，alias 從未用於序列化
- #795 L62 `True` → `False`：文件必含 _id 鍵，靠 alias 即可填入 id；程式中無以欄位名 id 建構
- #796 L81 `True` → `False`：NotificationResponse 僅以 **dict 或同類實例建構，from_attributes 不生效

### `app/models/room.py`

- #798 L24 `isinstance(v, str)` → `not (isinstance(v, str))`：StrEnum 本身即 str，兩分支最終皆被驗證為同一枚舉值
- #840 L51 `"_id"` → `"XX_idXX"`：_normalize_id 恆補 id 鍵且 populate_by_name，alias 從未被使用
- #842 L62 `True` → `False`：改 populate_by_name 會使現有測試失敗，故此為 arbitrary_types_allowed，無作用
- #800 L71 `0` → `1`：member_count 一律由 _prepare_room_data 覆寫，預設值不會被用到
- #801 L72 `False` → `True`：has_password 一律由 _prepare_room_data 覆寫
- #802 L73 `False` → `True`：has_password 一律由 _prepare_room_data 覆寫
- #843 L77 `True` → `False`：回應模型無任何 alias 欄位，populate_by_name 無作用
- #844 L77 `True` → `False`：回應模型無任何 alias 欄位，populate_by_name 無作用

### `app/models/user.py`

- #865 L61 `True` → `False`：UserResponse 無 alias 欄位，populate_by_name 無作用
- #866 L61 `True` → `False`：UserResponse 無 alias 欄位，populate_by_name 無作用
- #849 L80 `"bearer"` → `"XXbearerXX"`：AuthResponse 所有建構點皆明確傳入 token_type
- #850 L95 `"bearer"` → `"XXbearerXX"`：RefreshResponse 由 service dict 建構，必含 token_type

### `app/repositories/base.py`

- #926 L28 `"id"` → `"XXidXX"`：寫入時皆 exclude id，文件從不帶 id 欄位，是否覆寫結果相同
- #870 L30 `document` → `None`：所有呼叫端皆忽略回傳值（就地修改 dict）
- #894 L58 `100` → `101`：所有 find_many 呼叫端皆明確傳入 limit
- #895 L58 `100` → `0`：所有 find_many 呼叫端皆明確傳入 limit
- #927 L64 `"_id"` → `"XX_idXX"`：無呼叫端以 _id 排序，恆追加 tiebreaker 與原行為相同
- #881 L91 `str(result.inserted_id)` → `None`：所有呼叫端皆忽略 insert_one 回傳值
- #946 L99 `1000` → `1001`：k 毫秒變成 k*1001 微秒（k≤999），BSON 寫入截斷回 k 毫秒，呼叫端皆從 DB 讀回
- #920 L110 `and` → `or`：無呼叫端使用 upsert，upserted_id 恆為 None
- #950 L122 `1000` → `1001`：同 #939：毫秒截斷常數 1001 經 BSON 寫入仍截斷回同一毫秒，update_many 只回傳數量
- #960 L122 `1000` → `1001`：同 #950

### `app/repositories/message_repository.py`

- #1099 L182 `1000` → `1001`：同 #939：edited_at 經 $set 寫入後由 update 重新從 DB 讀回
- #1075 L217 `1000` → `1001`：同 #939：軟刪除的 edited_at 只寫入 DB，方法只回傳 bool
- #1007 L240 `20` → `21`：repo 預設 limit 從未使用：所有呼叫端（service 兩處）皆明確傳 limit
- #1016 L304 `200` → `201`：唯一呼叫端一律明確傳入 limit=SYNC_MAX_GAP，預設值用不到
- #1017 L304 `200` → `0`：唯一呼叫端一律明確傳入 limit=SYNC_MAX_GAP，預設值用不到

### `app/repositories/notification_repository.py`

- #1142 L71 `20` → `21`：唯一呼叫端 NotificationService 一律明確傳 limit，預設值永不使用
- #1200 L142 `1` → `2`：$project 的 1→2 仍是 inclusion，輸出相同
- #1201 L143 `1` → `2`：$project 的 1→2 仍是 inclusion，輸出相同
- #1202 L144 `1` → `2`：$project 的 1→2 仍是 inclusion，輸出相同
- #1178 L153 `1` → `2`：$facet 只產生一份文件，to_list(length=1→2) 結果相同

### `app/repositories/room_repository.py`

- #1251 L102 `20` → `21`：Service 一律明確傳入 skip/limit，預設值不被使用
- #1254 L109 `20` → `21`：Service 一律明確傳入 limit
- #1257 L117 `20` → `21`：Service 一律明確傳入 limit
- #1260 L132 `20` → `21`：Service 一律明確傳入 limit
- #1263 L145 `20` → `21`：Service 一律明確傳入 limit
- #1265 L146 `True` → `False`：Service 一律以位置參數明確傳入 public_only
- #1323 L215 `""` → `"XXXX"`：$unset 忽略欄位值內容

### `app/services/message_service.py`

- #1800 L263 `0` → `1`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1801 L264 `20` → `21`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1802 L264 `20` → `0`：預設值未被使用：兩個呼叫端（@bot 歷史、/summary）皆明確傳 skip=0 與 limit
- #1843 L327 `"_id"` → `"XX_idXX"`：model_dump() 只產生 id 鍵，'_id' 與 'XX_idXX' 皆不在 dict，分支永不執行

### `app/services/notification_service.py`

- #1883 L126 `0` → `1`：get_user_notifications 的預設值：唯一呼叫端（通知路由）一律明確傳入 skip 與 limit
- #1884 L127 `20` → `21`：同 #1883
- #1885 L127 `20` → `0`：同 #1883
- #1944 L340 `"status"` → `"XXstatusXX"`：讀不到 status 時退回 UNREAD；通知只由 create_notification 建立，建立當下一律是 UNREAD，結果相同（原判 low，複核後改判）
- #1958 L343 `"message"` → `"XXmessageXX"`：唯一呼叫端（create_notification）一律帶 content，message 回退值永遠用不到
- #1959 L343 `""` → `"XXXX"`：唯一呼叫端（create_notification）一律帶 content，message 回退值永遠用不到
- #1960 L346 `"message"` → `"XXmessageXX"`：唯一呼叫端（create_notification）一律帶 content，message 回退值永遠用不到
- #1961 L346 `""` → `"XXXX"`：唯一呼叫端（create_notification）一律帶 content，message 回退值永遠用不到
- #1962 L349 `"data"` → `"XXdataXX"`：唯一呼叫端一律帶 metadata，data 回退值永遠用不到
- #1963 L352 `"data"` → `"XXdataXX"`：唯一呼叫端一律帶 metadata，data 回退值永遠用不到

### `app/services/room_service.py`

- #1969 L45 `room_data["id"] = room.id if room.id el…` → `pass`：model_dump 已含 id，且 room.id 實務上恆非空
- #2085 L45 `"id"` → `"XXidXX"`：多出的鍵被 Pydantic 忽略，id 仍來自 model_dump
- #2125 L45 `"_id"` → `"XX_idXX"`：僅 room.id 為空時才求值，實務不可達
- #2126 L45 `""` → `"XXXX"`：僅 room.id 為空時才求值，實務不可達
- #1970 L46 `room_data.pop("_id", None)` → `pass`：model_dump 不含 _id 鍵，pop 本為 no-op
- #2086 L46 `"_id"` → `"XX_idXX"`：僅 room.id 為空時才求值，實務不可達
- #2008 L89 `<` → `<=`：過期時間與現在時間完全相等（微秒級）的邊界
- #2031 L281 `0` → `1`：唯一呼叫端（GET /rooms/my）一律明確傳入 skip
- #2032 L281 `20` → `21`：唯一呼叫端一律明確傳入 limit
- #2033 L281 `20` → `0`：唯一呼叫端一律明確傳入 limit
- #2078 L582 `50` → `51`：所有呼叫端皆明確傳入 limit
- #2079 L582 `50` → `0`：所有呼叫端皆明確傳入 limit
- #2148 L612 `"_id"` → `"XX_idXX"`：model_dump 輸出 id 而非 _id，此分支為死碼
- #2124 L614 `user.id` → `not (user.id)`：model_dump 已含 id，此補值分支為死碼
- #2149 L615 `user_dict["id"] = str(user.id)` → `pass`：model_dump 已含 id，此補值分支為死碼
- #2184 L615 `"id"` → `"XXidXX"`：model_dump 已含 id，此補值分支為死碼

### `app/services/user_service.py`

- #2236 L42 `"_id"` → `"XX_idXX"`：model_dump 預設不用 alias，鍵為 id 而非 _id，此分支原本就是死碼

### `app/utils/file_upload.py`

- #2404 L71 `True` → `False`：四類副檔名與 MIME 清單長度一致，strict 僅在長度不符時才有作用
- #2275 L107 `16` → `17`：最深簽章僅到 offset 12，讀 16 或 17 bytes 比對結果相同
- #2512 L234 `4096` → `4097`：SHA-256 結果與讀取 chunk 大小無關

### `app/utils/image_processor.py`

- #2577 L67 `"RGB"` → `"XXRGBXX"`：比對字串改壞後一律呼叫 convert("RGB")，RGB 圖片轉換為 no-op，結果相同
- #2546 L236 `"medium"` → `"XXmediumXX"`：唯一呼叫端一律傳入 size，預設值用不到

### `app/utils/user_cache.py`

- #2673 L13 `"user_cache"` → `"XXuser_cacheXX"`：前綴只經 _cache_key 一致使用，別處無硬編碼
- #2686 L55 `False` → `True`：ensure_ascii 只影響跳脫，json.loads 還原結果相同

### `app/utils/ws_ticket.py`

- #2690 L15 `"ws_ticket:"` → `"XXws_ticket:XX"`：建立與驗證使用同一前綴常數，無外部依賴

### `app/websocket/auth.py`

- #2754 L56 `"is_active"` → `"XXis_activeXX"`：停用帳號已在前面被拒，回傳的 is_active 恆為 True

### `app/websocket/handlers.py`

- #2924 L266 `"text"` → `"XXtextXX"`：預設值只在缺鍵時用；'xxtextxx' 與 'text' 皆落入 else→TEXT
- #3031 L349 `10000` → `10001`：max_members 上限 1000，切片 [:10000] 與 [:10001] 結果相同

### `app/websocket/manager.py`

- #3108 L316 `self.active_connections.pop(user_id, No…` → `pass`：此時 active_connections 不會有空 dict（各處皆刪鍵），pop 為 no-op
- #3190 L324 `and` → `or`：task 必非 None；對已完成 task 呼叫 cancel() 為 no-op，行為相同
- #3164 L454 `sender_id` → `not (sender_id)`：所有呼叫端都傳 sender_id=None；條件反轉後變成 user_info.get(None, {})，user_info 的鍵都是使用者 ID，結果仍是 {}

## 從未被任何測試執行的函數

共 11 個函數、35 個變異體。括號內為該函數的變異體數。

- `app/core/fastapi_integration.py`：`create_ai_service`（1）、`create_file_service`（1）
- `app/main.py`：`lifespan`（6）
- `app/repositories/base.py`：`delete`（2）
- `app/repositories/message_repository.py`：`get_reply_previews`（8）
- `app/repositories/room_repository.py`：`update_member_role`（5）
- `app/routers/ai.py`：`get_ai_status`（2）
- `app/services/ai_service.py`：`is_available`（2）
- `app/utils/file_upload.py`：`get_file_upload_manager`（1）、`upload_file`（6）
- `app/utils/image_processor.py`：`get_image_processor`（1）
