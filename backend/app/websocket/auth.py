"""WebSocket 認證中介軟體"""

import logging
from typing import Any

from bson import ObjectId
from fastapi import WebSocket
from fastapi.security.utils import get_authorization_scheme_param

from app.auth.jwt_handler import decode_access_token
from app.core.container import get_container
from app.services.room_service import RoomService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


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

        # 使用 UserService 獲取使用者資訊
        container = get_container()
        user_service = await container.get(UserService)

        user = await user_service.get_user_by_id(user_id)

        if not user:
            logger.warning(f"User {user_id} not found in database")
            return None

        if not user.is_active:
            logger.warning(f"User {user_id} is not active")
            return None

        # 返回使用者資訊，確保 id 字段正確
        return {
            "id": user.id or user_id,  # 如果 user.id 為空，使用原始的 user_id
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "avatar": user.avatar,  # 添加頭像資訊
            "is_active": user.is_active,
        }

    except Exception as e:
        logger.error(f"Error authenticating WebSocket connection: {e}")
        return None


async def verify_room_membership(user_id: str, room_id: str) -> bool:
    """
    驗證使用者是否有權限加入該房間

    Args:
        user_id: 使用者 ID
        room_id: 房間 ID

    Returns:
        bool: 是否有權限
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
        container = get_container()
        room_service = await container.get(RoomService)

        room = await room_service.get_room_by_id(room_id)
        if not room:
            logger.warning(f"Room {room_id} not found")
            return False

        # 如果是公開房間，允許任何人加入
        if room.is_public:
            # 檢查用戶是否已經是房間成員
            if user_id not in room.members:
                # 檢查房間是否已滿
                current_members = len(room.members)
                max_members = room.max_members

                if current_members >= max_members:
                    logger.warning(f"Room {room_id} is full")
                    return False

                # 自動將使用者加入房間成員列表
                try:
                    await room_service.join_room(room_id, user_id)
                except Exception as e:
                    logger.error(f"Failed to add user {user_id} to room {room_id}: {e}")
                    return False

            return True

        # 私人房間需要檢查成員資格
        if user_id not in room.members:
            logger.warning(f"User {user_id} is not a member of room {room_id}")
            return False

        return True

    except Exception as e:
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

    Args:
        websocket: WebSocket 連線物件
        room_id: 房間 ID

    Returns:
        Optional[Dict[str, Any]]: 使用者資訊，如果認證失敗則返回 None
    """
    try:
        # 提取 JWT Token
        token = extract_token_from_query(websocket)
        if not token:
            logger.warning("No token provided in WebSocket connection")
            return None

        # 認證使用者
        user_info = await authenticate_websocket(websocket, token)
        if not user_info:
            logger.warning("WebSocket authentication failed")
            return None

        # 驗證房間權限
        if not await verify_room_membership(user_info["id"], room_id):
            logger.warning(
                f"User {user_info['id']} has no permission to join room {room_id}"
            )
            return None

        logger.info(f"User {user_info['username']} authenticated for room {room_id}")
        return user_info

    except Exception as e:
        logger.error(f"Error in WebSocket auth middleware: {e}")
        return None
