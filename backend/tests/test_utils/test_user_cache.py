"""測試使用者快取工具"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.utils.user_cache import (
    CACHE_KEY_PREFIX,
    fetch_user_with_cache,
    get_cached_user,
    invalidate_user_cache,
    set_cached_user,
)


def _make_user_dict(user_id: str = "abc123") -> dict:
    """建立測試用的使用者 dict"""
    return {
        "_id": user_id,
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "avatar": None,
        "is_active": True,
        "hashed_password": "hashed_secret",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "updated_at": datetime(2024, 1, 1, tzinfo=UTC),
    }


class TestGetCachedUser:
    """測試 get_cached_user"""

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """快取命中時回傳解析後的 dict"""
        user_data = {"_id": "abc123", "username": "testuser", "is_active": True}
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(user_data))

        with patch("app.utils.user_cache.get_redis", return_value=mock_redis):
            result = await get_cached_user("abc123")

        assert result == user_data
        mock_redis.get.assert_called_once_with(f"{CACHE_KEY_PREFIX}:abc123")

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """快取未命中時回傳 None"""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.utils.user_cache.get_redis", return_value=mock_redis):
            result = await get_cached_user("abc123")

        assert result is None

    @pytest.mark.asyncio
    async def test_redis_down_returns_none(self):
        """Redis 不可用時回傳 None（fail-open）"""
        with patch(
            "app.utils.user_cache.get_redis", side_effect=RuntimeError("Redis down")
        ):
            result = await get_cached_user("abc123")

        assert result is None


class TestSetCachedUser:
    """測試 set_cached_user"""

    @pytest.mark.asyncio
    async def test_strips_hashed_password(self):
        """存入 Redis 的資料不含 hashed_password"""
        user_dict = _make_user_dict()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.utils.user_cache.get_redis", return_value=mock_redis):
            await set_cached_user("abc123", user_dict)

        # 取得實際存入 Redis 的 JSON
        call_args = mock_redis.set.call_args
        stored_json = call_args[0][1]
        stored_data = json.loads(stored_json)

        assert "hashed_password" not in stored_data
        assert stored_data["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_sets_ttl(self):
        """確認 set 帶有正確的 TTL"""
        user_dict = _make_user_dict()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.utils.user_cache.get_redis", return_value=mock_redis):
            await set_cached_user("abc123", user_dict)

        call_args = mock_redis.set.call_args
        assert call_args[1]["ex"] == 300  # USER_CACHE_TTL 預設值

    @pytest.mark.asyncio
    async def test_correct_cache_key(self):
        """確認使用正確的快取 key"""
        user_dict = _make_user_dict()
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        with patch("app.utils.user_cache.get_redis", return_value=mock_redis):
            await set_cached_user("abc123", user_dict)

        call_args = mock_redis.set.call_args
        assert call_args[0][0] == f"{CACHE_KEY_PREFIX}:abc123"

    @pytest.mark.asyncio
    async def test_redis_down_no_exception(self):
        """Redis 不可用時不拋出例外"""
        with patch(
            "app.utils.user_cache.get_redis", side_effect=RuntimeError("Redis down")
        ):
            # 不應拋出例外
            await set_cached_user("abc123", _make_user_dict())


class TestInvalidateUserCache:
    """測試 invalidate_user_cache"""

    @pytest.mark.asyncio
    async def test_deletes_correct_key(self):
        """確認刪除正確的快取 key"""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()

        with patch("app.utils.user_cache.get_redis", return_value=mock_redis):
            await invalidate_user_cache("abc123")

        mock_redis.delete.assert_called_once_with(f"{CACHE_KEY_PREFIX}:abc123")

    @pytest.mark.asyncio
    async def test_redis_down_no_exception(self):
        """Redis 不可用時不拋出例外"""
        with patch(
            "app.utils.user_cache.get_redis", side_effect=RuntimeError("Redis down")
        ):
            # 不應拋出例外
            await invalidate_user_cache("abc123")


class TestFetchUserWithCache:
    """測試 fetch_user_with_cache（cache-first 統一流程）"""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_db(self):
        """快取命中時不查 MongoDB"""
        cached_user = {"_id": "abc123", "username": "testuser", "is_active": True}

        with (
            patch(
                "app.utils.user_cache.get_cached_user",
                new_callable=AsyncMock,
                return_value=cached_user,
            ),
            patch("app.utils.user_cache.get_database") as mock_get_db,
        ):
            result = await fetch_user_with_cache("abc123")

        assert result == cached_user
        mock_get_db.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db_and_caches(self):
        """快取未命中時查 MongoDB 並寫入快取"""
        from app.models.user import UserInDB

        mock_user = UserInDB(
            _id="507f1f77bcf86cd799439011",
            username="testuser",
            email="test@example.com",
            hashed_password="secret",
            is_active=True,
        )

        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = mock_user

        with (
            patch(
                "app.utils.user_cache.get_cached_user",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.utils.user_cache.get_database",
                new_callable=AsyncMock,
            ),
            patch(
                "app.utils.user_cache.UserRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.utils.user_cache.set_cached_user", new_callable=AsyncMock
            ) as mock_set,
        ):
            result = await fetch_user_with_cache("507f1f77bcf86cd799439011")

        assert result["_id"] == "507f1f77bcf86cd799439011"
        assert result["username"] == "testuser"
        assert "hashed_password" not in result
        mock_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_not_found_returns_none(self):
        """使用者不存在時回傳 None"""
        mock_repo = AsyncMock()
        mock_repo.get_by_id.return_value = None

        with (
            patch(
                "app.utils.user_cache.get_cached_user",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.utils.user_cache.get_database",
                new_callable=AsyncMock,
            ),
            patch(
                "app.utils.user_cache.UserRepository",
                return_value=mock_repo,
            ),
        ):
            result = await fetch_user_with_cache("507f1f77bcf86cd799439099")

        assert result is None
