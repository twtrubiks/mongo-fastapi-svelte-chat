"""測試專用資料庫管理器"""

import logging

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger(__name__)


class MongoDBTestManager:
    """測試專用的 MongoDB 連線管理器"""

    def __init__(self):
        self.client: AsyncMongoClient | None = None
        self.database: AsyncDatabase | None = None
        self._database_name: str | None = None

    async def connect(self, mongodb_url: str, database_name: str):
        """建立 MongoDB 連線"""
        if self.client is not None:
            await self.disconnect()

        try:
            self.client = AsyncMongoClient(mongodb_url)
            # 測試連線
            await self.client.admin.command("ping")
            self.database = self.client[database_name]
            self._database_name = database_name
            logger.info(f"Test database connected: {database_name}")
        except Exception as e:
            logger.error(f"Failed to connect to test database: {e}")
            raise

    async def disconnect(self):
        """關閉 MongoDB 連線"""
        if self.client:
            await self.client.close()
            self.client = None
            self.database = None
            self._database_name = None
            logger.info("Test database connection closed")

    async def clean_database(self):
        """清理測試資料庫"""
        if self.database is not None and self._database_name:
            try:
                collections = await self.database.list_collection_names()
                for collection_name in collections:
                    await self.database[collection_name].delete_many({})
                logger.info(f"Cleaned test database: {self._database_name}")
            except Exception as e:
                logger.error(f"Failed to clean test database: {e}")

    async def get_database(self) -> AsyncDatabase:
        """獲取資料庫實例"""
        if self.database is None:
            raise RuntimeError("Test database not connected")
        return self.database
