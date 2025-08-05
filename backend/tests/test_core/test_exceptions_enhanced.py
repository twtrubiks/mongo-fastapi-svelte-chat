"""Core Exceptions 增強測試 - 提升覆蓋率"""
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


@pytest.mark.unit
class TestCoreExceptionsEnhanced:
    """Core Exceptions 增強測試類別"""
    
    def test_base_custom_exception_basic(self):
        """測試基礎自定義異常"""
        message = "Base exception message"
        exception = BaseCustomException(message)
        
        assert str(exception) == message
        assert exception.message == message
        assert exception.details == {}
        assert isinstance(exception, Exception)
    
    def test_base_custom_exception_with_details(self):
        """測試帶詳細資訊的基礎異常"""
        message = "Exception with details"
        details = {"error_code": "E001", "field": "username"}
        
        exception = BaseCustomException(message, details)
        
        assert str(exception) == message
        assert exception.message == message
        assert exception.details == details
    
    def test_base_custom_exception_none_details(self):
        """測試 None 詳細資訊處理"""
        message = "Exception with None details"
        exception = BaseCustomException(message, None)
        
        assert exception.details == {}
    
    def test_business_logic_error(self):
        """測試業務邏輯錯誤"""
        message = "Business rule violation"
        details = {"rule": "user_limit_exceeded", "current": 100, "max": 50}
        
        error = BusinessLogicError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_validation_error(self):
        """測試驗證錯誤"""
        message = "Validation failed"
        details = {
            "field_errors": {
                "email": "Invalid email format",
                "password": "Password too short"
            }
        }
        
        error = ValidationError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_not_found_error(self):
        """測試資源不存在錯誤"""
        message = "User not found"
        details = {"resource": "User", "id": "123", "query": {"username": "test"}}
        
        error = NotFoundError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_unauthorized_error(self):
        """測試未授權錯誤"""
        message = "Authentication required"
        details = {"reason": "invalid_token", "token_type": "Bearer"}
        
        error = UnauthorizedError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_forbidden_error(self):
        """測試禁止存取錯誤"""
        message = "Access denied"
        details = {"required_role": "admin", "user_role": "user", "resource": "admin_panel"}
        
        error = ForbiddenError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_conflict_error(self):
        """測試資源衝突錯誤"""
        message = "Resource already exists"
        details = {"field": "email", "value": "test@example.com", "existing_id": "456"}
        
        error = ConflictError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_database_error(self):
        """測試資料庫錯誤"""
        message = "Database connection failed"
        details = {"host": "localhost", "port": 27017, "database": "test_db", "error_code": "CONNECTION_TIMEOUT"}
        
        error = DatabaseError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_cache_error(self):
        """測試快取錯誤"""
        message = "Redis connection lost"
        details = {"cache_type": "redis", "operation": "set", "key": "user:123"}
        
        error = CacheError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_external_service_error(self):
        """測試外部服務錯誤"""
        message = "Payment service unavailable"
        details = {"service": "stripe", "endpoint": "/charges", "status_code": 503}
        
        error = ExternalServiceError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_configuration_error(self):
        """測試配置錯誤"""
        message = "Missing required configuration"
        details = {"config_key": "JWT_SECRET", "config_file": "settings.py"}
        
        error = ConfigurationError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_rate_limit_error(self):
        """測試速率限制錯誤"""
        message = "Rate limit exceeded"
        details = {"limit": 100, "window": 3600, "remaining": 0, "retry_after": 300}
        
        error = RateLimitError(message, details)
        
        assert isinstance(error, BaseCustomException)
        assert str(error) == message
        assert error.details == details
    
    def test_exception_inheritance_chain(self):
        """測試異常繼承鏈"""
        exceptions = [
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
        
        for exc_class in exceptions:
            assert issubclass(exc_class, BaseCustomException)
            assert issubclass(exc_class, Exception)
    
    def test_exceptions_with_empty_message(self):
        """測試空訊息的異常"""
        exceptions = [
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
        
        for exc_class in exceptions:
            error = exc_class("")
            assert str(error) == ""
            assert error.message == ""
            assert error.details == {}
    
    def test_exceptions_with_complex_details(self):
        """測試複雜詳細資訊的異常"""
        complex_details = {
            "nested": {
                "level1": {
                    "level2": "deep_value"
                }
            },
            "list": [1, 2, 3, "string"],
            "boolean": True,
            "null_value": None,
            "number": 42.5
        }
        
        error = ValidationError("Complex validation error", complex_details)
        
        assert error.details == complex_details
        assert error.details["nested"]["level1"]["level2"] == "deep_value"
        assert error.details["list"] == [1, 2, 3, "string"]
        assert error.details["boolean"] is True
        assert error.details["null_value"] is None
        assert error.details["number"] == 42.5
    
    def test_exception_args_attribute(self):
        """測試異常的 args 屬性"""
        message = "Test exception message"
        error = BaseCustomException(message)
        
        assert error.args == (message,)
        assert len(error.args) == 1
        assert error.args[0] == message
    
    def test_exception_chaining(self):
        """測試異常鏈結"""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise DatabaseError("Database operation failed") from e
        except DatabaseError as db_error:
            assert isinstance(db_error, DatabaseError)
            assert isinstance(db_error, BaseCustomException)
            assert str(db_error) == "Database operation failed"
            
            # 檢查異常鏈結
            assert db_error.__cause__ is not None
            assert isinstance(db_error.__cause__, ValueError)
            assert str(db_error.__cause__) == "Original error"
    
    def test_exception_context_manager(self):
        """測試在上下文管理器中使用異常"""
        def risky_operation():
            raise DatabaseError("Connection failed", {"host": "localhost"})
        
        with pytest.raises(DatabaseError) as exc_info:
            risky_operation()
        
        error = exc_info.value
        assert isinstance(error, DatabaseError)
        assert str(error) == "Connection failed"
        assert error.details == {"host": "localhost"}
    
    def test_multiple_inheritance_scenario(self):
        """測試多重繼承場景（如果適用）"""
        # 測試異常是否正確支援多重繼承模式
        error = ValidationError("Multi-inheritance test")
        
        # 檢查 MRO (Method Resolution Order)
        mro = ValidationError.__mro__
        assert BaseCustomException in mro
        assert Exception in mro
        assert object in mro
    
    def test_exception_repr(self):
        """測試異常的字串表示"""
        message = "Test exception for repr"
        details = {"key": "value"}
        error = BusinessLogicError(message, details)
        
        # 檢查基本的字串表示
        error_str = str(error)
        assert error_str == message
        
        # 檢查 repr（如果有自定義實現）
        error_repr = repr(error)
        assert isinstance(error_repr, str)
        assert len(error_repr) > 0