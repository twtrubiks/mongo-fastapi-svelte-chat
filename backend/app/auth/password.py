"""密碼處理模組"""
from passlib.context import CryptContext
import asyncio

# 設定密碼加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    驗證明文密碼與雜湊密碼是否匹配
    
    Args:
        plain_password: 明文密碼
        hashed_password: 雜湊密碼
        
    Returns:
        bool: 密碼是否匹配
    """
    try:
        # 暫時使用同步方式來避免 bcrypt 版本相容性問題
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        # 記錄錯誤但不拋出異常，避免影響認證流程
        return False

async def get_password_hash(password: str) -> str:
    """
    將明文密碼轉換為雜湊密碼
    
    Args:
        password: 明文密碼
        
    Returns:
        str: 雜湊後的密碼
    """
    try:
        # 暫時使用同步方式來避免 bcrypt 版本相容性問題
        return pwd_context.hash(password)
    except Exception as e:
        # 記錄錯誤並拋出異常，因為密碼加密失敗是嚴重錯誤
        raise