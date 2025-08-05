"""自定義異常類別"""
from typing import Dict, Any, Optional


class BaseCustomException(Exception):
    """自定義異常基礎類別"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class BusinessLogicError(BaseCustomException):
    """業務邏輯錯誤"""
    pass


class ValidationError(BaseCustomException):
    """驗證錯誤"""
    pass


class NotFoundError(BaseCustomException):
    """資源不存在錯誤"""
    pass


class UnauthorizedError(BaseCustomException):
    """未授權錯誤"""
    pass


class ForbiddenError(BaseCustomException):
    """禁止存取錯誤"""
    pass


class ConflictError(BaseCustomException):
    """資源衝突錯誤"""
    pass


class DatabaseError(BaseCustomException):
    """資料庫錯誤"""
    pass


class CacheError(BaseCustomException):
    """快取錯誤"""
    pass


class ExternalServiceError(BaseCustomException):
    """外部服務錯誤"""
    pass


class ConfigurationError(BaseCustomException):
    """配置錯誤"""
    pass


class RateLimitError(BaseCustomException):
    """速率限制錯誤"""
    pass