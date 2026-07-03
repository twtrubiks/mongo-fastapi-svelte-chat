"""Rate Limiting 中間件測試

涵蓋兩類回歸：
1. 同秒摺疊 — ZSET member 若不唯一，同一秒內的請求會被 ZADD 摺疊成一筆，計數失真
2. 客戶端識別符 — X-Forwarded-For 只信任可信 proxy、Bearer token 分桶、直連偽造 XFF 無效
"""

import uuid

import pytest
from starlette.requests import Request

from app.auth.jwt_handler import create_access_token
from app.config import Settings
from app.database.redis_conn import get_redis
from app.middleware.rate_limiting import (
    RateLimitingMiddleware,
    SlidingWindowRateLimiter,
)


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

    @pytest.fixture
    async def redis_client(self):
        try:
            client = await get_redis()
            await client.ping()
        except Exception:
            pytest.skip("Redis 不可用，跳過計數測試")
        return client

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
