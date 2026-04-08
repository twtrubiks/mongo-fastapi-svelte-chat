"""JWT Token 處理模組"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt.exceptions import InvalidTokenError

from app.config import settings


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    創建 JWT access token

    Args:
        data: 要編碼的資料
        expires_delta: 過期時間間隔

    Returns:
        str: 編碼後的 JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    解碼 JWT access token

    Args:
        token: JWT token

    Returns:
        Optional[Dict[str, Any]]: 解碼後的資料，如果驗證失敗則返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        # 防止 refresh token 被當成 access token 使用
        if payload.get("type") == "refresh":
            return None
        return payload
    except InvalidTokenError:
        return None


def create_refresh_token(data: dict) -> str:
    """
    創建 JWT refresh token

    Args:
        data: 要編碼的資料

    Returns:
        str: 編碼後的 JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    """
    解碼 JWT refresh token

    Args:
        token: JWT refresh token

    Returns:
        Optional[Dict[str, Any]]: 解碼後的資料，如果驗證失敗或不是 refresh token 則返回 None
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        # 只接受 refresh 類型的 token
        if payload.get("type") != "refresh":
            return None
        return payload
    except InvalidTokenError:
        return None
