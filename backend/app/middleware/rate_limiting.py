"""Rate Limiting 中間件 - 使用滑動視窗演算法"""
import time
import asyncio
from typing import Dict, Optional, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
import redis.asyncio as redis
import json
import logging
from app.config import Settings

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Rate limit 異常"""
    def __init__(self, message: str, retry_after: int):
        self.message = message
        self.retry_after = retry_after
        super().__init__(message)


class SlidingWindowRateLimiter:
    """滑動視窗 Rate Limiter"""
    
    def __init__(self, redis_client: redis.Redis, settings: Settings):
        self.redis = redis_client
        self.settings = settings
        
    async def is_allowed(
        self, 
        key: str, 
        window_size: int, 
        max_requests: int,
        burst_size: Optional[int] = None
    ) -> Tuple[bool, int, int]:
        """
        檢查請求是否被允許
        
        Args:
            key: 唯一識別鍵（通常是 IP 或 user_id）
            window_size: 時間窗口大小（秒）
            max_requests: 最大請求數
            burst_size: 突發請求限制
            
        Returns:
            Tuple[是否允許, 剩餘請求數, 重置時間（秒）]
        """
        now = int(time.time())
        window_start = now - window_size
        
        # Redis pipeline 提高效能
        pipe = self.redis.pipeline()
        
        # 滑動視窗清理：移除過期的請求記錄
        pipe.zremrangebyscore(key, 0, window_start)
        
        # 獲取當前時間窗口內的請求數
        pipe.zcard(key)
        
        # 檢查突發請求限制
        if burst_size:
            burst_window_start = now - 60  # 1分鐘突發視窗
            pipe.zcount(key, burst_window_start, now)
        
        results = await pipe.execute()
        current_requests = results[1]
        burst_requests = results[2] if burst_size else 0
        
        # 檢查突發限制
        if burst_size and burst_requests >= burst_size:
            remaining = 0
            reset_time = 60 - (now % 60)
            return False, remaining, reset_time
        
        # 檢查常規限制
        if current_requests >= max_requests:
            remaining = 0
            reset_time = window_size - (now % window_size)
            return False, remaining, reset_time
        
        # 記錄這次請求
        await self.redis.zadd(key, {str(now): now})
        await self.redis.expire(key, window_size + 1)
        
        remaining = max_requests - current_requests - 1
        reset_time = window_size - (now % window_size)
        
        return True, remaining, reset_time
    
    async def get_rate_limit_status(
        self, 
        key: str, 
        window_size: int, 
        max_requests: int
    ) -> Dict[str, int]:
        """獲取 rate limit 狀態"""
        now = int(time.time())
        window_start = now - window_size
        
        current_requests = await self.redis.zcount(key, window_start, now)
        remaining = max(0, max_requests - current_requests)
        reset_time = window_size - (now % window_size)
        
        return {
            "requests_made": current_requests,
            "requests_remaining": remaining,
            "reset_time": reset_time,
            "window_size": window_size,
            "max_requests": max_requests
        }


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Rate Limiting 中間件"""
    
    def __init__(self, app, redis_client: redis.Redis = None, settings: Settings = None):
        super().__init__(app)
        self.redis_client = redis_client
        self.settings = settings or Settings()
        self.limiter = None
        
        # 如果 Redis 客戶端已提供，立即初始化
        if redis_client:
            self.limiter = SlidingWindowRateLimiter(redis_client, self.settings)
        
        # 不同端點的 rate limit 配置
        # DEBUG 模式下使用更寬鬆的限制
        if self.settings.DEBUG:
            self.rate_limits = {
                # 認證相關 - DEBUG 模式非常寬鬆
                "/api/auth/login": {"window": 60, "max_requests": 100, "burst": 50},  # 1分鐘100次
                "/api/auth/register": {"window": 300, "max_requests": 50, "burst": 25},  # 5分鐘50次
                
                # API 端點 - DEBUG 模式寬鬆限制
                "/api/": {"window": 60, "max_requests": 200, "burst": 100},
                
                # 檔案上傳 - DEBUG 模式寬鬆
                "/api/files/upload": {"window": 300, "max_requests": 100, "burst": 50},
                
                # WebSocket 連接 - DEBUG 模式寬鬆
                "/ws": {"window": 60, "max_requests": 50, "burst": 20},
                
                # 預設限制 - DEBUG 模式寬鬆
                "default": {"window": 3600, "max_requests": 5000, "burst": 500}
            }
        else:
            self.rate_limits = {
                # 認證相關 - 生產環境限制
                "/api/auth/login": {"window": 300, "max_requests": 20, "burst": 10},  # 5分鐘20次，突發10次
                "/api/auth/register": {"window": 3600, "max_requests": 10, "burst": 5},  # 1小時10次，突發5次
                
                # API 端點 - 中等限制
                "/api/": {"window": 60, "max_requests": self.settings.RATE_LIMIT_REQUESTS_PER_MINUTE, "burst": self.settings.RATE_LIMIT_BURST_SIZE},
                
                # 檔案上傳 - 較寬鬆但有突發限制
                "/api/files/upload": {"window": 300, "max_requests": 20, "burst": 5},  # 5分鐘20次
                
                # WebSocket 連接 - 特殊處理
                "/ws": {"window": 60, "max_requests": 10, "burst": 3},
                
                # 預設限制
                "default": {"window": 3600, "max_requests": self.settings.RATE_LIMIT_REQUESTS_PER_HOUR, "burst": 50}
            }
    
    def _get_client_identifier(self, request: Request) -> str:
        """獲取客戶端唯一識別符"""
        # 優先使用認證使用者 ID
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # 檢查 X-Forwarded-For 標頭（代理伺服器）
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # 取第一個 IP（原始客戶端 IP）
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            # 使用直接連接的 IP
            client_ip = request.client.host if request.client else "unknown"
        
        return f"ip:{client_ip}"
    
    def _get_rate_limit_config(self, path: str) -> Dict[str, int]:
        """根據路徑獲取 rate limit 配置"""
        # 精確匹配
        if path in self.rate_limits:
            return self.rate_limits[path]
        
        # 前綴匹配
        for pattern, config in self.rate_limits.items():
            if path.startswith(pattern):
                return config
        
        # 使用預設配置
        return self.rate_limits["default"]
    
    def _should_skip_rate_limiting(self, request: Request) -> bool:
        """檢查是否應該跳過 rate limiting"""
        path = request.url.path
        
        # 跳過健康檢查和靜態檔案
        skip_paths = ["/health", "/docs", "/redoc", "/openapi.json", "/static/"]
        
        for skip_path in skip_paths:
            if path.startswith(skip_path):
                return True
        
        return False
    
    async def _initialize_limiter(self):
        """延遲初始化 limiter（如果尚未初始化）"""
        if self.limiter is None and self.redis_client is None:
            # 嘗試獲取 Redis 客戶端
            try:
                from app.database.redis_conn import get_redis
                self.redis_client = await get_redis()
                self.limiter = SlidingWindowRateLimiter(self.redis_client, self.settings)
            except Exception as e:
                logger.warning(f"Failed to initialize rate limiter: {e}")
                return False
        return True
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """處理 rate limiting"""
        # 檢查是否應該跳過
        if self._should_skip_rate_limiting(request):
            return await call_next(request)
        
        # 嘗試初始化 limiter
        if not await self._initialize_limiter():
            # 如果初始化失敗，允許請求通過（fail-open）
            logger.warning("Rate limiter not available, allowing request")
            return await call_next(request)
        
        try:
            # 獲取客戶端識別符和配置
            client_id = self._get_client_identifier(request)
            path = request.url.path
            config = self._get_rate_limit_config(path)
            
            # 生成 rate limit key
            rate_limit_key = f"rate_limit:{client_id}:{path}"
            
            # 檢查 rate limit
            allowed, remaining, reset_time = await self.limiter.is_allowed(
                rate_limit_key,
                config["window"],
                config["max_requests"],
                config.get("burst")
            )
            
            if not allowed:
                # 返回 429 錯誤
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Please try again in {reset_time} seconds.",
                        "retry_after": reset_time,
                        "limit": config["max_requests"],
                        "window": config["window"]
                    },
                    headers={
                        "Retry-After": str(reset_time),
                        "X-RateLimit-Limit": str(config["max_requests"]),
                        "X-RateLimit-Remaining": str(remaining),
                        "X-RateLimit-Reset": str(int(time.time()) + reset_time),
                        "X-RateLimit-Window": str(config["window"])
                    }
                )
            
            # 執行請求
            response = await call_next(request)
            
            # 添加 rate limit 標頭
            response.headers["X-RateLimit-Limit"] = str(config["max_requests"])
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + reset_time)
            response.headers["X-RateLimit-Window"] = str(config["window"])
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            # 如果 rate limiting 出錯，允許請求通過（fail-open）
            return await call_next(request)


class RateLimitingService:
    """Rate Limiting 服務類別 - 提供程式化 API"""
    
    def __init__(self, redis_client: redis.Redis, settings: Settings):
        self.limiter = SlidingWindowRateLimiter(redis_client, settings)
        self.settings = settings
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        action: str, 
        window_size: int = 3600, 
        max_requests: int = 100
    ) -> Tuple[bool, Dict[str, int]]:
        """
        檢查特定動作的 rate limit
        
        Args:
            identifier: 唯一識別符
            action: 動作名稱
            window_size: 時間窗口（秒）
            max_requests: 最大請求數
            
        Returns:
            Tuple[是否允許, 狀態資訊]
        """
        key = f"action_limit:{identifier}:{action}"
        
        allowed, remaining, reset_time = await self.limiter.is_allowed(
            key, window_size, max_requests
        )
        
        status = {
            "allowed": allowed,
            "remaining": remaining,
            "reset_time": reset_time,
            "window_size": window_size,
            "max_requests": max_requests
        }
        
        return allowed, status
    
    async def get_user_rate_limit_status(self, user_id: str) -> Dict[str, Dict]:
        """獲取使用者的所有 rate limit 狀態"""
        common_actions = [
            ("message_send", 60, 30),  # 1分鐘30則訊息
            ("room_create", 3600, 5),  # 1小時5個房間
            ("file_upload", 300, 10),  # 5分鐘10個檔案
        ]
        
        status = {}
        for action, window, max_req in common_actions:
            key = f"action_limit:user:{user_id}:{action}"
            status[action] = await self.limiter.get_rate_limit_status(
                key, window, max_req
            )
        
        return status
    
    async def reset_rate_limit(self, identifier: str, action: str = None):
        """重置 rate limit（管理員功能）"""
        if action:
            key = f"action_limit:{identifier}:{action}"
            await self.limiter.redis.delete(key)
        else:
            # 重置所有相關的 rate limit
            pattern = f"*{identifier}*"
            keys = await self.limiter.redis.keys(pattern)
            if keys:
                await self.limiter.redis.delete(*keys)