"""WebSocket 訊息處理器"""

import json
import logging
from datetime import UTC, datetime

from fastapi import WebSocket, WebSocketDisconnect

from app.config import settings
from app.core.bot import (
    BOT_USERNAME,
    get_bot_user_id,
    is_bot_trigger,
    is_summary_command,
)
from app.core.exceptions import AppError, NotFoundError
from app.core.fastapi_integration import (
    create_ai_service,
    create_message_service,
    create_notification_service,
    create_room_service,
)
from app.database.redis_conn import get_redis
from app.middleware.rate_limiting import SlidingWindowRateLimiter
from app.models.message import (
    MAX_CONTENT_LENGTH,
    MessageCreate,
    MessageResponse,
    MessageType,
)
from app.services.message_service import MessageService
from app.websocket.auth import websocket_auth_middleware
from app.websocket.manager import connection_manager

logger = logging.getLogger(__name__)

# 同房 bot streaming 並發鎖：預覽 id 僅含 roomId（bot-stream-${roomId}），同房
# 並發會讓兩次回覆累積進同一預覽、首次落地又誤收他人預覽；故一房一次只允許一個
# @bot streaming（單實例 in-memory，符合目前 per-room WS／單後端實例架構）
_bot_streaming_rooms: set[str] = set()


def _format_message_payload(msg: MessageResponse, avatar: str | None) -> dict:
    """將 MessageResponse 格式化為前端 Message 型別的 WS payload"""
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "user_id": msg.user_id,
        # top-level username：前端 Message 型別與 REST 回應皆以反正規化的 top-level
        # username 渲染；WS payload 必須一致，否則即時訊息會缺名稱（重整才正常）
        "username": msg.username,
        "content": msg.content,
        "message_type": msg.message_type,
        "status": msg.status,
        "seq": msg.seq,
        "client_id": msg.client_id,
        "created_at": msg.created_at,
        "metadata": msg.metadata,
        "user": {
            "id": msg.user_id,
            "username": msg.username,
            "avatar": avatar,
        },
    }


async def handle_websocket_connection(websocket: WebSocket, room_id: str):
    """
    處理 WebSocket 連線

    Args:
        websocket: WebSocket 連線物件
        room_id: 房間 ID
    """
    user_info = None
    user_id = None

    try:
        # 先接受 WebSocket 連接（必須在認證前接受，以便發送關閉訊息）
        await websocket.accept()

        # 認證使用者
        user_info = await websocket_auth_middleware(websocket, room_id)
        if not user_info:
            await websocket.close(code=4001, reason="Authentication failed")
            return

        user_id = user_info["id"]

        # 建立連線
        await connection_manager.connect(websocket, user_id, room_id, user_info)

        # 發送歡迎訊息
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "welcome",
                "message": f"歡迎 {user_info['username']} 加入聊天室！",
                "timestamp": datetime.now(UTC).isoformat(),
                "room_id": room_id,
            },
        )

        # 載入並發送歷史訊息：
        # 重連帶 last_seq → 只補發 gap（精確、不重不漏）
        # 首次連線（無 last_seq）→ 發送最近歷史訊息
        last_seq_param = websocket.query_params.get("last_seq")
        if last_seq_param and last_seq_param.isdigit():
            await send_gap_messages(user_id, room_id, int(last_seq_param))
        else:
            await send_recent_messages(user_id, room_id)

        # 處理訊息
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info(
                    f"WebSocket disconnected for user {user_id} in room {room_id}"
                )
                break
            except Exception as e:  # intentional catch-all: 接收失敗安全結束迴圈
                logger.warning(f"WebSocket receive failed for user {user_id}: {e}")
                break

            try:
                message_data = json.loads(data)
                await handle_message(user_id, room_id, message_data, user_info)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from user {user_id}")
                await connection_manager.send_personal_message(
                    user_id,
                    room_id,
                    {
                        "type": "error",
                        "message": "Invalid message format",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception as e:  # intentional catch-all: 訊息處理失敗不中斷 WS 連線
                logger.error(f"Error handling message from user {user_id}: {e}")
                await connection_manager.send_personal_message(
                    user_id,
                    room_id,
                    {
                        "type": "error",
                        "message": "Internal server error",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during connection setup")
    except Exception as e:  # intentional catch-all: WS 連線層級錯誤安全關閉
        logger.error(f"Error in WebSocket connection: {e}")
        try:
            await websocket.close(code=4000, reason="Internal server error")
        except Exception:  # intentional: close 失敗可安全忽略
            pass
    finally:
        # 清理連線：傳入當前 websocket 比對 identity，
        # 避免同 user 同房重連時舊連線的 finally 誤刪新連線
        if user_id:
            await connection_manager.disconnect(user_id, room_id, websocket)


async def handle_message(
    user_id: str,
    room_id: str,
    message_data: dict,
    user_info: dict,
):
    """
    處理收到的訊息

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        message_data: 訊息資料
        user_info: 使用者資訊
    """
    message_type = message_data.get("type")

    if message_type == "chat_message" or message_type == "message":
        await handle_chat_message(user_id, room_id, message_data, user_info)
    elif message_type == "ping":
        await connection_manager.handle_ping(user_id, room_id)
    elif message_type == "typing":
        await handle_typing_indicator(user_id, room_id, message_data, user_info)
    elif message_type == "get_users":
        await handle_get_users(user_id, room_id)
    elif message_type == "notification_read" or message_type == "mark_read":
        await handle_notification_read(user_id, room_id, message_data, user_info)
    else:
        logger.warning(f"Unknown message type: {message_type}")
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "error",
                "message": f"Unknown message type: {message_type}",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )


async def handle_chat_message(
    user_id: str,
    room_id: str,
    message_data: dict,
    user_info: dict,
):
    """
    處理聊天訊息

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        message_data: 訊息資料
        user_info: 使用者資訊
    """
    raw_content = message_data.get("content", "")
    message_type_str = message_data.get("message_type", "text").lower()
    # 客戶端訊息 ID（冪等去重 + ack 對應），兼容舊欄位名 temp_id
    client_id = message_data.get("client_id") or message_data.get("temp_id")
    temp_id = client_id
    metadata = message_data.get("metadata")  # 檔案元數據

    # 訊息內容驗證（商業邏輯委託 MessageService）
    try:
        content = MessageService.validate_message_content(raw_content)
    except AppError as e:
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now(UTC).isoformat(),
                "temp_id": temp_id,
            },
        )
        return

    try:
        # 使用 MessageService 創建訊息
        message_service = await create_message_service()

        # 根據前端發送的類型設置消息類型
        if message_type_str == "image":
            msg_type = MessageType.IMAGE
        elif message_type_str == "file":
            msg_type = MessageType.FILE  # 添加檔案類型支援
        elif message_type_str == "system":
            msg_type = MessageType.SYSTEM
        else:
            msg_type = MessageType.TEXT

        # 創建訊息
        message_create = MessageCreate(
            room_id=room_id,
            content=content,
            message_type=msg_type,
            metadata=metadata,
            client_id=client_id,
        )

        created_message = await message_service.create_message(user_id, message_create)

        # 先發送 ack 給發送者（真確認：訊息已持久化，攜帶 server id 與 seq）
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "ack",
                "client_id": client_id,
                "message_id": created_message.id,
                "seq": created_message.seq,
                "room_id": room_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        # 廣播訊息給房間內所有使用者（包括發送者，以確保訊息同步）
        message_payload = _format_message_payload(
            created_message, user_info.get("avatar")
        )

        # 如果有臨時 ID，添加到回應中（兼容舊欄位名）
        if temp_id:
            message_payload["temp_id"] = temp_id

        await connection_manager.broadcast_message(
            room_id, message_payload, None
        )  # 不排除任何用戶，確保發送者也能看到自己的訊息

        # 發送通知給房間內的其他成員
        try:
            # 獲取房間服務和通知服務
            room_service = await create_room_service()
            notification_service = await create_notification_service()

            # 獲取房間所有成員，通知必須發給每位成員。
            # limit 預設為 50，曾導致超過 50 人的房間後段成員收不到通知，
            # 因此顯式設為 10000 以涵蓋所有成員。
            room_members = await room_service.get_room_members(room_id, limit=10000)

            # 獲取房間信息（用於通知標題）
            try:
                room_info = await room_service.get_room_by_id(room_id)
                room_name = room_info.name
            except NotFoundError:
                room_name = f"房間 {room_id}"

            # 為每個成員（除發送者外）創建通知
            message_preview = created_message.content
            if len(message_preview) > 50:
                message_preview = message_preview[:50] + "..."

            sent_count = 0
            for member in room_members:
                if member.id != user_id:  # 不給自己發送通知
                    try:
                        await notification_service.send_message_notification(
                            user_id=member.id,
                            sender_name=created_message.username,
                            message_preview=message_preview,
                            room_name=room_name,
                            room_id=room_id,
                            sender_id=user_id,
                            message_id=created_message.id,
                        )
                        sent_count += 1
                    except Exception as e:  # intentional per-member fail-open
                        logger.error(
                            f"Failed to send notification to member {member.id}: {e}"
                        )

            logger.info(f"Notifications sent to {sent_count} members")
        except Exception as e:  # intentional fail-open: 通知前置準備失敗不影響訊息發送
            logger.error(f"Error preparing notifications: {e}")

        # AI 觸發：使用者訊息已落地廣播後處理（僅 TEXT）
        # @bot → streaming 問答；/summary → 對話摘要
        if msg_type == MessageType.TEXT:
            bot_question = is_bot_trigger(content)
            if bot_question is not None:
                await handle_bot_mention(user_id, room_id, bot_question)
            elif is_summary_command(content):
                await handle_summary_command(user_id, room_id)

        logger.info(f"Message saved and broadcasted: {user_id} -> {room_id}")

    except Exception as e:  # intentional catch-all: 訊息儲存失敗回報前端錯誤
        logger.error(f"Error saving message: {e}")
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "error",
                "message": "訊息發送失敗",
                "timestamp": datetime.now(UTC).isoformat(),
                "temp_id": temp_id,
            },
        )


async def _check_bot_rate_limit(user_id: str) -> tuple[bool, int]:
    """每使用者每分鐘 AI 使用上限（@bot 與 /summary 共用額度，複用 Redis 滑動視窗）。

    Returns:
        tuple[bool, int]: (是否允許, 重置秒數)；檢查失敗時 fail-open
    """
    try:
        redis_client = await get_redis()
        limiter = SlidingWindowRateLimiter(redis_client, settings)
        allowed, _, reset_time = await limiter.is_allowed(
            f"rate_limit:bot:{user_id}",
            window_size=60,
            max_requests=settings.BOT_RATE_LIMIT_PER_MINUTE,
        )
        return allowed, reset_time
    except Exception as e:  # intentional fail-open: 限流檢查失敗不擋 AI
        logger.error(f"Bot rate limit check failed: {e}")
        return True, 0


async def _send_bot_error(user_id: str, room_id: str, message: str):
    """回報 bot 前置錯誤給觸發者（限流／空問題，尚無預覽可收）"""
    await connection_manager.send_personal_message(
        user_id,
        room_id,
        {
            "type": "error",
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


async def _broadcast_bot_error(room_id: str, message: str):
    """廣播 bot 錯誤給房間，讓前端把 streaming 預覽收掉（而非卡在「打字中」）"""
    await connection_manager.broadcast_to_room(
        room_id,
        {
            "type": "bot_error",
            "room_id": room_id,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


async def handle_bot_mention(user_id: str, room_id: str, question: str):
    """
    處理 @bot 觸發（A1 streaming，兩階段）。

    階段一（瞬態預覽）：streaming 過程用 broadcast_to_room 發 bot_typing 增量，
        不走 seq、不持久化。
    階段二（正規落地）：streaming 結束後以 bot 身分走正規 create_message →
        broadcast_message（產生 seq、可持久化、可被 gap 補回）；前端收到正式
        訊息後把預覽替換成最終訊息。失敗時發 bot_error 讓前端收掉預覽。

    LLM 呼叫委託 ai_service（商業邏輯不寫在 handler）；bot 訊息刻意不發通知，
    避免每次回話全房間收到通知轟炸。

    Args:
        user_id: 觸發者 ID
        room_id: 房間 ID
        question: 去除 @bot 前綴後的問題（可能為空字串）
    """
    bot_user_id = get_bot_user_id()
    # 防迴圈保險：bot 尚未種子化或觸發者就是 bot 自身時不處理
    if not bot_user_id or user_id == bot_user_id:
        return

    # --- 前置檢查：限流／空問題（尚無預覽，僅回報觸發者）---
    allowed, reset_time = await _check_bot_rate_limit(user_id)
    if not allowed:
        await _send_bot_error(
            user_id, room_id, f"你呼叫 @bot 太頻繁了，請 {reset_time} 秒後再試"
        )
        return
    if not question:
        await _send_bot_error(user_id, room_id, "請在 @bot 後面輸入你的問題")
        return

    # --- 並發保護：同房一次只允許一個 bot streaming ---
    # 預覽 id 僅含 roomId，並發會讓兩次回覆累積進同一預覽、首次落地又誤收他人預覽
    if room_id in _bot_streaming_rooms:
        await _send_bot_error(user_id, room_id, "@bot 正在回覆中，請稍候再問")
        return
    _bot_streaming_rooms.add(room_id)
    try:
        # --- 階段一：streaming 瞬態預覽（廣播給全房間，含觸發者）---
        bot_user = {"id": bot_user_id, "username": BOT_USERNAME, "avatar": None}
        buffer = ""
        try:
            ai_service = await create_ai_service()
            async for delta in ai_service.stream_reply(question):
                if not delta:
                    continue
                buffer += delta
                await connection_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "bot_typing",
                        "room_id": room_id,
                        "user": bot_user,
                        "content": delta,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
        except AppError as e:
            # 可預期錯誤（如未配置 AI 供應商 API key）：收掉預覽並回報原因
            await _broadcast_bot_error(room_id, str(e))
            return
        except Exception as e:  # intentional catch-all: 外部服務逾時/斷線/429 收尾
            logger.error(f"Bot streaming failed: {e}")
            await _broadcast_bot_error(room_id, "AI 助理回覆中斷，請稍後再試")
            return

        answer = buffer.strip()[:MAX_CONTENT_LENGTH]
        if not answer:
            await _broadcast_bot_error(room_id, "AI 助理沒有產生回覆，請稍後再試")
            return

        # --- 階段二：正規落地（產生 seq、持久化）→ 前端用它替換預覽 ---
        try:
            message_service = await create_message_service()
            bot_message = await message_service.create_message(
                bot_user_id,
                MessageCreate(
                    room_id=room_id, content=answer, message_type=MessageType.TEXT
                ),
                skip_membership_check=True,
            )
            payload = _format_message_payload(bot_message, None)
            await connection_manager.broadcast_message(room_id, payload, None)
            logger.info(
                f"Bot streamed reply in room {room_id} (triggered by {user_id})"
            )
        except Exception as e:  # intentional catch-all: 落地失敗收掉預覽
            logger.error(f"Bot landing failed: {e}")
            await _broadcast_bot_error(room_id, "AI 助理回覆儲存失敗，請稍後再試")
    finally:
        _bot_streaming_rooms.discard(room_id)


# /summary 取用的近期訊息數
SUMMARY_MESSAGE_LIMIT = 30


async def handle_summary_command(user_id: str, room_id: str):
    """
    處理 /summary 指令（C）：撈近期訊息 → 摘要 → 以 bot 身分落地廣播。

    摘要為 one-shot（非 streaming），完整自我守護：失敗只回報觸發者，
    不影響聊天。與 @bot 共用每使用者限流額度；bot 訊息刻意不發通知。

    Args:
        user_id: 觸發者 ID
        room_id: 房間 ID
    """
    bot_user_id = get_bot_user_id()
    if not bot_user_id:
        await _send_bot_error(user_id, room_id, "AI 助理尚未就緒，請稍後再試")
        return

    # 限流（與 @bot 共用每使用者額度）
    allowed, reset_time = await _check_bot_rate_limit(user_id)
    if not allowed:
        await _send_bot_error(
            user_id, room_id, f"你呼叫 AI 太頻繁了，請 {reset_time} 秒後再試"
        )
        return

    try:
        # 撈近期訊息並組成 transcript（最舊→最新；排除 bot 自己與非文字訊息）
        message_service = await create_message_service()
        messages = await message_service.get_room_messages(
            room_id=room_id, skip=0, limit=SUMMARY_MESSAGE_LIMIT
        )
        lines = [
            f"{msg.username}: {msg.content}"
            for msg in messages
            if msg.message_type == MessageType.TEXT and msg.user_id != bot_user_id
        ]
        if not lines:
            await _send_bot_error(user_id, room_id, "目前沒有可摘要的訊息")
            return

        # 摘要（one-shot，商業邏輯在 ai_service）
        ai_service = await create_ai_service()
        summary = (await ai_service.summarize("\n".join(lines))).strip()
        if not summary:
            await _send_bot_error(user_id, room_id, "AI 助理沒有產生摘要，請稍後再試")
            return
        content = f"📋 對話摘要\n{summary}"[:MAX_CONTENT_LENGTH]

        # 以 bot 身分落地廣播（跳過成員檢查；刻意不發通知）
        bot_message = await message_service.create_message(
            bot_user_id,
            MessageCreate(
                room_id=room_id, content=content, message_type=MessageType.TEXT
            ),
            skip_membership_check=True,
        )
        payload = _format_message_payload(bot_message, None)
        await connection_manager.broadcast_message(room_id, payload, None)
        logger.info(f"Summary generated for room {room_id} (triggered by {user_id})")

    except AppError as e:
        # 可預期錯誤（如未配置 AI 供應商 API key）
        await _send_bot_error(user_id, room_id, str(e))
    except Exception as e:  # intentional catch-all: 摘要失敗不影響聊天
        logger.error(f"Error handling summary command: {e}")
        await _send_bot_error(user_id, room_id, "AI 助理暫時無法產生摘要，請稍後再試")


async def handle_typing_indicator(
    user_id: str, room_id: str, message_data: dict, user_info: dict
):
    """
    處理打字指示器

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        message_data: 訊息資料
        user_info: 使用者資訊
    """
    is_typing = message_data.get("is_typing", False)

    # 向房間內其他使用者廣播打字狀態
    await connection_manager.broadcast_to_room(
        room_id,
        {
            "type": "typing",
            "user": user_info,
            "is_typing": is_typing,
            "timestamp": datetime.now(UTC).isoformat(),
            "room_id": room_id,
        },
        exclude_user=user_id,
    )


async def handle_get_users(user_id: str, room_id: str):
    """
    處理獲取使用者列表請求

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
    """
    users = connection_manager.get_room_users(room_id)
    global_online_ids = connection_manager.get_global_online_user_ids()
    await connection_manager.send_personal_message(
        user_id,
        room_id,
        {
            "type": "room_users",
            "users": users,
            "global_online_user_ids": global_online_ids,
            "timestamp": datetime.now(UTC).isoformat(),
            "room_id": room_id,
        },
    )


async def handle_notification_read(
    user_id: str,
    room_id: str,
    message_data: dict,
    user_info: dict,
):
    """
    處理通知已讀狀態變更

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        message_data: 訊息資料
        user_info: 使用者資訊
    """
    try:
        # 獲取請求數據
        notification_id = message_data.get("notification_id")
        read_type = message_data.get(
            "read_type", "notification"
        )  # 'notification' | 'room'
        target_room_id = message_data.get("target_room_id", room_id)  # 目標房間ID

        # 獲取服務
        notification_service = await create_notification_service()

        success = False

        if read_type == "notification" and notification_id:
            # 標記單個通知為已讀
            try:
                await notification_service.mark_as_read(notification_id, user_id)
                success = True
            except Exception as e:  # intentional catch-all: 標記已讀失敗不中斷 WS 連線
                logger.error(
                    f"Failed to mark notification {notification_id} as read: {e}"
                )
            logger.info(
                f"Marked notification {notification_id} as read for user {user_id}: {success}"
            )

        elif read_type == "room" and target_room_id:
            # 標記房間相關通知為已讀
            try:
                logger.info(
                    f"[WebSocket] Processing room notification read request: user={user_id}, room={target_room_id}"
                )
                logger.info(f"[WebSocket] Message data: {message_data}")
                # 標記該房間所有未讀通知為已讀
                count = await notification_service.mark_room_notifications_as_read(
                    user_id, target_room_id
                )
                success = count >= 0  # 即使沒有未讀通知也算成功
                logger.info(
                    f"Marked {count} room notifications as read for user {user_id} in room {target_room_id}"
                )
            except Exception as e:  # intentional catch-all: 標記已讀失敗不中斷 WS 連線
                logger.error(f"Error marking room notifications as read: {e}")
                success = False

        elif read_type == "all":
            # 標記所有通知為已讀
            count = await notification_service.mark_all_as_read(user_id)
            success = count > 0
            logger.info(f"Marked {count} notifications as read for user {user_id}")

        # 發送響應
        response_data = {
            "type": "read_status_response",
            "success": success,
            "data": {
                "read_type": read_type,
                "notification_id": notification_id,
                "target_room_id": target_room_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        }

        await connection_manager.send_personal_message(user_id, room_id, response_data)

        # 如果成功，廣播狀態變更到用戶的所有設備
        if success:
            status_change_data = {
                "type": "notification_status_changed",
                "data": {
                    "read_type": read_type,
                    "id": notification_id or target_room_id,
                    "status": "read",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }

            await connection_manager.send_event(user_id, status_change_data)

            logger.info(
                f"Broadcasted read status change to all connections for user {user_id}"
            )

    except Exception as e:  # intentional catch-all: 通知已讀處理失敗不中斷 WS 連線
        logger.error(f"Error handling notification read: {e}")

        # 發送錯誤響應
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "read_status_response",
                "success": False,
                "error": "系統錯誤",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )


async def send_gap_messages(user_id: str, room_id: str, last_seq: int):
    """
    斷線重連補發：發送序號大於 last_seq 的訊息

    gap 超過上限時 full_reload=True，客戶端應清空並以本批訊息重載。

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        last_seq: 客戶端已知的最後序號
    """
    try:
        message_service = await create_message_service()
        messages, full_reload = await message_service.sync_messages_since(
            room_id, last_seq
        )

        formatted_messages = [
            _format_message_payload(msg, msg.avatar) for msg in messages
        ]

        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "message_sync",
                "messages": formatted_messages,
                "full_reload": full_reload,
                "last_seq": last_seq,
                "timestamp": datetime.now(UTC).isoformat(),
                "room_id": room_id,
            },
        )

        logger.info(
            f"Synced {len(formatted_messages)} messages to user {user_id} "
            f"(last_seq={last_seq}, full_reload={full_reload})"
        )

    except Exception as e:  # intentional catch-all: gap 補發失敗退回全量歷史
        logger.error(f"Error syncing gap messages: {e}")
        await send_recent_messages(user_id, room_id)


async def send_recent_messages(user_id: str, room_id: str, limit: int = 50):
    """
    發送最近的訊息記錄

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        limit: 訊息數量限制
    """
    try:
        # 使用 MessageService 獲取訊息
        message_service = await create_message_service()

        # 獲取最近的訊息（service 層已批次查詢 avatar）
        messages = await message_service.get_room_messages(
            room_id=room_id, skip=0, limit=limit
        )

        # 格式化訊息
        formatted_messages = []
        for msg in messages:
            formatted_messages.append(_format_message_payload(msg, msg.avatar))

        # 發送歷史訊息
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "message_history",
                "messages": formatted_messages,
                "timestamp": datetime.now(UTC).isoformat(),
                "room_id": room_id,
            },
        )

        logger.info(f"Sent {len(formatted_messages)} recent messages to user {user_id}")

    except Exception as e:  # intentional catch-all: 歷史訊息載入失敗回報前端錯誤
        logger.error(f"Error sending recent messages: {e}")
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "error",
                "message": "無法載入歷史訊息",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
