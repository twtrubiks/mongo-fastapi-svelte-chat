"""錯誤處理中間件測試"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.middleware.error_handler import GlobalErrorHandler


@pytest.fixture
def app_with_error_handler():
    """創建帶有錯誤處理中間件的測試應用"""
    app = FastAPI()
    app.add_middleware(GlobalErrorHandler, debug=True)

    @app.get("/test/http-exception")
    async def http_exception():
        raise HTTPException(status_code=400, detail="HTTP 錯誤")

    @app.get("/test/unknown-error")
    async def unknown_error():
        raise ValueError("未知錯誤")

    @app.get("/test/success")
    async def success():
        return {"message": "成功"}

    return app


@pytest.fixture
def client(app_with_error_handler):
    """測試客戶端"""
    return TestClient(app_with_error_handler)


@pytest.mark.integration
@pytest.mark.slow
class TestErrorHandlerMiddleware:
    """錯誤處理中間件測試"""

    def test_http_exception(self, client):
        """測試 HTTP 異常處理 (FastAPI 會自動處理，不會到達中間件)"""
        response = client.get("/test/http-exception")

        assert response.status_code == 400
        data = response.json()
        # HTTPException 由 FastAPI 自動處理，返回標準格式
        assert "detail" in data
        assert data["detail"] == "HTTP 錯誤"

    def test_unknown_error(self, client):
        """測試未知錯誤處理"""
        response = client.get("/test/unknown-error")

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        # 在 debug 模式下應該顯示錯誤訊息
        assert (
            "未知錯誤" in data["error"]["message"]
            or "ValueError" in data["error"]["message"]
        )

    def test_successful_request(self, client):
        """測試正常請求不受影響"""
        response = client.get("/test/success")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "成功"
