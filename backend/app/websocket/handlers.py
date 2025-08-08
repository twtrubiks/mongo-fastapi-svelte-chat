"""WebSocket 訊息處理器"""

import json
import logging
from datetime import UTC, datetime

from fastapi import WebSocket, WebSocketDisconnect

from app.core.container import get_container
from app.models.message import MessageCreate, MessageType
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService
from app.services.room_service import RoomService
from app.websocket.auth import websocket_auth_middleware
from app.websocket.manager import connection_manager

UTC = UTC

logger = logging.getLogger(__name__)


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

        # 載入並發送歷史訊息（使用獨立作用域）
        await send_recent_messages(user_id, room_id)

        # 為 WebSocket 連接創建作用域
        container = get_container()
        async with container.scope(f"websocket-{user_id}-{room_id}") as scope_id:
            # 處理訊息
            while True:
                try:
                    # 接收訊息
                    data = await websocket.receive_text()
                    message_data = json.loads(data)

                    # 處理不同類型的訊息
                    await handle_message(
                        user_id, room_id, message_data, user_info, scope_id
                    )

                except WebSocketDisconnect:
                    logger.info(
                        f"WebSocket disconnected for user {user_id} in room {room_id}"
                    )
                    break
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
                except Exception as e:
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
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        try:
            await websocket.close(code=4000, reason="Internal server error")
        except Exception:
            pass
    finally:
        # 清理連線
        if user_id:
            await connection_manager.disconnect(user_id, room_id)


async def handle_message(
    user_id: str,
    room_id: str,
    message_data: dict,
    user_info: dict,
    scope_id: str = None,
):
    """
    處理收到的訊息

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        message_data: 訊息資料
        user_info: 使用者資訊
        scope_id: 作用域 ID
    """
    message_type = message_data.get("type")

    if message_type == "chat_message" or message_type == "message":
        await handle_chat_message(user_id, room_id, message_data, user_info, scope_id)
    elif message_type == "ping":
        await connection_manager.handle_ping(user_id, room_id)
    elif message_type == "typing":
        await handle_typing_indicator(user_id, room_id, message_data, user_info)
    elif message_type == "get_users":
        await handle_get_users(user_id, room_id)
    elif message_type == "notification_read" or message_type == "mark_read":
        await handle_notification_read(
            user_id, room_id, message_data, user_info, scope_id
        )
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
    scope_id: str = None,
):
    """
    處理聊天訊息

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        message_data: 訊息資料
        user_info: 使用者資訊
        scope_id: 作用域 ID
    """
    content = message_data.get("content", "").strip()
    message_type_str = message_data.get("message_type", "text").lower()
    temp_id = message_data.get("temp_id")  # 前端臨時 ID
    metadata = message_data.get("metadata")  # 檔案元數據

    if not content:
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "error",
                "message": "訊息內容不能為空",
                "timestamp": datetime.now(UTC).isoformat(),
                "temp_id": temp_id,
            },
        )
        return

    # 檢查訊息長度（圖片和檔案URL可能較長，放寬限制）
    max_length = 2000 if message_type_str in ["image", "file"] else 1000
    if len(content) > max_length:
        await connection_manager.send_personal_message(
            user_id,
            room_id,
            {
                "type": "error",
                "message": f"訊息內容太長（最大 {max_length} 字元）",
                "timestamp": datetime.now(UTC).isoformat(),
                "temp_id": temp_id,
            },
        )
        return

    try:
        # 使用 MessageService 創建訊息
        container = get_container()
        message_service = await container.get(MessageService, scope_id)

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
            room_id=room_id, content=content, message_type=msg_type, metadata=metadata
        )

        created_message = await message_service.create_message(user_id, message_create)

        # 廣播訊息給房間內所有使用者（包括發送者，以確保訊息同步）
        message_payload = {
            "id": created_message.id,
            "room_id": created_message.room_id,
            "user_id": created_message.user_id,
            "content": created_message.content,
            "message_type": created_message.message_type,
            "status": created_message.status,
            "created_at": created_message.created_at,
            "metadata": created_message.metadata,
            "user": {
                "id": created_message.user_id,
                "username": created_message.username,
            },
        }

        # 如果有臨時 ID，添加到回應中
        if temp_id:
            message_payload["temp_id"] = temp_id

        await connection_manager.broadcast_message(
            room_id, message_payload, None
        )  # 不排除任何用戶，確保發送者也能看到自己的訊息

        # 發送通知給房間內的其他成員
        try:
            # 獲取房間服務和通知服務
            room_service = await container.get(RoomService, scope_id)
            notification_service = await container.get(NotificationService, scope_id)

            # 獲取房間成員列表
            room_members = await room_service.get_room_members(room_id)

            # 獲取房間信息（用於通知標題）
            room_info = await room_service.get_room_by_id(room_id)
            room_name = room_info.name if room_info else f"房間 {room_id}"

            # 為每個成員（除發送者外）創建通知
            for member in room_members:
                if member.id != user_id:  # 不給自己發送通知
                    # 創建訊息預覽（限制長度）
                    message_preview = created_message.content
                    if len(message_preview) > 50:
                        message_preview = message_preview[:50] + "..."

                    # 發送訊息通知，包含訊息 ID 以便點擊通知時定位
                    await notification_service.send_message_notification(
                        user_id=member.id,
                        sender_name=created_message.username,
                        message_preview=message_preview,
                        room_name=room_name,
                        room_id=room_id,
                        sender_id=user_id,
                        message_id=created_message.id,
                    )

            logger.info(
                f"Notifications sent to {len([m for m in room_members if m.id != user_id])} members"
            )
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            # 通知失敗不影響訊息發送的主要邏輯

        logger.info(f"Message saved and broadcasted: {user_id} -> {room_id}")

    except Exception as e:
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
    await connection_manager.send_personal_message(
        user_id,
        room_id,
        {
            "type": "room_users",
            "users": users,
            "timestamp": datetime.now(UTC).isoformat(),
            "room_id": room_id,
        },
    )


async def handle_notification_read(
    user_id: str,
    room_id: str,
    message_data: dict,
    user_info: dict,
    scope_id: str = None,
):
    """
    處理通知已讀狀態變更

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID
        message_data: 訊息資料
        user_info: 使用者資訊
        scope_id: 作用域 ID
    """
    try:
        # 獲取請求數據
        notification_id = message_data.get("notification_id")
        read_type = message_data.get(
            "read_type", "notification"
        )  # 'notification' | 'room'
        target_room_id = message_data.get("target_room_id", room_id)  # 目標房間ID

        # 獲取服務
        container = get_container()
        notification_service = await container.get(NotificationService, scope_id)

        success = False

        if read_type == "notification" and notification_id:
            # 標記單個通知為已讀
            success = await notification_service.mark_as_read(notification_id, user_id)
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
            except Exception as e:
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

            # 發送到用戶的所有活動連接（跨房間）
            await connection_manager.send_notification(
                user_id, status_change_data["data"]
            )

            logger.info(
                f"Broadcasted read status change to all connections for user {user_id}"
            )

    except Exception as e:
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
        container = get_container()
        message_service = await container.get(MessageService)

        # 獲取最近的訊息
        messages = await message_service.get_room_messages(
            room_id=room_id, skip=0, limit=limit
        )

        # 格式化訊息
        formatted_messages = []
        for msg in messages:
            formatted_messages.append(
                {
                    "id": msg.id,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "status": msg.status,
                    "timestamp": msg.created_at,
                    "user": {"id": msg.user_id, "username": msg.username},
                }
            )

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

    except Exception as e:
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
