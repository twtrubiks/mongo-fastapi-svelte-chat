"""核心異常類別的測試"""
import pytest
from app.core.exceptions import (
    BaseCustomException,
    BusinessLogicError,
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    ForbiddenError,
    ConflictError,
    DatabaseError,
    CacheError,
    ExternalServiceError,
    ConfigurationError,
    RateLimitError
)


class TestBaseCustomException:
    """測試 BaseCustomException"""
    
    def test_base_exception_with_message_only(self):
        """測試只有訊息的基礎異常"""
        exception = BaseCustomException("Test error message")
        
        assert exception.message == "Test error message"
        assert exception.details == {}
        assert str(exception) == "Test error message"
    
    def test_base_exception_with_message_and_details(self):
        """測試有訊息和詳細資訊的基礎異常"""
        details = {"error_code": "E001", "field": "username"}
        exception = BaseCustomException("Validation failed", details)
        
        assert exception.message == "Validation failed"
        assert exception.details == details
        assert exception.details["error_code"] == "E001"
        assert exception.details["field"] == "username"
        assert str(exception) == "Validation failed"


class TestSpecificExceptions:
    """測試特定的異常類別"""
    
    def test_business_logic_error(self):
        """測試業務邏輯錯誤"""
        exception = BusinessLogicError("Business rule violated", {"rule": "max_limit"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Business rule violated"
        assert exception.details["rule"] == "max_limit"
    
    def test_validation_error(self):
        """測試驗證錯誤"""
        exception = ValidationError("Invalid input", {"field": "email", "value": "invalid"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Invalid input"
        assert exception.details["field"] == "email"
        assert exception.details["value"] == "invalid"
    
    def test_not_found_error(self):
        """測試資源不存在錯誤"""
        exception = NotFoundError("User not found", {"user_id": "123"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "User not found"
        assert exception.details["user_id"] == "123"
    
    def test_unauthorized_error(self):
        """測試未授權錯誤"""
        exception = UnauthorizedError("Invalid token")
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Invalid token"
        assert exception.details == {}
    
    def test_forbidden_error(self):
        """測試禁止存取錯誤"""
        exception = ForbiddenError("Access denied", {"resource": "admin_panel"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Access denied"
        assert exception.details["resource"] == "admin_panel"
    
    def test_conflict_error(self):
        """測試資源衝突錯誤"""
        exception = ConflictError("Resource already exists", {"resource_id": "456"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Resource already exists"
        assert exception.details["resource_id"] == "456"
    
    def test_database_error(self):
        """測試資料庫錯誤"""
        exception = DatabaseError("Connection failed", {"host": "localhost", "port": 27017})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Connection failed"
        assert exception.details["host"] == "localhost"
        assert exception.details["port"] == 27017
    
    def test_cache_error(self):
        """測試快取錯誤"""
        exception = CacheError("Cache miss", {"key": "user:123"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Cache miss"
        assert exception.details["key"] == "user:123"
    
    def test_external_service_error(self):
        """測試外部服務錯誤"""
        exception = ExternalServiceError("API timeout", {"service": "payment", "timeout": 30})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "API timeout"
        assert exception.details["service"] == "payment"
        assert exception.details["timeout"] == 30
    
    def test_configuration_error(self):
        """測試配置錯誤"""
        exception = ConfigurationError("Missing config", {"key": "DATABASE_URL"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Missing config"
        assert exception.details["key"] == "DATABASE_URL"
    
    def test_rate_limit_error(self):
        """測試速率限制錯誤"""
        exception = RateLimitError("Too many requests", {"limit": 100, "window": "1min"})
        
        assert isinstance(exception, BaseCustomException)
        assert exception.message == "Too many requests"
        assert exception.details["limit"] == 100
        assert exception.details["window"] == "1min"


class TestExceptionInheritance:
    """測試異常繼承關係"""
    
    def test_all_exceptions_inherit_from_base(self):
        """測試所有異常都繼承自基礎異常"""
        exception_classes = [
            BusinessLogicError,
            ValidationError,
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ConflictError,
            DatabaseError,
            CacheError,
            ExternalServiceError,
            ConfigurationError,
            RateLimitError
        ]
        
        for exc_class in exception_classes:
            exception = exc_class("Test message")
            assert isinstance(exception, BaseCustomException)
            assert isinstance(exception, Exception)
    
    def test_exception_can_be_raised_and_caught(self):
        """測試異常可以被拋出和捕獲"""
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Invalid data", {"field": "age", "min": 0})
        
        assert exc_info.value.message == "Invalid data"
        assert exc_info.value.details["field"] == "age"
        assert exc_info.value.details["min"] == 0