"""認證相關的依賴注入"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt_handler import decode_access_token
from app.database.mongodb import get_database
from app.models.user import TokenData

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

    Args:
        token_data: Token 資料

    Returns:
        dict: 使用者資料

    Raises:
        HTTPException: 使用者不存在時拋出 404 錯誤
    """
    from bson import ObjectId

    db = await get_database()
    user = await db.users.find_one({"_id": ObjectId(token_data.user_id)})

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="使用者不存在"
        )

    # 將 ObjectId 轉換為字符串以符合 Pydantic 模型
    if user and "_id" in user:
        user["_id"] = str(user["_id"])

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


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """
    獲取可選的當前使用者（用於不強制要求登入的端點）

    Args:
        credentials: HTTP Bearer 認證憑證（可選）

    Returns:
        Optional[TokenData]: Token 資料或 None
    """
    if credentials is None:
        return None

    try:
        return get_current_user_token(credentials)
    except HTTPException:
        return None
