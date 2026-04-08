"""認證與授權相關的依賴注入"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_handler import decode_access_token
from app.core.fastapi_integration import create_room_repository
from app.models.enums import RoomType
from app.models.user import TokenData
from app.repositories.room_repository import RoomRepository
from app.utils.user_cache import fetch_user_with_cache

security = HTTPBearer()


async def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """
    從 JWT token 中獲取當前使用者資訊

    Args:
        credentials: HTTP Bearer 認證憑證

    Returns:
        TokenData: Token 資料

    Raises:
        HTTPException: 認證失敗時拋出 401 錯誤
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的認證憑證",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username: str = payload.get("sub")
    user_id: str = payload.get("user_id")

    if username is None or user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無效的認證憑證",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenData(username=username, user_id=user_id)


async def get_current_user(token_data: TokenData = Depends(get_current_user_token)):
    """
    獲取當前登入的使用者

    透過 fetch_user_with_cache 統一 cache-first 邏輯（與 WebSocket auth 共用）。

    Raises:
        HTTPException: 使用者不存在時拋出 404 錯誤
    """
    user = await fetch_user_with_cache(token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="使用者不存在"
        )
    return user


async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """
    獲取當前活躍的使用者

    Args:
        current_user: 當前使用者

    Returns:
        dict: 使用者資料

    Raises:
        HTTPException: 使用者未啟用時拋出 400 錯誤
    """
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="使用者已停用"
        )
    return current_user


async def require_room_membership(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_repo: RoomRepository = Depends(create_room_repository),
) -> dict:
    """檢查使用者是否為房間成員，非成員依房間類型回 403 或 404"""
    room = await room_repo.get_by_id(room_id)

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="聊天室不存在"
        )

    user_id = current_user["_id"]
    if user_id not in room.members:
        # PRIVATE 房間不洩漏存在性
        if room.room_type == RoomType.PRIVATE:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="聊天室不存在"
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="您不是該聊天室的成員"
        )

    return current_user
