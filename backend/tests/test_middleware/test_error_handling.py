"""錯誤處理中間件的測試"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class TestErrorHandlingMiddleware:
    """測試錯誤處理中間件"""

    def test_http_exception_handler(self):
        """測試 HTTP 異常處理"""

        # Mock 錯誤處理器
        class HTTPExceptionHandler:
            def __init__(self):
                self.logger = Mock()

            def handle_http_exception(self, request, exc):
                # 記錄錯誤
                self.logger.error(f"HTTP {exc.status_code}: {exc.detail}")

                # 返回格式化的錯誤響應
                return JSONResponse(
                    status_code=exc.status_code,
                    content={
                        "error": True,
                        "code": exc.status_code,
                        "message": exc.detail,
                        "path": request.url.path,
                    },
                )

        # 設置測試
        handler = HTTPExceptionHandler()
        mock_request = Mock()
        mock_request.url.path = "/api/test"

        # 測試 404 錯誤
        exc_404 = HTTPException(status_code=404, detail="Resource not found")
        response = handler.handle_http_exception(mock_request, exc_404)

        assert response.status_code == 404
        content = json.loads(response.body)
        assert content["error"] is True
        assert content["code"] == 404
        assert content["message"] == "Resource not found"
        assert content["path"] == "/api/test"

        # 驗證日誌
        handler.logger.error.assert_called_with("HTTP 404: Resource not found")

    def test_validation_error_handler(self):
        """測試驗證錯誤處理"""
        from pydantic import BaseModel, ValidationError

        # Mock 驗證錯誤處理器
        class ValidationErrorHandler:
            def __init__(self):
                self.logger = Mock()

            def handle_validation_error(self, request, exc):
                # 解析驗證錯誤
                errors = []
                for error in exc.errors():
                    errors.append(
                        {
                            "field": ".".join(str(x) for x in error["loc"]),
                            "message": error["msg"],
                            "type": error["type"],
                        }
                    )

                # 記錄錯誤
                self.logger.warning(f"Validation error: {len(errors)} errors")

                return JSONResponse(
                    status_code=422,
                    content={
                        "error": True,
                        "code": 422,
                        "message": "Validation failed",
                        "errors": errors,
                    },
                )

        # 創建測試模型
        class TestModel(BaseModel):
            name: str
            age: int

        # 設置測試
        handler = ValidationErrorHandler()
        mock_request = Mock()

        # 觸發驗證錯誤
        try:
            TestModel(name="test", age="not_a_number")
        except ValidationError as e:
            response = handler.handle_validation_error(mock_request, e)

        # 驗證響應
        assert response.status_code == 422
        content = json.loads(response.body)
        assert content["error"] is True
        assert content["message"] == "Validation failed"
        assert len(content["errors"]) > 0

        # 驗證日誌
        handler.logger.warning.assert_called()

    def test_general_exception_handler(self):
        """測試一般異常處理"""

        # Mock 通用錯誤處理器
        class GeneralExceptionHandler:
            def __init__(self):
                self.logger = Mock()
                self.sentry = Mock()

            def handle_exception(self, request, exc):
                # 記錄詳細錯誤
                self.logger.error(
                    f"Unhandled exception: {type(exc).__name__}", exc_info=exc
                )

                # 發送到 Sentry
                self.sentry.capture_exception(exc)

                # 返回通用錯誤響應
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": True,
                        "code": 500,
                        "message": "Internal server error",
                        "request_id": request.state.request_id,
                    },
                )

        # 設置測試
        handler = GeneralExceptionHandler()
        mock_request = Mock()
        mock_request.state.request_id = "req-123"

        # 測試異常
        exc = ValueError("Something went wrong")
        response = handler.handle_exception(mock_request, exc)

        # 驗證響應
        assert response.status_code == 500
        content = json.loads(response.body)
        assert content["error"] is True
        assert content["message"] == "Internal server error"
        assert content["request_id"] == "req-123"

        # 驗證錯誤追蹤
        handler.logger.error.assert_called()
        handler.sentry.capture_exception.assert_called_once_with(exc)

    def test_custom_business_error_handler(self):
        """測試自定義業務錯誤處理"""

        # 定義業務錯誤
        class BusinessError(Exception):
            def __init__(self, code, message, details=None):
                self.code = code
                self.message = message
                self.details = details
                super().__init__(message)

        class BusinessErrorHandler:
            def __init__(self):
                self.logger = Mock()

            def handle_business_error(self, request, exc):
                # 記錄業務錯誤
                self.logger.info(f"Business error {exc.code}: {exc.message}")

                # 返回業務錯誤響應
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": True,
                        "code": exc.code,
                        "message": exc.message,
                        "details": exc.details,
                    },
                )

        # 設置測試
        handler = BusinessErrorHandler()
        mock_request = Mock()

        # 測試業務錯誤
        exc = BusinessError(
            code="USER_NOT_FOUND",
            message="User does not exist",
            details={"user_id": "123"},
        )
        response = handler.handle_business_error(mock_request, exc)

        # 驗證響應
        assert response.status_code == 400
        content = json.loads(response.body)
        assert content["code"] == "USER_NOT_FOUND"
        assert content["message"] == "User does not exist"
        assert content["details"]["user_id"] == "123"

    def test_rate_limit_error_handler(self):
        """測試速率限制錯誤處理"""

        # Mock 速率限制錯誤處理器
        class RateLimitHandler:
            def __init__(self):
                self.logger = Mock()

            def handle_rate_limit(self, request, exc):
                # 獲取限制信息
                retry_after = getattr(exc, "retry_after", 60)

                # 記錄
                self.logger.warning(f"Rate limit exceeded for {request.client.host}")

                # 返回 429 響應
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": True,
                        "code": 429,
                        "message": "Too many requests",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": "100",
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": "1234567890",
                    },
                )

        # 設置測試
        handler = RateLimitHandler()
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"

        # Mock 速率限制異常
        mock_exc = Mock()
        mock_exc.retry_after = 30

        # 處理錯誤
        response = handler.handle_rate_limit(mock_request, mock_exc)

        # 驗證響應
        assert response.status_code == 429
        content = json.loads(response.body)
        assert content["message"] == "Too many requests"
        assert content["retry_after"] == 30

        # 驗證標頭
        assert response.headers["Retry-After"] == "30"
        assert response.headers["X-RateLimit-Remaining"] == "0"

    def test_database_error_handler(self):
        """測試資料庫錯誤處理"""

        # Mock 資料庫錯誤處理器
        class DatabaseErrorHandler:
            def __init__(self):
                self.logger = Mock()
                self.metrics = Mock()

            def handle_database_error(self, request, exc):
                # 記錄錯誤
                self.logger.error(
                    f"Database error: {exc}",
                    extra={"request_id": request.state.request_id},
                )

                # 更新指標
                self.metrics.increment("database.errors")

                # 判斷錯誤類型
                if "connection" in str(exc).lower():
                    message = "Database connection error"
                    code = "DB_CONNECTION_ERROR"
                elif "timeout" in str(exc).lower():
                    message = "Database operation timeout"
                    code = "DB_TIMEOUT"
                else:
                    message = "Database error occurred"
                    code = "DB_ERROR"

                return JSONResponse(
                    status_code=503,
                    content={
                        "error": True,
                        "code": code,
                        "message": message,
                        "request_id": request.state.request_id,
                    },
                )

        # 設置測試
        handler = DatabaseErrorHandler()
        mock_request = Mock()
        mock_request.state.request_id = "req-456"

        # 測試連接錯誤
        exc = Exception("Database connection failed")
        response = handler.handle_database_error(mock_request, exc)

        # 驗證響應
        assert response.status_code == 503
        content = json.loads(response.body)
        assert content["code"] == "DB_CONNECTION_ERROR"
        assert content["message"] == "Database connection error"

        # 驗證指標
        handler.metrics.increment.assert_called_with("database.errors")

    def test_authentication_error_handler(self):
        """測試認證錯誤處理"""

        # Mock 認證錯誤處理器
        class AuthErrorHandler:
            def __init__(self):
                self.logger = Mock()

            def handle_auth_error(self, request, exc):
                # 記錄認證失敗
                self.logger.warning(
                    f"Authentication failed: {exc}",
                    extra={"ip": request.client.host, "path": request.url.path},
                )

                # 判斷錯誤類型
                if hasattr(exc, "expired") and exc.expired:
                    message = "Token has expired"
                    code = "TOKEN_EXPIRED"
                elif hasattr(exc, "invalid") and exc.invalid:
                    message = "Invalid token"
                    code = "INVALID_TOKEN"
                else:
                    message = "Authentication required"
                    code = "AUTH_REQUIRED"

                return JSONResponse(
                    status_code=401,
                    content={"error": True, "code": code, "message": message},
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # 設置測試
        handler = AuthErrorHandler()
        mock_request = Mock()
        mock_request.client.host = "192.168.1.1"
        mock_request.url.path = "/api/protected"

        # 測試過期令牌
        mock_exc = Mock()
        mock_exc.expired = True
        response = handler.handle_auth_error(mock_request, mock_exc)

        # 驗證響應
        assert response.status_code == 401
        content = json.loads(response.body)
        assert content["code"] == "TOKEN_EXPIRED"
        assert content["message"] == "Token has expired"
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_file_upload_error_handler(self):
        """測試文件上傳錯誤處理"""

        # Mock 文件錯誤處理器
        class FileUploadErrorHandler:
            def __init__(self):
                self.logger = Mock()

            def handle_file_error(self, request, exc):
                # 解析錯誤類型
                error_map = {
                    "size": ("FILE_TOO_LARGE", "File size exceeds limit"),
                    "type": ("INVALID_FILE_TYPE", "File type not allowed"),
                    "virus": ("MALWARE_DETECTED", "File contains malware"),
                    "corrupt": ("FILE_CORRUPTED", "File is corrupted"),
                }

                # 獲取錯誤信息
                error_type = getattr(exc, "error_type", "unknown")
                code, message = error_map.get(
                    error_type, ("FILE_ERROR", "File upload error")
                )

                # 記錄
                self.logger.error(f"File upload error: {code} - {message}")

                return JSONResponse(
                    status_code=400,
                    content={
                        "error": True,
                        "code": code,
                        "message": message,
                        "max_size": "10MB",
                        "allowed_types": ["jpg", "png", "pdf"],
                    },
                )

        # 設置測試
        handler = FileUploadErrorHandler()
        mock_request = Mock()

        # 測試文件過大錯誤
        mock_exc = Mock()
        mock_exc.error_type = "size"
        response = handler.handle_file_error(mock_request, mock_exc)

        # 驗證響應
        assert response.status_code == 400
        content = json.loads(response.body)
        assert content["code"] == "FILE_TOO_LARGE"
        assert content["message"] == "File size exceeds limit"
        assert content["max_size"] == "10MB"

    def test_concurrent_modification_error_handler(self):
        """測試並發修改錯誤處理"""

        # Mock 並發錯誤處理器
        class ConcurrentModificationHandler:
            def __init__(self):
                self.logger = Mock()

            def handle_concurrent_error(self, request, exc):
                # 記錄並發衝突
                self.logger.warning(
                    "Concurrent modification detected",
                    extra={
                        "resource": getattr(exc, "resource", "unknown"),
                        "version": getattr(exc, "version", "unknown"),
                    },
                )

                return JSONResponse(
                    status_code=409,
                    content={
                        "error": True,
                        "code": "CONCURRENT_MODIFICATION",
                        "message": "Resource was modified by another user",
                        "current_version": getattr(exc, "current_version", None),
                        "your_version": getattr(exc, "your_version", None),
                    },
                )

        # 設置測試
        handler = ConcurrentModificationHandler()
        mock_request = Mock()

        # Mock 並發錯誤
        mock_exc = Mock()
        mock_exc.resource = "document_123"
        mock_exc.current_version = 5
        mock_exc.your_version = 3

        response = handler.handle_concurrent_error(mock_request, mock_exc)

        # 驗證響應
        assert response.status_code == 409
        content = json.loads(response.body)
        assert content["code"] == "CONCURRENT_MODIFICATION"
        assert content["current_version"] == 5
        assert content["your_version"] == 3

    @pytest.mark.asyncio
    async def test_async_middleware_chain(self):
        """測試異步中間件鏈"""

        # Mock 異步中間件
        class AsyncErrorMiddleware:
            def __init__(self):
                self.logger = Mock()
                self.handlers = []

            async def __call__(self, request, call_next):
                try:
                    # 調用下一個中間件
                    response = await call_next(request)
                    return response
                except Exception as exc:
                    # 處理錯誤
                    for handler in self.handlers:
                        if handler.can_handle(exc):
                            return await handler.handle(request, exc)

                    # 默認處理
                    self.logger.error(f"Unhandled error: {exc}")
                    return JSONResponse(
                        status_code=500, content={"error": "Internal server error"}
                    )

        # Mock handler
        mock_handler = Mock()
        mock_handler.can_handle.return_value = True
        mock_handler.handle = AsyncMock(
            return_value=JSONResponse(status_code=400, content={"error": "Handled"})
        )

        # 設置測試
        middleware = AsyncErrorMiddleware()
        middleware.handlers.append(mock_handler)

        # Mock call_next 拋出異常
        async def failing_call_next(request):
            raise ValueError("Test error")

        # 執行中間件
        mock_request = Mock()
        response = await middleware(mock_request, failing_call_next)

        # 驗證
        assert response.status_code == 400
        content = json.loads(response.body)
        assert content["error"] == "Handled"
        mock_handler.handle.assert_called_once()

    def test_error_response_formatting(self):
        """測試錯誤響應格式化"""

        # Mock 響應格式化器
        class ErrorResponseFormatter:
            def __init__(self, debug=False):
                self.debug = debug

            def format_error(self, error_code, message, details=None, stack_trace=None):
                response = {
                    "error": True,
                    "code": error_code,
                    "message": message,
                    "timestamp": "2024-01-01T00:00:00Z",
                }

                if details:
                    response["details"] = details

                if self.debug and stack_trace:
                    response["stack_trace"] = stack_trace

                return response

        # 測試生產環境格式（無堆疊追蹤）
        formatter_prod = ErrorResponseFormatter(debug=False)
        response = formatter_prod.format_error(
            "VALIDATION_ERROR",
            "Invalid input",
            details={"field": "email"},
            stack_trace="traceback...",
        )

        assert response["code"] == "VALIDATION_ERROR"
        assert response["message"] == "Invalid input"
        assert response["details"]["field"] == "email"
        assert "stack_trace" not in response

        # 測試開發環境格式（含堆疊追蹤）
        formatter_dev = ErrorResponseFormatter(debug=True)
        response = formatter_dev.format_error(
            "INTERNAL_ERROR", "Something went wrong", stack_trace="traceback..."
        )

        assert response["stack_trace"] == "traceback..."


class TestGlobalErrorHandlerAdditional:
    """針對 GlobalErrorHandler 的額外測試用於提升覆蓋率"""

    @pytest.fixture
    def app_database_errors(self):
        """創建測試資料庫錯誤的應用"""
        from fastapi import FastAPI
        from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError

        from app.middleware.error_handler import GlobalErrorHandler

        app = FastAPI()
        app.add_middleware(GlobalErrorHandler, debug=True)

        @app.get("/test/duplicate-key")
        async def duplicate_key():
            raise DuplicateKeyError("E11000 duplicate key")

        @app.get("/test/bulk-write-error")
        async def bulk_write_error():
            error = BulkWriteError(
                {
                    "writeErrors": [
                        {"index": 0, "code": 11000, "errmsg": "duplicate key"}
                    ]
                }
            )
            raise error

        @app.get("/test/pymongo-error")
        async def pymongo_error():
            raise PyMongoError("Database connection failed")

        return app

    @pytest.fixture
    def app_redis_errors(self):
        """創建測試 Redis 錯誤的應用"""
        from fastapi import FastAPI
        from redis.exceptions import ConnectionError as RedisConnectionError
        from redis.exceptions import RedisError

        from app.middleware.error_handler import GlobalErrorHandler

        app = FastAPI()
        app.add_middleware(GlobalErrorHandler, debug=True)

        @app.get("/test/redis-connection-error")
        async def redis_connection_error():
            raise RedisConnectionError("Connection to Redis failed")

        @app.get("/test/redis-error")
        async def redis_error():
            raise RedisError("Redis operation failed")

        return app

    @pytest.fixture
    def app_auth_errors(self):
        """創建測試認證錯誤的應用"""
        from fastapi import FastAPI

        from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
        from app.middleware.error_handler import GlobalErrorHandler

        app = FastAPI()
        app.add_middleware(GlobalErrorHandler, debug=True)

        @app.get("/test/unauthorized")
        async def unauthorized():
            raise UnauthorizedError("未授權訪問")

        @app.get("/test/forbidden")
        async def forbidden():
            raise ForbiddenError("禁止訪問")

        @app.get("/test/conflict")
        async def conflict():
            raise ConflictError("資源衝突")

        return app

    def test_duplicate_key_error(self, app_database_errors):
        """測試重複鍵錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_database_errors)
        response = client.get("/test/duplicate-key")

        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "DUPLICATE_KEY_ERROR"
        assert data["error"]["message"] == "資源重複，請檢查唯一性限制"
        assert "details" in data["error"]

    def test_bulk_write_error(self, app_database_errors):
        """測試批量寫入錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_database_errors)
        response = client.get("/test/bulk-write-error")

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "BULK_WRITE_ERROR"
        assert data["error"]["message"] == "批量寫入操作失敗"
        assert "details" in data["error"]
        assert "write_errors" in data["error"]["details"]

    def test_pymongo_error(self, app_database_errors):
        """測試 PyMongo 錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_database_errors)
        response = client.get("/test/pymongo-error")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "DATABASE_ERROR"
        assert data["error"]["message"] == "資料庫操作失敗"
        # 在 debug 模式下應該有詳細信息
        assert "details" in data["error"]

    def test_redis_connection_error(self, app_redis_errors):
        """測試 Redis 連接錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_redis_errors)
        response = client.get("/test/redis-connection-error")

        assert response.status_code == 503
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "CACHE_CONNECTION_ERROR"
        assert data["error"]["message"] == "快取服務連線失敗"
        # 在 debug 模式下應該有詳細信息
        assert "details" in data["error"]

    def test_redis_error(self, app_redis_errors):
        """測試 Redis 錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_redis_errors)
        response = client.get("/test/redis-error")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "CACHE_ERROR"
        assert data["error"]["message"] == "快取操作失敗"
        # 在 debug 模式下應該有詳細信息
        assert "details" in data["error"]

    def test_unauthorized_error(self, app_auth_errors):
        """測試未授權錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_auth_errors)
        response = client.get("/test/unauthorized")

        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert data["error"]["message"] == "未授權訪問"

    def test_forbidden_error(self, app_auth_errors):
        """測試禁止訪問錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_auth_errors)
        response = client.get("/test/forbidden")

        assert response.status_code == 403
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "FORBIDDEN"
        assert data["error"]["message"] == "禁止訪問"

    def test_conflict_error(self, app_auth_errors):
        """測試衝突錯誤處理"""
        from fastapi.testclient import TestClient

        client = TestClient(app_auth_errors)
        response = client.get("/test/conflict")

        assert response.status_code == 409
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "RESOURCE_CONFLICT"
        assert data["error"]["message"] == "資源衝突"

    @pytest.mark.asyncio
    async def test_client_ip_extraction(self):
        """測試客戶端 IP 提取邏輯"""
        from app.middleware.error_handler import GlobalErrorHandler

        handler = GlobalErrorHandler(app=None, debug=True)

        # 測試 x-forwarded-for 標頭
        request = Mock(spec=Request)
        request.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}

        ip = handler._get_client_ip(request)
        assert ip == "192.168.1.1"

        # 測試 x-real-ip 標頭
        request.headers = {"x-real-ip": "203.0.113.1"}
        ip = handler._get_client_ip(request)
        assert ip == "203.0.113.1"

        # 測試連線資訊
        request.headers = {}
        request.client = Mock()
        request.client.host = "198.51.100.1"

        ip = handler._get_client_ip(request)
        assert ip == "198.51.100.1"

        # 測試無法獲取 IP 的情況
        request.client = None
        ip = handler._get_client_ip(request)
        assert ip == "unknown"

    @pytest.mark.asyncio
    async def test_log_levels(self):
        """測試不同錯誤的日誌級別"""
        from app.middleware.error_handler import ErrorDetail, GlobalErrorHandler

        handler = GlobalErrorHandler(app=None, debug=True)

        request = Mock(spec=Request)
        request.method = "GET"
        request.url = "http://test.com/api"
        request.headers = {}
        request.client = None

        error_detail = ErrorDetail("TEST_ERROR", "Test message")

        with patch("app.middleware.error_handler.logger") as mock_logger:
            # 測試 5xx 錯誤 - error 級別
            await handler._log_error(request, Exception(), error_detail, 500)
            mock_logger.error.assert_called()

            # 測試 4xx 錯誤 - warning 級別
            await handler._log_error(request, Exception(), error_detail, 400)
            mock_logger.warning.assert_called()

            # 測試其他錯誤 - info 級別
            await handler._log_error(request, Exception(), error_detail, 200)
            mock_logger.info.assert_called()

    def test_create_error_handler_middleware_function(self):
        """測試便利函數"""
        from app.middleware.error_handler import (
            GlobalErrorHandler,
            create_error_handler_middleware,
        )

        handler = create_error_handler_middleware(debug=True)
        assert isinstance(handler, GlobalErrorHandler)
        assert handler.debug is True

        handler = create_error_handler_middleware(debug=False)
        assert handler.debug is False

    def test_error_detail_class(self):
        """測試 ErrorDetail 類別"""
        from app.middleware.error_handler import ErrorDetail

        detail = ErrorDetail("TEST_CODE", "Test message")
        assert detail.error_code == "TEST_CODE"
        assert detail.message == "Test message"
        assert detail.details == {}
        assert detail.timestamp is not None

        # 測試帶詳細信息的情況
        details = {"field": "value"}
        detail = ErrorDetail("TEST_CODE", "Test message", details)
        assert detail.details == details

    def test_non_debug_mode_error_details(self):
        """測試非 debug 模式下的錯誤詳情"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from pymongo.errors import PyMongoError

        from app.middleware.error_handler import GlobalErrorHandler

        app = FastAPI()
        app.add_middleware(GlobalErrorHandler, debug=False)  # 關閉 debug

        @app.get("/test/pymongo-error")
        async def pymongo_error():
            raise PyMongoError("Database error")

        client = TestClient(app)
        response = client.get("/test/pymongo-error")

        data = response.json()
        # 非 debug 模式下不應該有 details
        assert "details" not in data["error"] or data["error"]["details"] == {}

    def test_error_handler_internal_error(self):
        """測試錯誤處理器本身出錯的情況"""

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.middleware.error_handler import GlobalErrorHandler

        app = FastAPI()

        # 創建一個會在內部出錯的錯誤處理器
        class FaultyErrorHandler(GlobalErrorHandler):
            def _create_error_detail(self, exc):
                if isinstance(exc, ValueError) and str(exc) == "trigger_handler_error":
                    raise Exception("錯誤處理器內部錯誤")
                return super()._create_error_detail(exc)

        # 添加中間件
        app.add_middleware(FaultyErrorHandler, debug=True)

        @app.get("/test/handler-error")
        async def handler_error():
            raise ValueError("trigger_handler_error")

        client = TestClient(app)
        response = client.get("/test/handler-error")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert data["error"]["message"] == "伺服器內部錯誤"
        assert "timestamp" in data["error"]
