"""Redis 連線管理模組"""
import redis.asyncio as redis
from typing import Optional
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    """Redis 連線管理器"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """建立 Redis 連線"""
        if self.redis_client is None:
            try:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    password=settings.REDIS_PASSWORD,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=settings.REDIS_MAX_CONNECTIONS
                )
                # 測試連線
                await self.redis_client.ping()
                logger.info("Successfully connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    async def disconnect(self):
        """關閉 Redis 連線"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
            logger.info("Redis connection closed")
    
    async def get_client(self) -> redis.Redis:
        """獲取 Redis 客戶端實例"""
        if self.redis_client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self.redis_client

# 全局 Redis 管理器實例
_redis_manager = RedisManager()

async def init_redis():
    """初始化 Redis 連線"""
    await _redis_manager.connect()

async def close_redis():
    """關閉 Redis 連線"""
    await _redis_manager.disconnect()

async def get_redis() -> redis.Redis:
    """獲取 Redis 客戶端實例"""
    return await _redis_manager.get_client()