"""錯誤處理中間件測試"""

import ast
import logging
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

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


def _app_raising(exc: Exception, **handler_kwargs) -> FastAPI:
    app = FastAPI()
    app.add_middleware(GlobalErrorHandler, **handler_kwargs)

    @app.api_route("/boom", methods=["GET", "POST"])
    async def boom():
        raise exc

    return app


def _assert_recent_utc(timestamp: str) -> datetime:
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - parsed) < timedelta(seconds=5)
    return parsed


@pytest.mark.unit
class TestGlobalErrorHandlerContract:
    """回應格式、debug 與生產模式差異、錯誤日誌內容"""

    def test_response_envelope(self):
        client = TestClient(_app_raising(PyMongoError("db down"), debug=False))

        response = client.post("/boom?page=2")

        assert response.status_code == 500
        assert response.headers["content-type"] == "application/json; charset=utf-8"
        body = response.json()
        _assert_recent_utc(body["error"].pop("timestamp"))
        assert body == {
            "success": False,
            "error": {
                "code": "DATABASE_ERROR",
                "message": "資料庫操作失敗",
                "path": "http://testserver/boom?page=2",
                "method": "POST",
            },
        }

    def test_defaults_to_production_mode(self):
        """未指定 debug 時不得洩漏例外訊息與類型"""
        client = TestClient(_app_raising(ValueError("internal secret")))

        response = client.get("/boom")

        assert response.status_code == 500
        error = response.json()["error"]
        assert error["message"] == "伺服器內部錯誤"
        assert "details" not in error
        assert "internal secret" not in response.text
        assert "ValueError" not in response.text

    @pytest.mark.parametrize(
        ("exc", "status_code", "code", "message", "details"),
        [
            pytest.param(
                DuplicateKeyError("E11000 duplicate key"),
                409,
                "DUPLICATE_KEY_ERROR",
                "資源重複，請檢查唯一性限制",
                {"error": "E11000 duplicate key"},
                id="duplicate-key",
            ),
            pytest.param(
                BulkWriteError(
                    {"writeErrors": [{"index": 0, "code": 11000, "errmsg": "dup"}]}
                ),
                400,
                "BULK_WRITE_ERROR",
                "批量寫入操作失敗",
                {"write_errors": [{"index": 0, "code": 11000, "errmsg": "dup"}]},
                id="bulk-write",
            ),
            pytest.param(
                PyMongoError("db down"),
                500,
                "DATABASE_ERROR",
                "資料庫操作失敗",
                {"error": "db down"},
                id="pymongo",
            ),
            pytest.param(
                RedisConnectionError("redis unreachable"),
                503,
                "CACHE_CONNECTION_ERROR",
                "快取服務連線失敗",
                {"error": "redis unreachable"},
                id="redis-connection",
            ),
            pytest.param(
                RedisError("redis op failed"),
                500,
                "CACHE_ERROR",
                "快取操作失敗",
                {"error": "redis op failed"},
                id="redis",
            ),
            pytest.param(
                ValueError("boom"),
                500,
                "INTERNAL_SERVER_ERROR",
                "boom",
                {"error_type": "ValueError"},
                id="unknown",
            ),
        ],
    )
    def test_debug_details(self, exc, status_code, code, message, details):
        client = TestClient(_app_raising(exc, debug=True))

        response = client.get("/boom")

        assert response.status_code == status_code
        error = response.json()["error"]
        assert (error["code"], error["message"], error["details"]) == (
            code,
            message,
            details,
        )

    @pytest.mark.parametrize(
        ("exc", "level", "prefix", "status_code", "code", "message"),
        [
            pytest.param(
                RedisError("redis op failed"),
                "ERROR",
                "伺服器錯誤: ",
                500,
                "CACHE_ERROR",
                "快取操作失敗",
                id="5xx",
            ),
            pytest.param(
                DuplicateKeyError("dup"),
                "WARNING",
                "客戶端錯誤: ",
                409,
                "DUPLICATE_KEY_ERROR",
                "資源重複，請檢查唯一性限制",
                id="4xx",
            ),
        ],
    )
    def test_error_is_logged_with_request_context(
        self, caplog, exc, level, prefix, status_code, code, message
    ):
        client = TestClient(_app_raising(exc, debug=False))

        with caplog.at_level(logging.INFO, logger="app.middleware.error_handler"):
            response = client.get(
                "/boom",
                headers={
                    "User-Agent": "chat-client/1.0",
                    "X-Forwarded-For": "203.0.113.9, 10.0.0.1",
                },
            )

        records = [
            r for r in caplog.records if r.name == "app.middleware.error_handler"
        ]
        assert [r.levelname for r in records] == [level]
        logged = records[0].getMessage()
        assert logged.startswith(prefix)
        assert ast.literal_eval(logged.removeprefix(prefix)) == {
            "method": "GET",
            "url": "http://testserver/boom",
            "status_code": status_code,
            "error_code": code,
            "error_message": message,
            "timestamp": response.json()["error"]["timestamp"],
            "user_agent": "chat-client/1.0",
            "client_ip": "203.0.113.9",
        }

    @pytest.mark.parametrize(
        "exc",
        [
            pytest.param(
                DuplicateKeyError('E11000 dup key: { email: "alice@example.com" }'),
                id="duplicate-key",
            ),
            pytest.param(
                BulkWriteError(
                    {"writeErrors": [{"index": 0, "code": 11000, "errmsg": "dup"}]}
                ),
                id="bulk-write",
            ),
        ],
    )
    def test_production_hides_details_and_traceback(self, caplog, exc):
        """生產模式：錯誤即使帶細節（如重複的鍵值）也不放進回應，也不記 traceback"""
        client = TestClient(_app_raising(exc, debug=False))

        with caplog.at_level(logging.DEBUG, logger="app.middleware.error_handler"):
            response = client.get("/boom")

        assert "details" not in response.json()["error"]
        assert "alice@example.com" not in response.text
        assert not any(
            r.getMessage().startswith("Traceback:")
            for r in caplog.records
            if r.name == "app.middleware.error_handler"
        )

    def test_debug_logs_traceback_for_unexpected_errors(self, caplog):
        client = TestClient(_app_raising(ValueError("boom"), debug=True))

        with caplog.at_level(logging.DEBUG, logger="app.middleware.error_handler"):
            client.get("/boom")

        tracebacks = [
            r.getMessage()
            for r in caplog.records
            if r.name == "app.middleware.error_handler"
            and r.getMessage().startswith("Traceback:")
        ]
        assert len(tracebacks) == 1
        assert "ValueError: boom" in tracebacks[0]
