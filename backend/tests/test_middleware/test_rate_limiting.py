"""Rate Limiting 中間件測試

涵蓋：
1. 同秒摺疊 — ZSET member 若不唯一，同一秒內的請求會被 ZADD 摺疊成一筆，計數失真
2. 客戶端識別符 — X-Forwarded-For 只信任可信 proxy、Bearer token 分桶、直連偽造 XFF 無效
3. dispatch — 以生產設定（DEBUG=False）與真實 Redis 驗證實際回 429、
   路徑對應的限制、跳過路徑與分桶；dispatch 對任何錯誤 fail-open 放行，
   因此「沒有回 429」本身就是限流失效的訊號
4. 時間相關 — 固定限流模組的時間來源，驗證突發視窗邊界、重置秒數範圍、
   429 回應內容與標頭一致性、key 的 TTL

限流需要 Redis：Redis 不可用時測試直接失敗，不 skip。
"""

import logging
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from app.auth.jwt_handler import create_access_token
from app.config import Settings
from app.database.redis_conn import get_redis
from app.middleware.rate_limiting import (
    RateLimitingMiddleware,
    SlidingWindowRateLimiter,
)

PRODUCTION = {
    "_env_file": None,
    "DEBUG": False,
    "RATE_LIMIT_REQUESTS_PER_MINUTE": 60,
    "RATE_LIMIT_REQUESTS_PER_HOUR": 1000,
    "RATE_LIMIT_BURST_SIZE": 10,
}

NOW = 1_800_000_000


def freeze_time(now: int):
    """固定限流模組看到的時間（只換掉該模組的 time，不影響 event loop 與 Redis client）"""
    return patch("app.middleware.rate_limiting.time", SimpleNamespace(time=lambda: now))


def rate_limit_headers(response) -> dict[str, str]:
    return {k: v for k, v in response.headers.items() if k.startswith("x-ratelimit-")}


@pytest.fixture
async def redis_client():
    client = await get_redis()
    assert await client.ping(), "Redis 不可用：限流測試需要真實 Redis"
    return client


def make_request(
    client_host: str = "203.0.113.10", headers: dict | None = None
) -> Request:
    """建立最小可用的 Starlette Request（只含識別符邏輯需要的欄位）"""
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test",
        "headers": raw_headers,
        "client": (client_host, 12345),
        "query_string": b"",
    }
    return Request(scope)


@pytest.fixture
def middleware() -> RateLimitingMiddleware:
    """不啟動 app 的 middleware 實例（只測識別符邏輯，不走 dispatch）"""
    return RateLimitingMiddleware(app=None, settings=Settings())


class TestClientIdentifier:
    """客戶端識別符：XFF 信任邊界與 Bearer token 分桶"""

    def test_direct_client_forged_xff_ignored(self, middleware):
        """直連請求（非可信 proxy）偽造 XFF 不能換桶"""
        request = make_request(
            client_host="203.0.113.10",
            headers={"X-Forwarded-For": "1.2.3.4"},
        )
        assert middleware._get_client_identifier(request) == "ip:203.0.113.10"

    def test_trusted_proxy_xff_used(self, middleware):
        """來自可信 proxy（BFF）的 XFF 採信"""
        request = make_request(
            client_host="127.0.0.1",
            headers={"X-Forwarded-For": "198.51.100.7"},
        )
        assert middleware._get_client_identifier(request) == "ip:198.51.100.7"

    def test_trusted_proxy_xff_takes_rightmost(self, middleware):
        """多段 XFF 取最右端（可信 proxy 附加），最左端可被偽造"""
        request = make_request(
            client_host="127.0.0.1",
            headers={"X-Forwarded-For": "6.6.6.6, 198.51.100.7"},
        )
        assert middleware._get_client_identifier(request) == "ip:198.51.100.7"

    def test_no_xff_uses_direct_ip(self, middleware):
        """無 XFF 時使用直連 IP"""
        request = make_request(client_host="203.0.113.10")
        assert middleware._get_client_identifier(request) == "ip:203.0.113.10"

    def test_valid_bearer_token_uses_user_bucket(self, middleware):
        """有效 Bearer token 以 user_id 分桶（避免 BFF 後所有用戶共享 IP 桶）"""
        token = create_access_token({"sub": "tester", "user_id": "user-abc-123"})
        request = make_request(headers={"Authorization": f"Bearer {token}"})
        assert middleware._get_client_identifier(request) == "user:user-abc-123"

    def test_invalid_bearer_token_falls_back_to_ip(self, middleware):
        """無效 token（偽造簽章）退回 IP 分桶，不能自選桶名"""
        request = make_request(
            client_host="203.0.113.10",
            headers={"Authorization": "Bearer not-a-valid-jwt"},
        )
        assert middleware._get_client_identifier(request) == "ip:203.0.113.10"


class TestSlidingWindowCounting:
    """滑動視窗計數：同秒請求必須逐筆計數（需要真實 Redis 驗證 ZADD 語意）"""

    async def test_same_second_requests_counted_individually(self, redis_client):
        """同一秒內連續請求逐筆計數，超過上限即拒絕（回歸：member 摺疊）"""
        limiter = SlidingWindowRateLimiter(redis_client, Settings())
        key = f"rate_limit:test:{uuid.uuid4().hex}"
        try:
            results = []
            for _ in range(5):
                allowed, _, _ = await limiter.is_allowed(
                    key, window_size=60, max_requests=3
                )
                results.append(allowed)
            # 修正前：同秒 member 摺疊成一筆，5 次全數放行
            assert results == [True, True, True, False, False]
        finally:
            await redis_client.delete(key)

    async def test_burst_limit_counts_same_second(self, redis_client):
        """突發限制同樣逐筆計數（zcount 與 zcard 共用同一批 member）"""
        limiter = SlidingWindowRateLimiter(redis_client, Settings())
        key = f"rate_limit:test:{uuid.uuid4().hex}"
        try:
            results = []
            for _ in range(4):
                allowed, _, _ = await limiter.is_allowed(
                    key, window_size=300, max_requests=100, burst_size=2
                )
                results.append(allowed)
            # 視窗上限寬鬆（100），第 3 次起應被突發限制（2）擋下
            assert results == [True, True, False, False]
        finally:
            await redis_client.delete(key)


class TestSlidingWindowTiming:
    """固定時間來源下的視窗邊界、重置秒數與 key 存活時間（真實 Redis）"""

    @pytest.mark.parametrize(("age", "allowed"), [(60, False), (61, True)])
    async def test_burst_window_covers_last_60_seconds(
        self, redis_client, age, allowed
    ):
        """突發視窗含 60 秒前的請求，61 秒前的不再計入突發"""
        limiter = SlidingWindowRateLimiter(redis_client, Settings())
        key = f"rate_limit:test:{uuid.uuid4().hex}"
        try:
            await redis_client.zadd(key, {f"old-{i}": NOW - age for i in range(2)})
            with freeze_time(NOW):
                result, _, _ = await limiter.is_allowed(
                    key, window_size=300, max_requests=100, burst_size=2
                )
        finally:
            await redis_client.delete(key)

        assert result is allowed

    async def test_reset_seconds_within_window_at_every_second(self, redis_client):
        """連續兩分鐘的每一秒，回報的重置秒數都落在 1 ~ 視窗長度

        0 會叫客戶端立刻重試、負數或超過視窗長度則不合理；
        突發視窗含 60 秒前的請求，因此上限是 61 秒。
        """
        limiter = SlidingWindowRateLimiter(redis_client, Settings())
        keys = []
        out_of_range = []
        try:
            for now in range(NOW, NOW + 120):
                window_key = f"rate_limit:test:{uuid.uuid4().hex}"
                burst_key = f"rate_limit:test:{uuid.uuid4().hex}"
                keys += [window_key, burst_key]
                with freeze_time(now):
                    first = await limiter.is_allowed(window_key, 60, 1)
                    window_blocked = await limiter.is_allowed(window_key, 60, 1)
                    await limiter.is_allowed(burst_key, 300, 100, burst_size=1)
                    burst_blocked = await limiter.is_allowed(
                        burst_key, 300, 100, burst_size=1
                    )

                assert (first[0], window_blocked[0], burst_blocked[0]) == (
                    True,
                    False,
                    False,
                )
                if not (
                    1 <= first[2] <= 60
                    and 1 <= window_blocked[2] <= 60
                    and 1 <= burst_blocked[2] <= 61
                ):
                    out_of_range.append(
                        (now, first[2], window_blocked[2], burst_blocked[2])
                    )
        finally:
            await redis_client.delete(*keys)

        assert out_of_range == []

    @pytest.mark.parametrize(
        ("window_size", "max_requests", "burst_size", "expected"),
        [(300, 100, 3, 41), (60, 3, None, 40)],
        ids=["burst", "window"],
    )
    async def test_retry_after_is_when_request_would_be_allowed(
        self, redis_client, window_size, max_requests, burst_size, expected
    ):
        """依回報秒數等待後重試即放行、早一秒仍被擋：滑動視窗以最舊紀錄過期為準，
        不對齊固定的整分鐘邊界"""
        limiter = SlidingWindowRateLimiter(redis_client, Settings())
        key = f"rate_limit:test:{uuid.uuid4().hex}"
        start = NOW + 40  # 不在整分鐘邊界上

        async def attempt(at: int):
            with freeze_time(at):
                return await limiter.is_allowed(
                    key, window_size, max_requests, burst_size=burst_size
                )

        try:
            for offset in (0, 10, 20):
                assert (await attempt(start + offset))[0] is True
            blocked, _, retry_after = await attempt(start + 20)
            too_early = await attempt(start + 20 + retry_after - 1)
            on_time = await attempt(start + 20 + retry_after)
        finally:
            await redis_client.delete(key)

        assert blocked is False
        assert retry_after == expected
        assert too_early[0] is False
        assert on_time[0] is True

    async def test_key_expires_once_last_request_stops_counting(self, redis_client):
        """key 存活到最後一筆請求不再被計數為止後由 Redis 自動清除

        視窗 60 秒、突發視窗含 60 秒前的請求，最後一筆在 61 秒內都還算數，
        TTL 不足會提早遺失計數，未設定則閒置 key 永遠殘留。
        """
        limiter = SlidingWindowRateLimiter(redis_client, Settings())
        key = f"rate_limit:test:{uuid.uuid4().hex}"
        try:
            await limiter.is_allowed(key, window_size=60, max_requests=10, burst_size=5)
            ttl_ms = await redis_client.pttl(key)
        finally:
            await redis_client.delete(key)

        assert 60_000 < ttl_ms <= 61_000


def make_app(**settings_overrides) -> FastAPI:
    """掛上 RateLimitingMiddleware 的最小 app，所有路徑都回 200"""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        RateLimitingMiddleware,
        settings=Settings(**{**PRODUCTION, **settings_overrides}),
    )

    @app.api_route("/{path:path}", methods=["GET", "POST"])
    async def catch_all(path: str):
        return {"ok": True}

    return app


def make_client(app: FastAPI, client_ip: str = "127.0.0.1") -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, client=(client_ip, 12345)),
        base_url="http://test",
    )


def unique_client() -> dict:
    """經可信 proxy（127.0.0.1）轉送的唯一客戶端，避免測試間共用限流桶"""
    return {"X-Forwarded-For": f"client-{uuid.uuid4().hex}"}


async def hit(client: AsyncClient, path: str, headers: dict, times: int) -> list[int]:
    return [
        (await client.post(path, headers=headers)).status_code for _ in range(times)
    ]


@pytest.mark.asyncio
@pytest.mark.integration
class TestRateLimitingDispatch:
    """經由 dispatch 實際限流（生產設定、真實 Redis）"""

    async def test_login_burst_limit(self):
        async with make_client(make_app()) as client:
            headers = unique_client()
            statuses = await hit(client, "/api/auth/login", headers, 10)
            blocked = await client.post("/api/auth/login", headers=headers)

        assert statuses == [200] * 10
        assert blocked.status_code == 429
        assert blocked.json()["error"] == "Rate limit exceeded"
        assert blocked.json()["limit"] == 20
        assert blocked.json()["window"] == 300
        # 突發視窗含剛好 60 秒前的請求，最舊一筆要 61 秒後才滑出
        assert 0 < int(blocked.headers["Retry-After"]) <= 61
        assert blocked.headers["X-RateLimit-Remaining"] == "0"

    async def test_register_burst_limit(self):
        async with make_client(make_app()) as client:
            statuses = await hit(client, "/api/auth/register", unique_client(), 6)

        assert statuses == [200] * 5 + [429]

    async def test_rate_limit_headers_on_allowed_requests(self):
        with freeze_time(NOW):
            async with make_client(make_app()) as client:
                headers = unique_client()
                first = await client.post("/api/auth/login", headers=headers)
                second = await client.post("/api/auth/login", headers=headers)

        reset_at = int(first.headers["X-RateLimit-Reset"])
        assert NOW < reset_at <= NOW + 300
        assert rate_limit_headers(first) == {
            "x-ratelimit-limit": "20",
            "x-ratelimit-remaining": "19",
            "x-ratelimit-reset": str(reset_at),
            "x-ratelimit-window": "300",
        }
        assert rate_limit_headers(second) == {
            **rate_limit_headers(first),
            "x-ratelimit-remaining": "18",
        }

    @pytest.mark.parametrize(
        ("overrides", "limit"),
        [
            ({"RATE_LIMIT_REQUESTS_PER_MINUTE": 2, "RATE_LIMIT_BURST_SIZE": 10}, 2),
            ({"RATE_LIMIT_REQUESTS_PER_MINUTE": 100, "RATE_LIMIT_BURST_SIZE": 2}, 100),
        ],
        ids=["window-limit", "burst-limit"],
    )
    async def test_rejected_response_contract(self, overrides, limit):
        """429 的 body 與標頭彼此一致：retry_after = Retry-After、Reset = 現在 + Retry-After"""
        with freeze_time(NOW):
            async with make_client(make_app(**overrides)) as client:
                headers = unique_client()
                await hit(client, "/api/rooms", headers, 2)
                blocked = await client.post("/api/rooms", headers=headers)

        assert blocked.status_code == 429
        retry_after = int(blocked.headers["Retry-After"])
        assert blocked.json() == {
            "error": "Rate limit exceeded",
            "message": f"Too many requests. Please try again in {retry_after} seconds.",
            "retry_after": retry_after,
            "limit": limit,
            "window": 60,
        }
        assert rate_limit_headers(blocked) == {
            "x-ratelimit-limit": str(limit),
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset": str(NOW + retry_after),
            "x-ratelimit-window": "60",
        }

    async def test_api_paths_use_configured_limits(self):
        async with make_client(
            make_app(RATE_LIMIT_REQUESTS_PER_MINUTE=40, RATE_LIMIT_BURST_SIZE=3)
        ) as client:
            headers = unique_client()
            statuses = await hit(client, "/api/rooms", headers, 4)
            blocked = await client.post("/api/rooms", headers=headers)

        assert statuses == [200, 200, 200, 429]
        assert blocked.json()["limit"] == 40
        assert blocked.json()["window"] == 60

    @pytest.mark.parametrize("path", ["/api/files/upload", "/api/files/upload/image"])
    async def test_upload_paths_use_upload_limits(self, path):
        """上傳子路徑要套用上傳設定，不能被較短的 /api/ 前綴搶先命中"""
        async with make_client(make_app()) as client:
            statuses = await hit(client, path, unique_client(), 6)
            response = await client.post(path, headers=unique_client())

        assert statuses == [200] * 5 + [429]
        assert response.headers["X-RateLimit-Window"] == "300"
        assert response.headers["X-RateLimit-Limit"] == "20"

    async def test_websocket_path_limits(self):
        async with make_client(make_app()) as client:
            statuses = await hit(client, "/ws/room-1", unique_client(), 4)

        assert statuses == [200, 200, 200, 429]

    async def test_other_paths_use_default_limits(self):
        async with make_client(make_app(RATE_LIMIT_REQUESTS_PER_HOUR=500)) as client:
            response = await client.get("/", headers=unique_client())

        assert response.headers["X-RateLimit-Window"] == "3600"
        assert response.headers["X-RateLimit-Limit"] == "500"

    @pytest.mark.parametrize(
        "path", ["/health", "/docs", "/redoc", "/openapi.json", "/static/app.js"]
    )
    async def test_skipped_paths_never_limited(self, path):
        async with make_client(make_app(RATE_LIMIT_BURST_SIZE=1)) as client:
            headers = unique_client()
            responses = [await client.get(path, headers=headers) for _ in range(3)]

        assert [r.status_code for r in responses] == [200, 200, 200]
        assert all("X-RateLimit-Limit" not in r.headers for r in responses)

    async def test_api_health_like_paths_are_not_skipped(self):
        async with make_client(make_app()) as client:
            response = await client.get("/api/health", headers=unique_client())

        assert response.headers["X-RateLimit-Window"] == "60"

    async def test_buckets_are_per_client_and_per_path(self):
        async with make_client(make_app()) as client:
            exhausted = unique_client()
            await hit(client, "/api/auth/register", exhausted, 5)

            same_client = await client.post("/api/auth/register", headers=exhausted)
            other_client = await client.post(
                "/api/auth/register", headers=unique_client()
            )
            other_path = await client.post("/api/auth/login", headers=exhausted)

        assert same_client.status_code == 429
        assert other_client.status_code == 200
        assert other_path.status_code == 200

    async def test_untrusted_client_cannot_rotate_buckets_with_xff(self):
        """直連（非可信 proxy）偽造 X-Forwarded-For 無法換桶繞過限流"""
        # 註冊桶視窗 1 小時：只有 250 種隨機 IP 時，重跑會撞到 Redis 中仍在視窗內的舊桶，
        # 改用文件保留段（2001:db8::/32）的 IPv6 加 48 位元隨機後綴
        suffix = uuid.uuid4().hex[:12]
        client_ip = f"2001:db8::{suffix[:4]}:{suffix[4:8]}:{suffix[8:]}"
        async with make_client(make_app(), client_ip=client_ip) as client:
            statuses = [
                (
                    await client.post("/api/auth/register", headers=unique_client())
                ).status_code
                for _ in range(6)
            ]

        assert statuses == [200] * 5 + [429]

    async def test_authenticated_user_bucket_follows_token(self):
        token = create_access_token(
            {"sub": "limited", "user_id": f"user-{uuid.uuid4().hex}"}
        )
        async with make_client(make_app()) as client:
            statuses = [
                (
                    await client.post(
                        "/api/auth/register",
                        headers={
                            "Authorization": f"Bearer {token}",
                            **unique_client(),
                        },
                    )
                ).status_code
                for _ in range(6)
            ]

        assert statuses == [200] * 5 + [429]

    async def test_debug_mode_uses_lenient_limits(self):
        async with make_client(make_app(DEBUG=True)) as client:
            statuses = await hit(client, "/api/auth/login", unique_client(), 11)

        assert statuses == [200] * 11

    async def test_no_fail_open_on_normal_requests(self, caplog):
        """正常請求不應走進 fail-open 分支（初始化或查表錯誤都會靜默放行）"""
        with caplog.at_level(logging.WARNING, logger="app.middleware.rate_limiting"):
            async with make_client(make_app()) as client:
                for path in ("/api/auth/login", "/api/rooms", "/ws/x", "/"):
                    await client.post(path, headers=unique_client())

        assert caplog.records == []

    async def test_fail_open_when_redis_unavailable(self, caplog):
        """Redis 不可用時放行請求（刻意的 fail-open 設計），並以 warning 記錄限流停用，
        而不是走進內部錯誤分支"""
        with (
            patch(
                "app.middleware.rate_limiting.get_redis",
                side_effect=ConnectionError("redis down"),
            ),
            caplog.at_level(logging.WARNING, logger="app.middleware.rate_limiting"),
        ):
            async with make_client(make_app(RATE_LIMIT_BURST_SIZE=1)) as client:
                statuses = await hit(client, "/api/rooms", unique_client(), 3)

        assert statuses == [200, 200, 200]
        assert [
            (r.levelname, r.getMessage())
            for r in caplog.records
            if r.name == "app.middleware.rate_limiting"
        ] == [
            ("WARNING", "Failed to initialize rate limiter: redis down"),
            ("WARNING", "Rate limiter not available, allowing request"),
        ] * 3


@pytest.mark.unit
class TestRateLimitConfiguration:
    def test_production_limits(self):
        middleware = RateLimitingMiddleware(app=None, settings=Settings(**PRODUCTION))

        assert middleware.rate_limits == {
            "/api/auth/login": {"window": 300, "max_requests": 20, "burst": 10},
            "/api/auth/register": {"window": 3600, "max_requests": 10, "burst": 5},
            "/api/": {"window": 60, "max_requests": 60, "burst": 10},
            "/api/files/upload": {"window": 300, "max_requests": 20, "burst": 5},
            "/ws": {"window": 60, "max_requests": 10, "burst": 3},
            "default": {"window": 3600, "max_requests": 1000, "burst": 10},
        }

    def test_debug_limits_are_more_lenient(self):
        production = RateLimitingMiddleware(app=None, settings=Settings(**PRODUCTION))
        debug = RateLimitingMiddleware(
            app=None, settings=Settings(**{**PRODUCTION, "DEBUG": True})
        )

        assert set(debug.rate_limits) == set(production.rate_limits)
        for path, limits in production.rate_limits.items():
            assert debug.rate_limits[path]["max_requests"] > limits["max_requests"]
            assert debug.rate_limits[path]["burst"] > limits["burst"]

    def test_debug_limits_applied_per_path(self):
        """DEBUG 模式下各類路徑實際套用的限制"""
        debug = RateLimitingMiddleware(
            app=None, settings=Settings(**{**PRODUCTION, "DEBUG": True})
        )
        expected = {
            "/api/auth/login": {"window": 60, "max_requests": 100, "burst": 50},
            "/api/auth/register": {"window": 300, "max_requests": 50, "burst": 25},
            "/api/rooms": {"window": 60, "max_requests": 200, "burst": 100},
            "/api/files/upload/image": {
                "window": 300,
                "max_requests": 100,
                "burst": 50,
            },
            "/ws/room-1": {"window": 60, "max_requests": 50, "burst": 20},
            "/": {"window": 3600, "max_requests": 5000, "burst": 500},
        }

        assert {path: debug._get_rate_limit_config(path) for path in expected} == (
            expected
        )

    def test_trusted_proxies_parsed_from_settings(self):
        middleware = RateLimitingMiddleware(
            app=None,
            settings=Settings(**{**PRODUCTION, "TRUSTED_PROXIES": " 10.0.0.1, ,::1 "}),
        )

        assert middleware.trusted_proxies == {"10.0.0.1", "::1"}

    def test_app_registers_rate_limiting(self):
        from app.main import app

        assert RateLimitingMiddleware in [m.cls for m in app.user_middleware]
