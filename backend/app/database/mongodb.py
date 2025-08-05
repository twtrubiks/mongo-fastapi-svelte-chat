"""MongoDB 資料庫連線模組

使用 pymongo AsyncMongoClient 提供異步資料庫連線功能
"""
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

class MongoDBManager:
    """MongoDB 連線管理器"""

    def __init__(self):
        self.client: Optional[AsyncMongoClient] = None
        self.database: Optional[AsyncDatabase] = None
        self._lock = asyncio.Lock()

    async def connect(self, mongodb_url: str, database_name: str = "chatroom"):
        """建立 MongoDB 連線"""
        async with self._lock:
            if self.client is None:
                try:
                    self.client = AsyncMongoClient(mongodb_url)
                    # 測試連線
                    await self.client.admin.command('ping')
                    self.database = self.client[database_name]
                    logger.info(f"Successfully connected to MongoDB: {database_name}")
                except Exception as e:
                    logger.error(f"Failed to connect to MongoDB: {e}")
                    raise

    async def disconnect(self):
        """關閉 MongoDB 連線"""
        async with self._lock:
            if self.client:
                await self.client.close()
                self.client = None
                self.database = None
                logger.info("MongoDB connection closed")

    async def get_database(self) -> AsyncDatabase:
        """獲取資料庫實例"""
        if self.database is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self.database

# 全局資料庫管理器實例
_db_manager = MongoDBManager()

async def init_database(mongodb_url: str, database_name: str = "chatroom"):
    """初始化資料庫連線"""
    await _db_manager.connect(mongodb_url, database_name)

async def close_database():
    """關閉資料庫連線"""
    await _db_manager.disconnect()

async def get_database() -> AsyncDatabase:
    """獲取資料庫實例"""
    return await _db_manager.get_database()

def get_client() -> Optional[AsyncMongoClient]:
    """獲取 MongoDB 客戶端"""
    return _db_manager.client

# 為了向後相容，提供 mongo_client 接口
class MongoClientWrapper:
    """MongoDB 客戶端包裝器，提供向後相容的接口"""
    
    def get_client(self) -> Optional[AsyncMongoClient]:
        """獲取 MongoDB 客戶端"""
        return _db_manager.client

# 全域 mongo_client 實例
mongo_client = MongoClientWrapper()