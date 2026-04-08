"""WebSocket Ticket 管理模組

前端無法直接取得 JWT token（httpOnly cookie），
因此透過 BFF 取得一次性短效 ticket 來認證 WebSocket 連線。
"""

import json
import logging
import secrets

from app.database.redis_conn import get_redis

logger = logging.getLogger(__name__)

WS_TICKET_PREFIX = "ws_ticket:"
WS_TICKET_TTL = 30  # 30 秒


async def create_ws_ticket(user_id: str, room_id: str) -> str:
    """
    建立一次性 WebSocket 連線 ticket

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID

    Returns:
        str: ticket ID
    """
    redis_client = await get_redis()
    ticket = secrets.token_urlsafe(32)
    key = f"{WS_TICKET_PREFIX}{ticket}"
    data = json.dumps({"user_id": user_id, "room_id": room_id})
    await redis_client.setex(key, WS_TICKET_TTL, data)
    logger.debug(f"Created WS ticket for user {user_id} in room {room_id}")
    return ticket


async def validate_ws_ticket(ticket: str, room_id: str) -> str | None:
    """
    驗證並消費一次性 WebSocket ticket

    使用 getdel 原子操作確保 ticket 只能使用一次。

    Args:
        ticket: ticket ID
        room_id: 預期的房間 ID

    Returns:
        Optional[str]: 使用者 ID，驗證失敗則返回 None
    """
    redis_client = await get_redis()
    key = f"{WS_TICKET_PREFIX}{ticket}"

    # 原子性取出並刪除（一次性使用）
    data = await redis_client.getdel(key)
    if not data:
        logger.warning("WS ticket not found or already consumed")
        return None

    try:
        payload = json.loads(data)
        if payload.get("room_id") != room_id:
            logger.warning(
                f"WS ticket room_id mismatch: expected {room_id}, "
                f"got {payload.get('room_id')}"
            )
            return None
        return payload.get("user_id")
    except (json.JSONDecodeError, KeyError):
        logger.warning("WS ticket payload decode failed")
        return None
