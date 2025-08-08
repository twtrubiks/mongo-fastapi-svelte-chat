"""安全標頭中間件測試"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.middleware.security_headers import (
    SecurityHeadersMiddleware,
    default_security_middleware,
    dev_security_middleware,
    prod_security_middleware,
)


@pytest.mark.unit
class TestSecurityHeadersMiddleware:
    """安全標頭中間件測試類別"""

    @pytest.fixture
    def security_middleware(self):
        """基本安全標頭中間件"""
        return SecurityHeadersMiddleware()

    @pytest.fixture
    def custom_middleware(self):
        """自訂設定的安全標頭中間件"""
        return SecurityHeadersMiddleware(
            enable_hsts=False,
            enable_csp=False,
            custom_headers={"X-Custom-Header": "test-value"},
        )

    @pytest.fixture
    def app_with_middleware(self, security_middleware):
        """帶有安全標頭中間件的測試應用"""
        app = FastAPI()

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            return await security_middleware(request, call_next)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        @app.get("/error")
        async def error_endpoint():
            raise Exception("Test error")

        return app

    @pytest.fixture
    def client(self, app_with_middleware):
        """測試客戶端"""
        return TestClient(app_with_middleware)

    def test_middleware_initialization(self, security_middleware):
        """測試中間件初始化"""
        # 檢查基本標頭是否正確設定
        headers = security_middleware.get_headers()

        assert "X-Content-Type-Options" in headers
        assert headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in headers
        assert headers["X-XSS-Protection"] == "1; mode=block"

        assert "Referrer-Policy" in headers
        assert "Permissions-Policy" in headers

        # 檢查 HSTS 標頭 (預設啟用)
        assert "Strict-Transport-Security" in headers

        # 檢查 CSP 標頭 (預設啟用)
        assert "Content-Security-Policy" in headers

    def test_custom_headers_initialization(self):
        """測試自訂標頭初始化"""
        custom_headers = {"X-Custom": "value", "X-Test": "test"}
        middleware = SecurityHeadersMiddleware(
            enable_hsts=False, custom_headers=custom_headers
        )

        headers = middleware.get_headers()
        assert headers["X-Custom"] == "value"
        assert headers["X-Test"] == "test"
        assert "Strict-Transport-Security" not in headers

    def test_basic_security_headers_added(self, client):
        """測試基本安全標頭是否添加到回應"""
        response = client.get("/test")

        assert response.status_code == 200

        # 檢查基本安全標頭
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

        # 檢查內容
        assert response.json() == {"message": "test"}

    def test_hsts_header_with_https(self):
        """測試 HTTPS 環境下的 HSTS 標頭"""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(enable_hsts=True)

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            return await middleware(request, call_next)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # 模擬 HTTPS 請求
        with TestClient(app, base_url="https://testserver") as client:
            response = client.get("/test")

            assert response.status_code == 200
            assert "Strict-Transport-Security" in response.headers
            assert "max-age=" in response.headers["Strict-Transport-Security"]

    def test_hsts_header_skipped_for_http(self):
        """測試 HTTP 環境下跳過 HSTS 標頭"""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(enable_hsts=True)

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            return await middleware(request, call_next)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        # 模擬 HTTP 請求
        with TestClient(app, base_url="http://testserver") as client:
            response = client.get("/test")

            assert response.status_code == 200
            # HSTS 標頭應該被跳過
            assert "Strict-Transport-Security" not in response.headers

    def test_x_forwarded_proto_https(self):
        """測試透過 X-Forwarded-Proto 檢測 HTTPS"""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware(enable_hsts=True)

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            return await middleware(request, call_next)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        with TestClient(app) as client:
            response = client.get("/test", headers={"X-Forwarded-Proto": "https"})

            assert response.status_code == 200
            assert "Strict-Transport-Security" in response.headers

    def test_csp_header_configuration(self):
        """測試內容安全政策標頭配置"""
        # 啟用 CSP
        middleware_with_csp = SecurityHeadersMiddleware(enable_csp=True)
        headers_with_csp = middleware_with_csp.get_headers()
        assert "Content-Security-Policy" in headers_with_csp

        # 禁用 CSP
        middleware_without_csp = SecurityHeadersMiddleware(enable_csp=False)
        headers_without_csp = middleware_without_csp.get_headers()
        assert "Content-Security-Policy" not in headers_without_csp

    def test_error_handling(self):
        """測試錯誤處理"""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware()

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            return await middleware(request, call_next)

        @app.get("/error")
        async def error_endpoint():
            raise Exception("Test error")

        with TestClient(app) as client:
            response = client.get("/error")

            assert response.status_code == 500
            # 即使出錯，安全標頭也應該存在
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers

    def test_add_custom_header(self, security_middleware):
        """測試動態添加自訂標頭"""
        # 添加前檢查
        headers_before = security_middleware.get_headers()
        assert "X-Custom-Test" not in headers_before

        # 添加自訂標頭
        security_middleware.add_custom_header("X-Custom-Test", "test-value")

        # 添加後檢查
        headers_after = security_middleware.get_headers()
        assert "X-Custom-Test" in headers_after
        assert headers_after["X-Custom-Test"] == "test-value"

    def test_remove_header(self, security_middleware):
        """測試移除標頭"""
        # 確認標頭存在
        headers_before = security_middleware.get_headers()
        assert "X-Frame-Options" in headers_before

        # 移除標頭
        result = security_middleware.remove_header("X-Frame-Options")
        assert result is True

        # 確認標頭已移除
        headers_after = security_middleware.get_headers()
        assert "X-Frame-Options" not in headers_after

        # 嘗試移除不存在的標頭
        result = security_middleware.remove_header("Non-Existent-Header")
        assert result is False

    def test_get_headers_returns_copy(self, security_middleware):
        """測試 get_headers 返回副本"""
        headers1 = security_middleware.get_headers()
        headers2 = security_middleware.get_headers()

        # 應該是不同的對象 (副本)
        assert headers1 is not headers2
        # 但內容應該相同
        assert headers1 == headers2

        # 修改副本不應影響原始標頭
        headers1["X-Test"] = "test"
        headers3 = security_middleware.get_headers()
        assert "X-Test" not in headers3

    def test_server_header_added(self, client):
        """測試 Server 標頭是否添加"""
        response = client.get("/test")

        assert response.status_code == 200
        assert "Server" in response.headers
        assert response.headers["Server"] == "FastAPI"

    def test_existing_headers_not_overwritten(self):
        """測試不覆蓋已存在的標頭"""
        app = FastAPI()
        middleware = SecurityHeadersMiddleware()

        @app.middleware("http")
        async def add_security_headers(request: Request, call_next):
            return await middleware(request, call_next)

        @app.get("/test")
        async def test_endpoint():
            response = JSONResponse({"message": "test"})
            # 手動設定一個安全標頭
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            return response

        with TestClient(app) as client:
            response = client.get("/test")

            assert response.status_code == 200
            # 應該保持原有值，不被覆蓋
            assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_predefined_middleware_instances(self):
        """測試預定義的中間件實例"""
        # 測試預設實例
        default_headers = default_security_middleware.get_headers()
        assert "Strict-Transport-Security" in default_headers
        assert "Content-Security-Policy" in default_headers

        # 測試開發環境實例
        dev_headers = dev_security_middleware.get_headers()
        assert "Strict-Transport-Security" not in dev_headers
        assert "Content-Security-Policy" in dev_headers

        # 測試生產環境實例
        prod_headers = prod_security_middleware.get_headers()
        assert "Strict-Transport-Security" in prod_headers
        assert "Content-Security-Policy" in prod_headers
        # 生產環境的 HSTS 應該有更長的 max-age
        assert "max-age=63072000" in prod_headers["Strict-Transport-Security"]

    @pytest.mark.asyncio
    async def test_middleware_call_with_mock(self, security_middleware):
        """測試中間件的直接調用"""
        # 創建模擬的 request 和 call_next
        mock_request = AsyncMock()
        mock_request.url.scheme = "https"
        mock_request.url.path = "/test"
        mock_request.headers = {}

        mock_response = AsyncMock()
        mock_response.headers = {}

        mock_call_next = AsyncMock(return_value=mock_response)

        # 調用中間件
        result = await security_middleware(mock_request, mock_call_next)

        # 檢查是否調用了下一個處理器
        mock_call_next.assert_called_once_with(mock_request)

        # 檢查返回的回應
        assert result == mock_response

        # 檢查是否添加了安全標頭
        assert len(mock_response.headers) > 0

    @pytest.mark.asyncio
    async def test_middleware_exception_handling(self, security_middleware):
        """測試中間件的異常處理"""
        # 創建會拋出異常的 call_next
        mock_request = AsyncMock()
        mock_request.url.scheme = "http"
        mock_request.url.path = "/error"
        mock_request.headers = {}

        mock_call_next = AsyncMock(side_effect=Exception("Test error"))

        # 調用中間件
        result = await security_middleware(mock_request, mock_call_next)

        # 檢查返回錯誤回應
        assert hasattr(result, "status_code")
        assert result.status_code == 500

        # 檢查錯誤回應也包含安全標頭
        assert len(result.headers) > 0
        assert "X-Content-Type-Options" in result.headers
