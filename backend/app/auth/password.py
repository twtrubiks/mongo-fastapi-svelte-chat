"""密碼處理模組"""

import logging

import bcrypt

logger = logging.getLogger(__name__)


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
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError) as e:
        logger.error(f"密碼驗證失敗: {e}")
        return False


async def get_password_hash(password: str) -> str:
    """
    將明文密碼轉換為雜湊密碼

    Args:
        password: 明文密碼

    Returns:
        str: 雜湊後的密碼
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")
