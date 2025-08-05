"""JWT Token 處理模組"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from jwt.exceptions import InvalidTokenError
from app.config import settings

# JWT 設定常數
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_EXPIRE_MINUTES

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
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
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解碼 JWT access token
    
    Args:
        token: JWT token
        
    Returns:
        Optional[Dict[str, Any]]: 解碼後的資料，如果驗證失敗則返回 None
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
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
    expire = datetime.now(timezone.utc) + timedelta(days=7)  # Refresh token 有效期 7 天
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt