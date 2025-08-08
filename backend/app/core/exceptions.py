"""自定義異常類別"""

from typing import Any


class BaseCustomError(Exception):
    """自定義異常基礎類別"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class BusinessLogicError(BaseCustomError):
    """業務邏輯錯誤"""

    pass


class ValidationError(BaseCustomError):
    """驗證錯誤"""

    pass


class NotFoundError(BaseCustomError):
    """資源不存在錯誤"""

    pass


class UnauthorizedError(BaseCustomError):
    """未授權錯誤"""

    pass


class ForbiddenError(BaseCustomError):
    """禁止存取錯誤"""

    pass


class ConflictError(BaseCustomError):
    """資源衝突錯誤"""

    pass


class DatabaseError(BaseCustomError):
    """資料庫錯誤"""

    pass


class CacheError(BaseCustomError):
    """快取錯誤"""

    pass


class ExternalServiceError(BaseCustomError):
    """外部服務錯誤"""

    pass


class ConfigurationError(BaseCustomError):
    """配置錯誤"""

    pass


class RateLimitError(BaseCustomError):
    """速率限制錯誤"""

    pass
