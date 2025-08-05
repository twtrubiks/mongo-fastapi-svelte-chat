"""高層級快取管理器"""
import json
import asyncio
import logging
from typing import Any, Optional, Dict, List, Callable, TypeVar, Union
from datetime import datetime, timezone, timedelta
from functools import wraps
from redis.asyncio import Redis
from app.core.exceptions import CacheError

UTC = timezone.utc
logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheKey:
    """快取鍵生成器"""
    
    @staticmethod
    def user(user_id: str) -> str:
        return f"user:{user_id}"
    
    @staticmethod
    def room(room_id: str) -> str:
        return f"room:{room_id}"
    
    @staticmethod
    def room_members(room_id: str) -> str:
        return f"room:members:{room_id}"
    
    @staticmethod
    def user_rooms(user_id: str) -> str:
        return f"user:rooms:{user_id}"
    
    @staticmethod
    def messages(room_id: str, page: int = 1) -> str:
        return f"messages:{room_id}:page:{page}"
    
    @staticmethod
    def notifications(user_id: str) -> str:
        return f"notifications:{user_id}"
    
    @staticmethod
    def online_users(room_id: str) -> str:
        return f"online_users:{room_id}"
    
    @staticmethod
    def rate_limit(user_id: str, endpoint: str) -> str:
        return f"rate_limit:{user_id}:{endpoint}"
    
    @staticmethod
    def session(session_id: str) -> str:
        return f"session:{session_id}"


class CacheSerializer:
    """快取序列化器"""
    
    @staticmethod
    def serialize(data: Any) -> str:
        """序列化資料為 JSON 字串"""
        if data is None:
            return ""
        
        try:
            if isinstance(data, (dict, list)):
                return json.dumps(data, ensure_ascii=False, default=str)
            elif isinstance(data, (str, int, float, bool)):
                return str(data)
            else:
                # 對於其他對象，嘗試轉換為字典
                if hasattr(data, '__dict__'):
                    return json.dumps(data.__dict__, ensure_ascii=False, default=str)
                else:
                    return str(data)
        except Exception as e:
            logger.warning(f"序列化失敗: {e}, 資料類型: {type(data)}")
            return str(data)
    
    @staticmethod
    def deserialize(data: str, target_type: type = None) -> Any:
        """反序列化 JSON 字串為 Python 對象"""
        if not data:
            return None
        
        try:
            # 嘗試 JSON 反序列化
            parsed = json.loads(data)
            
            # 如果指定了目標類型，嘗試轉換
            if target_type:
                if target_type == str:
                    return str(parsed)
                elif target_type == int:
                    return int(parsed)
                elif target_type == float:
                    return float(parsed)
                elif target_type == bool:
                    return bool(parsed)
                elif target_type in (list, dict):
                    return parsed
            
            return parsed
            
        except json.JSONDecodeError:
            # 如果不是 JSON，直接返回字串
            return data
        except Exception as e:
            logger.warning(f"反序列化失敗: {e}, 資料: {data[:100]}...")
            return data


class CacheManager:
    """高層級快取管理器"""
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.serializer = CacheSerializer()
        self.default_ttl = 3600  # 1 小時
        self.key_generator = CacheKey()
        
        # 統計資訊
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }
    
    async def get(self, key: str, target_type: type = None) -> Optional[Any]:
        """獲取快取值"""
        try:
            value = await self.redis.get(key)
            if value is None:
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            return self.serializer.deserialize(value.decode('utf-8'), target_type)
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"快取讀取失敗 key={key}: {e}")
            raise CacheError(f"快取讀取失敗: {e}")
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """設定快取值"""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = self.serializer.serialize(value)
            
            await self.redis.setex(key, ttl, serialized_value)
            self._stats["sets"] += 1
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"快取寫入失敗 key={key}: {e}")
            raise CacheError(f"快取寫入失敗: {e}")
    
    async def delete(self, key: str) -> bool:
        """刪除快取"""
        try:
            result = await self.redis.delete(key)
            if result > 0:
                self._stats["deletes"] += 1
            return result > 0
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"快取刪除失敗 key={key}: {e}")
            raise CacheError(f"快取刪除失敗: {e}")
    
    async def exists(self, key: str) -> bool:
        """檢查快取是否存在"""
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"快取存在性檢查失敗 key={key}: {e}")
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """設定快取過期時間"""
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error(f"設定快取過期時間失敗 key={key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """獲取快取剩餘時間"""
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"獲取快取 TTL 失敗 key={key}: {e}")
            return -1
    
    async def get_or_set(self, key: str, factory_func: Callable, 
                        ttl: Optional[int] = None, 
                        target_type: type = None) -> Any:
        """獲取快取，如果不存在則執行工廠函數並快取結果"""
        try:
            # 先嘗試從快取獲取
            cached_value = await self.get(key, target_type)
            if cached_value is not None:
                return cached_value
            
            # 快取不存在，執行工廠函數
            if asyncio.iscoroutinefunction(factory_func):
                value = await factory_func()
            else:
                value = factory_func()
            
            # 如果值不為空，則快取
            if value is not None:
                await self.set(key, value, ttl)
            
            return value
            
        except Exception as e:
            logger.error(f"get_or_set 操作失敗 key={key}: {e}")
            # 如果快取操作失敗，直接執行工廠函數
            if asyncio.iscoroutinefunction(factory_func):
                return await factory_func()
            else:
                return factory_func()
    
    async def mget(self, keys: List[str], target_type: type = None) -> Dict[str, Any]:
        """批量獲取快取"""
        try:
            if not keys:
                return {}
            
            values = await self.redis.mget(keys)
            result = {}
            
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self.serializer.deserialize(value.decode('utf-8'), target_type)
                    self._stats["hits"] += 1
                else:
                    self._stats["misses"] += 1
            
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"批量快取讀取失敗 keys={keys}: {e}")
            return {}
    
    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量設定快取"""
        try:
            if not mapping:
                return True
            
            # 序列化所有值
            serialized_mapping = {}
            for key, value in mapping.items():
                serialized_mapping[key] = self.serializer.serialize(value)
            
            # 批量設定
            await self.redis.mset(serialized_mapping)
            
            # 如果指定了 TTL，批量設定過期時間
            if ttl:
                await asyncio.gather(*[
                    self.redis.expire(key, ttl) 
                    for key in mapping.keys()
                ])
            
            self._stats["sets"] += len(mapping)
            return True
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"批量快取寫入失敗: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """根據模式刪除快取"""
        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                deleted = await self.redis.delete(*keys)
                self._stats["deletes"] += deleted
                return deleted
            
            return 0
            
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"模式刪除快取失敗 pattern={pattern}: {e}")
            return 0
    
    async def clear_user_cache(self, user_id: str) -> int:
        """清除用戶相關的所有快取"""
        patterns = [
            f"user:{user_id}*",
            f"*:user:{user_id}*",
            f"notifications:{user_id}*",
            f"session:*:{user_id}*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = await self.delete_pattern(pattern)
            total_deleted += deleted
        
        return total_deleted
    
    async def clear_room_cache(self, room_id: str) -> int:
        """清除房間相關的所有快取"""
        patterns = [
            f"room:{room_id}*",
            f"messages:{room_id}*",
            f"online_users:{room_id}*"
        ]
        
        total_deleted = 0
        for pattern in patterns:
            deleted = await self.delete_pattern(pattern)
            total_deleted += deleted
        
        return total_deleted
    
    async def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計資訊"""
        try:
            info = await self.redis.info()
            memory_info = await self.redis.info("memory")
            
            return {
                "operation_stats": self._stats.copy(),
                "hit_rate": self._stats["hits"] / max(self._stats["hits"] + self._stats["misses"], 1),
                "redis_info": {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_human": memory_info.get("used_memory_human", "unknown"),
                    "keyspace": info.get("db0", {})
                },
                "timestamp": datetime.now(UTC).isoformat()
            }
            
        except Exception as e:
            logger.error(f"獲取快取統計資訊失敗: {e}")
            return {"error": str(e)}
    
    def reset_stats(self):
        """重置統計資訊"""
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "errors": 0
        }


def cache_result(key_template: str, ttl: int = 3600, target_type: type = None):
    """快取裝飾器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 這裡需要從依賴注入容器獲取 CacheManager
            # 為了簡化，暫時跳過實現
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# 便利函數
async def create_cache_manager(redis_client: Redis) -> CacheManager:
    """創建快取管理器實例"""
    return CacheManager(redis_client)