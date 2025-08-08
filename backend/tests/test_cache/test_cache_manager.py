"""快取管理器測試"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cache.cache_manager import CacheKey, CacheManager, CacheSerializer


@pytest.fixture
def mock_redis():
    """模擬 Redis 客戶端"""
    redis_mock = AsyncMock()

    # 設定基本方法的預設行為
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = 1
    redis_mock.expire.return_value = True
    redis_mock.ttl.return_value = 3600
    redis_mock.mget.return_value = []
    redis_mock.mset.return_value = True
    redis_mock.scan_iter.return_value = []
    redis_mock.info.return_value = {"connected_clients": 1}

    return redis_mock


@pytest.fixture
def cache_manager(mock_redis):
    """快取管理器實例"""
    return CacheManager(mock_redis)


@pytest.mark.unit
class TestCacheKey:
    """快取鍵生成器測試"""

    def test_user_key(self):
        """測試用戶鍵生成"""
        assert CacheKey.user("123") == "user:123"

    def test_room_key(self):
        """測試房間鍵生成"""
        assert CacheKey.room("abc") == "room:abc"

    def test_room_members_key(self):
        """測試房間成員鍵生成"""
        assert CacheKey.room_members("abc") == "room:members:abc"

    def test_messages_key(self):
        """測試訊息鍵生成"""
        assert CacheKey.messages("abc", 1) == "messages:abc:page:1"
        assert CacheKey.messages("abc", 2) == "messages:abc:page:2"

    def test_rate_limit_key(self):
        """測試速率限制鍵生成"""
        assert CacheKey.rate_limit("123", "/api/users") == "rate_limit:123:/api/users"


@pytest.mark.unit
class TestCacheSerializer:
    """快取序列化器測試"""

    def test_serialize_dict(self):
        """測試字典序列化"""
        data = {"name": "test", "value": 123}
        result = CacheSerializer.serialize(data)
        assert '"name": "test"' in result
        assert '"value": 123' in result

    def test_serialize_list(self):
        """測試列表序列化"""
        data = [1, 2, 3, "test"]
        result = CacheSerializer.serialize(data)
        assert "[1, 2, 3" in result
        assert '"test"]' in result

    def test_serialize_string(self):
        """測試字串序列化"""
        data = "test string"
        result = CacheSerializer.serialize(data)
        assert result == "test string"

    def test_serialize_number(self):
        """測試數字序列化"""
        assert CacheSerializer.serialize(123) == "123"
        assert CacheSerializer.serialize(45.67) == "45.67"

    def test_serialize_none(self):
        """測試 None 序列化"""
        assert CacheSerializer.serialize(None) == ""

    def test_deserialize_json(self):
        """測試 JSON 反序列化"""
        data = '{"name": "test", "value": 123}'
        result = CacheSerializer.deserialize(data)
        assert result == {"name": "test", "value": 123}

    def test_deserialize_string(self):
        """測試字串反序列化"""
        data = "simple string"
        result = CacheSerializer.deserialize(data)
        assert result == "simple string"

    def test_deserialize_with_type(self):
        """測試指定類型反序列化"""
        data = "123"
        result = CacheSerializer.deserialize(data, int)
        assert result == 123
        assert isinstance(result, int)


@pytest.mark.unit
class TestCacheManager:
    """快取管理器測試"""

    @pytest.mark.asyncio
    async def test_get_existing_value(self, cache_manager, mock_redis):
        """測試獲取存在的快取值"""
        mock_redis.get.return_value = b'{"test": "value"}'

        result = await cache_manager.get("test_key")

        mock_redis.get.assert_called_once_with("test_key")
        assert result == {"test": "value"}
        assert cache_manager._stats["hits"] == 1
        assert cache_manager._stats["misses"] == 0

    @pytest.mark.asyncio
    async def test_get_nonexistent_value(self, cache_manager, mock_redis):
        """測試獲取不存在的快取值"""
        mock_redis.get.return_value = None

        result = await cache_manager.get("test_key")

        mock_redis.get.assert_called_once_with("test_key")
        assert result is None
        assert cache_manager._stats["hits"] == 0
        assert cache_manager._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_set_value(self, cache_manager, mock_redis):
        """測試設定快取值"""
        test_data = {"test": "value"}

        result = await cache_manager.set("test_key", test_data, 1800)

        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args[0]
        assert args[0] == "test_key"
        assert args[1] == 1800
        assert "test" in args[2]
        assert result is True
        assert cache_manager._stats["sets"] == 1

    @pytest.mark.asyncio
    async def test_delete_value(self, cache_manager, mock_redis):
        """測試刪除快取值"""
        mock_redis.delete.return_value = 1

        result = await cache_manager.delete("test_key")

        mock_redis.delete.assert_called_once_with("test_key")
        assert result is True
        assert cache_manager._stats["deletes"] == 1

    @pytest.mark.asyncio
    async def test_exists(self, cache_manager, mock_redis):
        """測試檢查快取是否存在"""
        mock_redis.exists.return_value = 1

        result = await cache_manager.exists("test_key")

        mock_redis.exists.assert_called_once_with("test_key")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, cache_manager, mock_redis):
        """測試 get_or_set 快取命中"""
        mock_redis.get.return_value = b'{"cached": "value"}'
        factory_func = AsyncMock(return_value={"new": "value"})

        result = await cache_manager.get_or_set("test_key", factory_func)

        mock_redis.get.assert_called_once_with("test_key")
        factory_func.assert_not_called()
        assert result == {"cached": "value"}

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss(self, cache_manager, mock_redis):
        """測試 get_or_set 快取未命中"""
        mock_redis.get.return_value = None
        factory_func = AsyncMock(return_value={"new": "value"})

        result = await cache_manager.get_or_set("test_key", factory_func, 1800)

        mock_redis.get.assert_called_once_with("test_key")
        factory_func.assert_called_once()
        mock_redis.setex.assert_called_once()
        assert result == {"new": "value"}

    @pytest.mark.asyncio
    async def test_get_or_set_sync_factory(self, cache_manager, mock_redis):
        """測試 get_or_set 同步工廠函數"""
        mock_redis.get.return_value = None
        factory_func = MagicMock(return_value={"sync": "value"})

        result = await cache_manager.get_or_set("test_key", factory_func)

        factory_func.assert_called_once()
        assert result == {"sync": "value"}

    @pytest.mark.asyncio
    async def test_mget(self, cache_manager, mock_redis):
        """測試批量獲取快取"""
        mock_redis.mget.return_value = [
            b'{"key1": "value1"}',
            None,
            b'{"key3": "value3"}',
        ]
        keys = ["key1", "key2", "key3"]

        result = await cache_manager.mget(keys)

        mock_redis.mget.assert_called_once_with(keys)
        assert result == {"key1": {"key1": "value1"}, "key3": {"key3": "value3"}}
        assert cache_manager._stats["hits"] == 2
        assert cache_manager._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_mset(self, cache_manager, mock_redis):
        """測試批量設定快取"""
        mapping = {"key1": {"value": 1}, "key2": {"value": 2}}

        result = await cache_manager.mset(mapping, 1800)

        mock_redis.mset.assert_called_once()
        mock_redis.expire.assert_called()
        assert result is True
        assert cache_manager._stats["sets"] == 2

    @pytest.mark.asyncio
    async def test_clear_user_cache(self, cache_manager, mock_redis):
        """測試清除用戶快取"""

        # 簡化測試，直接模擬 delete_pattern 的結果
        async def mock_delete_pattern(pattern):
            return 2  # 模擬刪除了 2 個鍵

        # 替換 delete_pattern 方法
        cache_manager.delete_pattern = mock_delete_pattern

        result = await cache_manager.clear_user_cache("123")

        # 每個模式都會刪除 2 個鍵，總共 4 個模式
        assert result == 8  # 2 * 4 = 8

    def test_reset_stats(self, cache_manager):
        """測試重置統計資訊"""
        cache_manager._stats["hits"] = 10
        cache_manager._stats["misses"] = 5

        cache_manager.reset_stats()

        assert cache_manager._stats["hits"] == 0
        assert cache_manager._stats["misses"] == 0
        assert cache_manager._stats["sets"] == 0
        assert cache_manager._stats["deletes"] == 0
        assert cache_manager._stats["errors"] == 0
