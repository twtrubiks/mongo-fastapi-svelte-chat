"""MongoDB 資料庫連線的基礎測試"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pymongo.errors import InvalidOperation, ServerSelectionTimeoutError

from app.database import mongodb as mongodb_module
from app.database.mongodb import (
    MongoDBManager,
    close_database,
    get_client,
    get_database,
    init_database,
    mongo_client,
)
from tests.test_config import TestConfig

# 關閉的埠：連線立即被拒；縮短伺服器選擇逾時（實測約 0.5 秒失敗）
UNREACHABLE_URL = "mongodb://localhost:1/?serverSelectionTimeoutMS=100"


@pytest.mark.asyncio
@pytest.mark.integration
class TestMongoDBManagerLifecycle:
    """連線生命週期（真實 MongoDB；一律使用獨立的 manager，不碰 conftest 的全域連線）"""

    async def test_connect_fails_fast_when_server_unreachable(self):
        manager = MongoDBManager()
        try:
            with pytest.raises(ServerSelectionTimeoutError):
                await manager.connect(UNREACHABLE_URL, "unused")
            with pytest.raises(RuntimeError, match="Database not connected"):
                await manager.get_database()
        finally:
            await manager.disconnect()

    async def test_disconnect_closes_client_and_allows_reconnect(self):
        manager = MongoDBManager()
        await manager.connect(
            TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME
        )
        try:
            database = await manager.get_database()
            assert database.name == TestConfig.TEST_DATABASE_NAME
            assert (await database.command("ping"))["ok"] == 1

            await manager.disconnect()

            with pytest.raises(RuntimeError, match="Database not connected"):
                await manager.get_database()
            # 底層 client 已關閉，殘留的 database 參照不能再使用
            with pytest.raises(InvalidOperation):
                await database.command("ping")

            await manager.connect(
                TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME
            )
            reconnected = await manager.get_database()
            assert (await reconnected.command("ping"))["ok"] == 1
        finally:
            await manager.disconnect()

    async def test_disconnect_without_connection_is_noop(self):
        manager = MongoDBManager()

        await manager.disconnect()

        with pytest.raises(RuntimeError, match="Database not connected"):
            await manager.get_database()

    async def test_module_init_and_close(self, monkeypatch):
        """init_database / close_database 作用在模組層的 manager（此處換成獨立實例）"""
        manager = MongoDBManager()
        monkeypatch.setattr(mongodb_module, "_db_manager", manager)
        try:
            await init_database(
                TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME
            )
            assert (await (await get_database()).command("ping"))["ok"] == 1

            await close_database()

            assert get_client() is None
            with pytest.raises(RuntimeError, match="Database not connected"):
                await get_database()
        finally:
            await manager.disconnect()


class TestModuleFunctions:
    """測試模組級函數"""

    @pytest.mark.asyncio
    async def test_get_database_function(self):
        """測試 get_database 函數"""
        with patch("app.database.mongodb._db_manager") as mock_manager:
            mock_manager.get_database = AsyncMock(return_value=Mock())

            result = await get_database()

            assert result is not None
            mock_manager.get_database.assert_called_once()

    def test_get_client_function(self):
        """測試 get_client 函數"""
        with patch("app.database.mongodb._db_manager") as mock_manager:
            mock_client = Mock()
            mock_manager.client = mock_client

            result = get_client()

            assert result == mock_client

    def test_mongo_client_wrapper(self):
        """測試 MongoClientWrapper"""
        with patch("app.database.mongodb._db_manager") as mock_manager:
            mock_client = Mock()
            mock_manager.client = mock_client

            result = mongo_client.get_client()

            assert result == mock_client
