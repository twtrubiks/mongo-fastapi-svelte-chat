"""快取操作的進階測試"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from datetime import datetime, UTC, timedelta


class TestCacheOperations:
    """測試快取的各種操作"""
    
    def test_cache_hit_miss_tracking(self):
        """測試快取命中/未命中追蹤"""
        # Mock 快取管理器
        mock_redis = Mock()
        
        class CacheManager:
            def __init__(self, redis):
                self.redis = redis
                self.stats = {"hits": 0, "misses": 0}
            
            def get(self, key):
                value = self.redis.get(key)
                if value:
                    self.stats["hits"] += 1
                else:
                    self.stats["misses"] += 1
                return value
            
            def set(self, key, value, ex=None):
                return self.redis.set(key, value, ex=ex)
            
            def get_hit_rate(self):
                total = self.stats["hits"] + self.stats["misses"]
                if total == 0:
                    return 0
                return self.stats["hits"] / total
        
        # 設置 Mock 行為
        mock_redis.get.side_effect = ["value1", None, "value3", None, "value5"]
        mock_redis.set.return_value = True
        
        # 測試
        cache = CacheManager(mock_redis)
        
        # 執行一些快取操作
        assert cache.get("key1") == "value1"  # hit
        assert cache.get("key2") is None      # miss
        assert cache.get("key3") == "value3"  # hit
        assert cache.get("key4") is None      # miss
        assert cache.get("key5") == "value5"  # hit
        
        # 驗證統計
        assert cache.stats["hits"] == 3
        assert cache.stats["misses"] == 2
        assert cache.get_hit_rate() == 0.6
    
    def test_cache_expiration_handling(self):
        """測試快取過期處理"""
        mock_redis = Mock()
        
        class ExpiringCache:
            def __init__(self, redis):
                self.redis = redis
                self.default_ttl = 300
            
            def set_with_expiry(self, key, value, ttl=None):
                if ttl is None:
                    ttl = self.default_ttl
                
                # 設置值和過期時間
                self.redis.set(key, json.dumps(value))
                self.redis.expire(key, ttl)
                return True
            
            def get_with_ttl(self, key):
                value = self.redis.get(key)
                if not value:
                    return None, None
                
                ttl = self.redis.ttl(key)
                return json.loads(value), ttl
        
        # 設置 Mock
        mock_redis.set.return_value = True
        mock_redis.expire.return_value = True
        mock_redis.get.return_value = '{"data": "test"}'
        mock_redis.ttl.return_value = 150
        
        # 測試
        cache = ExpiringCache(mock_redis)
        
        # 設置帶過期的值
        assert cache.set_with_expiry("key1", {"data": "test"}, 300) is True
        
        # 獲取值和剩餘時間
        value, ttl = cache.get_with_ttl("key1")
        assert value["data"] == "test"
        assert ttl == 150
        
        # 驗證調用
        mock_redis.expire.assert_called_once_with("key1", 300)
    
    def test_cache_invalidation_patterns(self):
        """測試快取失效模式"""
        mock_redis = Mock()
        
        class CacheInvalidator:
            def __init__(self, redis):
                self.redis = redis
            
            def invalidate_pattern(self, pattern):
                """按模式失效快取"""
                # 掃描匹配的鍵
                keys = self.redis.scan_iter(match=pattern)
                deleted = 0
                
                for key in keys:
                    if self.redis.delete(key):
                        deleted += 1
                
                return deleted
            
            def invalidate_tags(self, tags):
                """按標籤失效快取"""
                all_keys = set()
                
                for tag in tags:
                    # 獲取標籤對應的鍵
                    tag_keys = self.redis.smembers(f"tag:{tag}")
                    all_keys.update(tag_keys)
                
                deleted = 0
                for key in all_keys:
                    if self.redis.delete(key):
                        deleted += 1
                        # 清理標籤關聯
                        for tag in tags:
                            self.redis.srem(f"tag:{tag}", key)
                
                return deleted
        
        # 設置 Mock
        mock_redis.scan_iter.return_value = ["user:1", "user:2", "user:3"]
        mock_redis.delete.return_value = 1
        mock_redis.smembers.return_value = {"cache:1", "cache:2"}
        mock_redis.srem.return_value = 1
        
        # 測試
        invalidator = CacheInvalidator(mock_redis)
        
        # 測試模式失效
        deleted = invalidator.invalidate_pattern("user:*")
        assert deleted == 3
        
        # 測試標籤失效
        deleted = invalidator.invalidate_tags(["user_data", "profile"])
        assert deleted == 2
    
    def test_cache_warming_strategy(self):
        """測試快取預熱策略"""
        mock_redis = Mock()
        mock_db = Mock()
        
        class CacheWarmer:
            def __init__(self, redis, db):
                self.redis = redis
                self.db = db
            
            def warm_user_cache(self, user_ids):
                """預熱用戶快取"""
                warmed = 0
                
                # 批量從資料庫獲取
                users = self.db.get_users_by_ids(user_ids)
                
                # 批量寫入快取
                pipe = self.redis.pipeline()
                for user in users:
                    key = f"user:{user['id']}"
                    pipe.set(key, json.dumps(user), ex=3600)
                    warmed += 1
                
                pipe.execute()
                return warmed
            
            def warm_frequently_accessed(self, top_n=100):
                """預熱高頻訪問數據"""
                # 獲取訪問頻率最高的鍵
                hot_keys = self.db.get_hot_keys(top_n)
                
                warmed = 0
                for key_info in hot_keys:
                    data = self.db.get_data(key_info["key"])
                    if data:
                        self.redis.set(
                            key_info["key"],
                            json.dumps(data),
                            ex=key_info.get("ttl", 3600)
                        )
                        warmed += 1
                
                return warmed
        
        # 設置 Mock
        mock_db.get_users_by_ids.return_value = [
            {"id": "1", "name": "User1"},
            {"id": "2", "name": "User2"}
        ]
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = True
        
        mock_db.get_hot_keys.return_value = [
            {"key": "hot:1", "ttl": 7200},
            {"key": "hot:2", "ttl": 3600}
        ]
        mock_db.get_data.return_value = {"data": "hot"}
        mock_redis.set.return_value = True
        
        # 測試
        warmer = CacheWarmer(mock_redis, mock_db)
        
        # 測試用戶快取預熱
        warmed = warmer.warm_user_cache(["1", "2"])
        assert warmed == 2
        assert mock_pipeline.set.call_count == 2
        
        # 測試高頻數據預熱
        warmed = warmer.warm_frequently_accessed(2)
        assert warmed == 2
    
    def test_distributed_cache_locking(self):
        """測試分散式快取鎖"""
        mock_redis = Mock()
        
        class DistributedLock:
            def __init__(self, redis, key, timeout=10):
                self.redis = redis
                self.key = f"lock:{key}"
                self.timeout = timeout
                self.identifier = None
            
            def acquire(self):
                """獲取鎖"""
                import uuid
                identifier = str(uuid.uuid4())
                
                # 嘗試設置鎖（NX: 只在不存在時設置）
                acquired = self.redis.set(
                    self.key,
                    identifier,
                    nx=True,
                    ex=self.timeout
                )
                
                if acquired:
                    self.identifier = identifier
                return acquired
            
            def release(self):
                """釋放鎖"""
                if not self.identifier:
                    return False
                
                # 使用 Lua 腳本確保原子性
                script = '''
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                '''
                
                return self.redis.eval(script, 1, self.key, self.identifier) == 1
            
            def extend(self, additional_time):
                """延長鎖時間"""
                if not self.identifier:
                    return False
                
                # 檢查鎖是否仍屬於我們
                if self.redis.get(self.key) == self.identifier:
                    return self.redis.expire(self.key, self.timeout + additional_time)
                return False
        
        # 設置 Mock
        mock_redis.set.return_value = True
        mock_redis.get.return_value = "test-uuid"
        mock_redis.eval.return_value = 1
        mock_redis.expire.return_value = True
        
        # 測試
        lock = DistributedLock(mock_redis, "resource1", timeout=30)
        
        # 測試獲取鎖
        assert lock.acquire() is True
        assert lock.identifier is not None
        
        # 設置 Mock 返回實際的 identifier
        mock_redis.get.return_value = lock.identifier
        
        # 測試延長鎖
        assert lock.extend(10) is True
        
        # 測試釋放鎖
        assert lock.release() is True
    
    def test_cache_batch_operations(self):
        """測試批量快取操作"""
        mock_redis = Mock()
        
        class BatchCache:
            def __init__(self, redis):
                self.redis = redis
            
            def mget_with_fallback(self, keys, fallback_func):
                """批量獲取，未命中的使用回調函數"""
                # 批量獲取
                values = self.redis.mget(keys)
                
                result = {}
                missing_keys = []
                
                # 處理結果
                for key, value in zip(keys, values):
                    if value:
                        result[key] = json.loads(value)
                    else:
                        missing_keys.append(key)
                
                # 處理未命中的鍵
                if missing_keys and fallback_func:
                    fallback_data = fallback_func(missing_keys)
                    
                    # 寫入快取
                    pipe = self.redis.pipeline()
                    for key, data in fallback_data.items():
                        result[key] = data
                        pipe.set(key, json.dumps(data), ex=300)
                    pipe.execute()
                
                return result
            
            def mset_with_tags(self, data_dict, tags=None):
                """批量設置並打標籤"""
                pipe = self.redis.pipeline()
                
                # 批量設置值
                for key, value in data_dict.items():
                    pipe.set(key, json.dumps(value), ex=3600)
                    
                    # 添加標籤
                    if tags:
                        for tag in tags:
                            pipe.sadd(f"tag:{tag}", key)
                
                results = pipe.execute()
                
                # 計算成功數量
                success_count = sum(1 for r in results if r)
                return success_count
        
        # 設置 Mock
        mock_redis.mget.return_value = ['{"data": "1"}', None, '{"data": "3"}']
        
        def mock_fallback(keys):
            return {key: {"data": f"fallback_{key}"} for key in keys}
        
        mock_pipeline = Mock()
        mock_redis.pipeline.return_value = mock_pipeline
        mock_pipeline.execute.return_value = [True, True, True, True]
        
        # 測試
        cache = BatchCache(mock_redis)
        
        # 測試批量獲取with fallback
        result = cache.mget_with_fallback(
            ["key1", "key2", "key3"],
            mock_fallback
        )
        
        assert result["key1"]["data"] == "1"
        assert result["key2"]["data"] == "fallback_key2"
        assert result["key3"]["data"] == "3"
        
        # 測試批量設置with標籤
        data = {"item1": {"value": 1}, "item2": {"value": 2}}
        success = cache.mset_with_tags(data, tags=["products", "featured"])
        assert success == 4  # 2個值 + 2個標籤