"""WebSocket 認證中介軟體"""

import logging
from typing import Any

from bson import ObjectId
from fastapi import WebSocket
from fastapi.security.utils import get_authorization_scheme_param

from app.auth.jwt_handler import decode_access_token
from app.core.exceptions import NotFoundError
from app.core.fastapi_integration import create_room_service
from app.utils.user_cache import fetch_user_with_cache
from app.utils.ws_ticket import validate_ws_ticket

logger = logging.getLogger(__name__)


async def _get_user_info(user_id: str) -> dict[str, Any] | None:
    """
    透過 user_id 查詢使用者資訊（與 HTTP auth 共用 cache-first 邏輯）

    Returns:
        WebSocket 所需的使用者資訊 dict，如果查無或未啟用則返回 None
    """
    try:
        user = await fetch_user_with_cache(user_id)
        if user is None:
            logger.warning(f"User {user_id} not found")
            return None

        if not user.get("is_active", True):
            logger.warning(f"User {user_id} is not active")
            return None

        return {
            "id": user["_id"],
            "username": user["username"],
            "email": user.get("email"),
            "full_name": user.get("full_name"),
            "avatar": user.get("avatar"),
            "is_active": user.get("is_active", True),
        }
    except Exception as e:  # intentional catch-all: 使用者查詢失敗回傳 None 拒絕連線
        logger.error(f"Error fetching user info for {user_id}: {e}")
        return None


async def authenticate_websocket(
    websocket: WebSocket, token: str
) -> dict[str, Any] | None:
    """
    驗證 WebSocket 連線的 JWT Token

    Args:
        websocket: WebSocket 連線物件
        token: JWT Token

    Returns:
        Optional[Dict[str, Any]]: 使用者資訊，如果驗證失敗則返回 None
    """
    try:
        # 解碼 JWT Token
        payload = decode_access_token(token)
        if not payload:
            logger.warning("Invalid JWT token in WebSocket connection")
            return None

        # 獲取使用者資訊
        user_id = payload.get("user_id")
        username = payload.get("sub")

        if not user_id or not username:
            logger.warning("Missing user_id or username in JWT token")
            return None

        return await _get_user_info(user_id)

    except Exception as e:  # intentional catch-all: 認證失敗回傳 None 拒絕連線
        logger.error(f"Error authenticating WebSocket connection: {e}")
        return None


async def authenticate_websocket_by_ticket(
    ticket: str, room_id: str
) -> dict[str, Any] | None:
    """
    透過一次性 ticket 驗證 WebSocket 連線

    Args:
        ticket: 一次性 ticket
        room_id: 房間 ID（用於驗證 ticket 是否匹配）

    Returns:
        Optional[Dict[str, Any]]: 使用者資訊，如果驗證失敗則返回 None
    """
    user_id = await validate_ws_ticket(ticket, room_id)
    if not user_id:
        logger.warning("Invalid or expired WS ticket")
        return None

    return await _get_user_info(user_id)


async def verify_room_membership(user_id: str, room_id: str) -> bool:
    """
    驗證使用者是否為房間成員（純驗證，不做自動加入）

    WS 連線只驗證成員資格，加入房間必須透過 HTTP API（經過完整的 join_policy 檢查）。

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID

    Returns:
        bool: 是否為房間成員
    """
    try:
        # 特殊處理 lobby 房間 - 所有登入用戶都可以連接
        if room_id == "lobby":
            logger.info(f"User {user_id} connecting to lobby")
            return True

        # 檢查房間 ID 格式
        if not ObjectId.is_valid(room_id):
            logger.warning(f"Invalid room ID format: {room_id}")
            return False

        # 使用 RoomService 獲取房間資訊
        room_service = await create_room_service()

        try:
            room = await room_service.get_room_by_id(room_id)
        except NotFoundError:
            logger.warning(f"Room {room_id} not found")
            return False

        # 統一檢查成員資格（不區分公開/私人房間）
        if user_id not in room.members:
            logger.warning(f"User {user_id} is not a member of room {room_id}")
            return False

        return True

    except Exception as e:  # intentional catch-all: 房間驗證失敗回傳 False 拒絕連線
        logger.error(f"Error verifying room membership: {e}")
        return False


def extract_token_from_query(websocket: WebSocket) -> str | None:
    """
    從 WebSocket 查詢參數中提取 JWT Token

    Args:
        websocket: WebSocket 連線物件

    Returns:
        Optional[str]: JWT Token，如果不存在則返回 None
    """
    # 從查詢參數中獲取 token
    token = websocket.query_params.get("token")

    if not token:
        # 也可以從 Authorization header 中獲取
        authorization = websocket.headers.get("Authorization")
        if authorization:
            scheme, token = get_authorization_scheme_param(authorization)
            if scheme.lower() != "bearer":
                return None

    return token


async def websocket_auth_middleware(
    websocket: WebSocket, room_id: str
) -> dict[str, Any] | None:
    """
    WebSocket 認證中介軟體

    優先使用一次性 ticket 認證（BFF httpOnly 模式），
    fallback 到 JWT token（向後相容，過渡期使用）。

    Args:
        websocket: WebSocket 連線物件
        room_id: 房間 ID

    Returns:
        Optional[Dict[str, Any]]: 使用者資訊，如果認證失敗則返回 None
    """
    try:
        user_info = None

        # 優先嘗試 ticket 認證（新模式）
        ticket = websocket.query_params.get("ticket")
        if ticket:
            user_info = await authenticate_websocket_by_ticket(ticket, room_id)
            if not user_info:
                logger.warning("WebSocket ticket authentication failed")
                return None
        else:
            # Fallback: JWT token（向後相容）
            token = extract_token_from_query(websocket)
            if not token:
                logger.warning("No ticket or token provided in WebSocket connection")
                return None

            user_info = await authenticate_websocket(websocket, token)
            if not user_info:
                logger.warning("WebSocket token authentication failed")
                return None

        # 驗證房間權限
        if not await verify_room_membership(user_info["id"], room_id):
            logger.warning(
                f"User {user_info['id']} has no permission to join room {room_id}"
            )
            return None

        logger.info(f"User {user_info['username']} authenticated for room {room_id}")
        return user_info

    except Exception as e:  # intentional catch-all: 認證中介軟體失敗回傳 None 拒絕連線
        logger.error(f"Error in WebSocket auth middleware: {e}")
        return None
