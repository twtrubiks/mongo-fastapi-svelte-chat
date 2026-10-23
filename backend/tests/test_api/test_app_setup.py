"""app/main.py 組裝出的 app：公開端點契約、CORS / TrustedHost / 安全標頭設定

main.py 在 import 時依 settings（DEBUG、CORS_ORIGINS、ALLOWED_HOSTS、SECURITY_*）
組裝中介層。為了測生產與開發兩種組態又不動到全域共用的 app.main，
這裡以指定設定重新執行一次 main.py 的原始碼，取得一個獨立的 app 實例。
"""

import importlib.util
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.config import settings

ALLOWED_METHODS = "GET, POST, PUT, DELETE, OPTIONS"
# Starlette 會把 CORS 安全清單標頭（Accept-Language、Content-Language）一併列入
ALLOWED_HEADERS = (
    "Accept, Accept-Language, Authorization, Content-Language, "
    "Content-Type, X-Requested-With"
)
DEV_CSP = {
    "default-src": [
        "'self'",
        "'unsafe-inline'",
        "'unsafe-eval'",
        "https://cdn.jsdelivr.net",
    ],
    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "'unsafe-eval'",
        "https://cdn.jsdelivr.net",
    ],
    "style-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
    "connect-src": ["'self'", "ws:", "wss:", "http:", "https:"],
    "img-src": ["'self'", "data:", "http:", "https:"],
    "font-src": ["'self'", "https:", "https://cdn.jsdelivr.net"],
    "frame-ancestors": ["'none'"],
}


def parse_csp(header: str) -> dict[str, list[str]]:
    directives = {}
    for part in header.split(";"):
        name, *sources = part.split()
        directives[name] = sources
    return directives


def build_app(monkeypatch, **overrides):
    """以覆寫後的 settings 重新執行 main.py，回傳獨立的 FastAPI app"""
    with monkeypatch.context() as patched:
        for name, value in overrides.items():
            patched.setattr(settings, name, value)
        spec = importlib.util.spec_from_file_location(
            "app_main_isolated", main_module.__file__
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module.app


@pytest.fixture
def app_client(monkeypatch):
    @asynccontextmanager
    async def _client(base_url: str = "http://test", **overrides):
        app = build_app(monkeypatch, **overrides)
        with patch(
            "app.middleware.rate_limiting.RateLimitingMiddleware._should_skip_rate_limiting",
            return_value=True,
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url=base_url
            ) as client:
                yield client

    return _client


def preflight(origin: str, method: str = "PUT", headers: str | None = None) -> dict:
    request_headers = {"Origin": origin, "Access-Control-Request-Method": method}
    if headers:
        request_headers["Access-Control-Request-Headers"] = headers
    return request_headers


@pytest.mark.asyncio
@pytest.mark.integration
class TestPublicEndpoints:
    async def test_root(self, async_client):
        response = await async_client.get("/")

        assert response.status_code == 200
        assert response.json() == {
            "message": "即時聊天室 API",
            "status": "running",
            "version": "1.0.0",
        }

    async def test_health_reports_infrastructure(self, async_client):
        response = await async_client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "service": "chatroom-api",
            "version": "1.0.0",
            "infrastructure": {
                "status": "healthy",
                "checks": {"mongodb": "connected", "redis": "connected"},
                "errors": [],
            },
        }

    async def test_openapi_info(self, async_client):
        response = await async_client.get("/openapi.json")

        assert response.status_code == 200
        assert response.json()["info"] == {
            "title": "即時聊天室 API",
            "description": "使用 FastAPI + MongoDB + WebSocket 的即時聊天室",
            "version": "1.0.0",
        }


@pytest.mark.asyncio
@pytest.mark.integration
class TestProductionCors:
    """DEBUG=False：只放行 CORS_ORIGINS 逗號清單中的來源"""

    ORIGINS = "https://app.example.com,https://admin.example.com"

    async def test_listed_origin_preflight(self, app_client):
        async with app_client(DEBUG=False, CORS_ORIGINS=self.ORIGINS) as client:
            response = await client.options(
                "/api/rooms",
                headers=preflight(
                    "https://admin.example.com",
                    headers="authorization, content-type, x-requested-with",
                ),
            )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == (
            "https://admin.example.com"
        )
        assert response.headers["Access-Control-Allow-Credentials"] == "true"
        assert response.headers["Access-Control-Allow-Methods"] == ALLOWED_METHODS
        assert response.headers["Access-Control-Allow-Headers"] == ALLOWED_HEADERS

    async def test_listed_origin_simple_request(self, app_client):
        async with app_client(DEBUG=False, CORS_ORIGINS=self.ORIGINS) as client:
            response = await client.get(
                "/", headers={"Origin": "https://app.example.com"}
            )

        assert response.headers["Access-Control-Allow-Origin"] == (
            "https://app.example.com"
        )
        assert response.headers["Access-Control-Allow-Credentials"] == "true"

    @pytest.mark.parametrize(
        ("request_headers", "reason"),
        [
            pytest.param(
                preflight("https://evil.example.com"), "origin", id="unlisted-origin"
            ),
            pytest.param(
                preflight("https://app.example.com", method="PATCH"),
                "method",
                id="unlisted-method",
            ),
            pytest.param(
                preflight("https://app.example.com", headers="x-api-key"),
                "headers",
                id="unlisted-header",
            ),
        ],
    )
    async def test_preflight_rejected(self, app_client, request_headers, reason):
        async with app_client(DEBUG=False, CORS_ORIGINS=self.ORIGINS) as client:
            response = await client.options("/api/rooms", headers=request_headers)

        assert response.status_code == 400
        assert response.text == f"Disallowed CORS {reason}"

    async def test_wildcard_setting_allows_any_origin(self, app_client):
        async with app_client(DEBUG=False, CORS_ORIGINS="*") as client:
            response = await client.options(
                "/api/rooms", headers=preflight("https://anywhere.example.org")
            )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == (
            "https://anywhere.example.org"
        )


@pytest.mark.asyncio
@pytest.mark.integration
class TestDebugCors:
    async def test_debug_ignores_cors_origins_setting(self, app_client):
        """開發模式放行所有來源（例如 Vite dev server），不受 CORS_ORIGINS 限制"""
        async with app_client(
            DEBUG=True, CORS_ORIGINS="https://app.example.com"
        ) as client:
            response = await client.options(
                "/api/rooms", headers=preflight("http://localhost:5173")
            )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == (
            "http://localhost:5173"
        )


@pytest.mark.asyncio
@pytest.mark.integration
class TestTrustedHosts:
    async def test_production_rejects_unlisted_host(self, app_client):
        async with app_client(
            DEBUG=False, ALLOWED_HOSTS="api.example.com,test"
        ) as client:
            listed = await client.get("/")
            unlisted = await client.get("/", headers={"Host": "evil.example.com"})

        assert listed.status_code == 200
        assert unlisted.status_code == 400
        assert unlisted.text == "Invalid host header"

    async def test_debug_does_not_restrict_hosts(self, app_client):
        async with app_client(DEBUG=True, ALLOWED_HOSTS="api.example.com") as client:
            response = await client.get("/", headers={"Host": "evil.example.com"})

        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
class TestHstsConfiguration:
    async def test_disabled_by_setting(self, app_client):
        async with app_client(
            base_url="https://test", DEBUG=False, SECURITY_ENABLE_HSTS=False
        ) as client:
            response = await client.get("/")

        assert response.status_code == 200
        assert "Strict-Transport-Security" not in response.headers

    async def test_production_without_custom_headers_still_sends_hsts(self, app_client):
        """SECURITY_ENABLE_HEADERS=False 只關掉 security_config 的標頭，HSTS 由中介層基礎標頭送出"""
        async with app_client(
            base_url="https://test",
            DEBUG=False,
            SECURITY_ENABLE_HEADERS=False,
            SECURITY_HSTS_MAX_AGE=600,
        ) as client:
            response = await client.get("/")

        assert response.headers["Strict-Transport-Security"] == (
            "max-age=600; includeSubDomains; preload"
        )

    async def test_debug_without_custom_headers_skips_hsts(self, app_client):
        async with app_client(
            base_url="https://test", DEBUG=True, SECURITY_ENABLE_HEADERS=False
        ) as client:
            response = await client.get("/")

        assert response.status_code == 200
        assert "Strict-Transport-Security" not in response.headers


@pytest.mark.asyncio
@pytest.mark.integration
class TestDevelopmentCsp:
    async def test_debug_csp_allows_swagger_ui_cdn(self, app_client):
        """DEBUG 時 /docs 的 Swagger UI 從 CDN 載入，CSP 必須放行該來源"""
        async with app_client(DEBUG=True, SECURITY_DEVELOPMENT_MODE=False) as client:
            response = await client.get("/docs")

        assert response.status_code == 200
        assert (
            '<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist' in response.text
        )
        assert parse_csp(response.headers["Content-Security-Policy"]) == DEV_CSP
