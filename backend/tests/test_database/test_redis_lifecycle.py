"""Redis 連線生命週期（真實 Redis；一律使用獨立的 manager，不碰 conftest 的全域連線）"""

import asyncio
import uuid

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings
from app.database import redis_conn
from app.database.redis_conn import (
    RedisManager,
    close_redis,
    get_redis,
    init_redis,
)
from tests.test_config import TestConfig


@pytest.fixture
def use_redis_url(monkeypatch):
    """讓 redis_conn 讀到指定的 REDIS_URL（換掉模組參照，不改全域 settings）"""

    def _use(url: str):
        monkeypatch.setattr(
            redis_conn, "settings", settings.model_copy(update={"REDIS_URL": url})
        )

    return _use


async def _server_connections_named(name: str, expected: int) -> int:
    """以全域連線查 CLIENT LIST；伺服器處理斷線是非同步的，短暫輪詢至符合預期"""
    observer = await get_redis()
    for _ in range(50):
        count = sum(1 for c in await observer.client_list() if c["name"] == name)
        if count == expected:
            break
        await asyncio.sleep(0.01)
    return count


@pytest.mark.asyncio
@pytest.mark.integration
class TestRedisManagerLifecycle:
    async def test_connect_fails_fast_when_server_unreachable(self, use_redis_url):
        use_redis_url("redis://localhost:1/0")
        manager = RedisManager()
        try:
            with pytest.raises(RedisConnectionError):
                await manager.connect()
        finally:
            await manager.disconnect()

    async def test_disconnect_releases_connection_and_allows_reconnect(
        self, use_redis_url
    ):
        name = f"lifecycle-{uuid.uuid4().hex[:8]}"
        use_redis_url(f"{TestConfig.TEST_REDIS_URL}?client_name={name}")
        manager = RedisManager()
        await manager.connect()
        try:
            assert await (await manager.get_client()).ping() is True
            assert await _server_connections_named(name, 1) == 1

            await manager.disconnect()

            with pytest.raises(RuntimeError, match="Redis not connected"):
                await manager.get_client()
            assert await _server_connections_named(name, 0) == 0

            await manager.connect()
            assert await (await manager.get_client()).ping() is True
        finally:
            await manager.disconnect()

    async def test_disconnect_without_connection_is_noop(self):
        manager = RedisManager()

        await manager.disconnect()

        with pytest.raises(RuntimeError, match="Redis not connected"):
            await manager.get_client()

    async def test_module_init_and_close(self, monkeypatch):
        """init_redis / close_redis 作用在模組層的 manager（此處換成獨立實例）"""
        manager = RedisManager()
        monkeypatch.setattr(redis_conn, "_redis_manager", manager)
        try:
            await init_redis()
            assert await (await get_redis()).ping() is True

            await close_redis()

            with pytest.raises(RuntimeError, match="Redis not connected"):
                await get_redis()
        finally:
            await manager.disconnect()
