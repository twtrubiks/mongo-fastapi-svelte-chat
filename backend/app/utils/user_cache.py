"""使用者資料 Redis 快取工具"""

import json
import logging

from app.config import settings
from app.database.mongodb import get_database
from app.database.redis_conn import get_redis
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "user_cache"


def _cache_key(user_id: str) -> str:
    return f"{CACHE_KEY_PREFIX}:{user_id}"


async def get_cached_user(user_id: str) -> dict | None:
    """
    從 Redis 取得快取的使用者資料

    Args:
        user_id: 使用者 ID

    Returns:
        使用者資料 dict 或 None（快取未命中或 Redis 不可用）
    """
    try:
        redis_client = await get_redis()
        cached = await redis_client.get(_cache_key(user_id))
        if cached is not None:
            logger.debug(f"User cache hit: {user_id}")
            return json.loads(cached)
        return None
    except Exception as e:  # intentional fail-open: 快取操作失敗不影響主流程
        logger.warning(f"Redis get failed for user cache {user_id}: {e}")
        return None


async def set_cached_user(user_id: str, user_dict: dict) -> None:
    """
    將使用者資料寫入 Redis 快取

    會自動移除 hashed_password，不將敏感資料存入 Redis。

    Args:
        user_id: 使用者 ID
        user_dict: 使用者資料 dict
    """
    try:
        # 複製並移除敏感欄位
        cache_data = {k: v for k, v in user_dict.items() if k != "hashed_password"}
        json_str = json.dumps(cache_data, default=str, ensure_ascii=False)

        redis_client = await get_redis()
        await redis_client.set(
            _cache_key(user_id), json_str, ex=settings.USER_CACHE_TTL
        )
        logger.debug(f"User cache set: {user_id}")
    except Exception as e:  # intentional fail-open: 快取操作失敗不影響主流程
        logger.warning(f"Redis set failed for user cache {user_id}: {e}")


async def invalidate_user_cache(user_id: str) -> None:
    """
    清除指定使用者的快取

    Args:
        user_id: 使用者 ID
    """
    try:
        redis_client = await get_redis()
        await redis_client.delete(_cache_key(user_id))
        logger.debug(f"User cache invalidated: {user_id}")
    except Exception as e:  # intentional fail-open: 快取操作失敗不影響主流程
        logger.warning(f"Redis delete failed for user cache {user_id}: {e}")


async def fetch_user_with_cache(user_id: str) -> dict | None:
    """
    取得使用者資料（快取優先，miss 時查 MongoDB 並回寫快取）

    HTTP auth 和 WebSocket auth 共用此函數，確保 cache-first 邏輯只有一份。

    Returns:
        正規化的使用者 dict（_id 為字串，不含 hashed_password），或 None
    """
    cached = await get_cached_user(user_id)
    if cached is not None:
        return cached

    # 透過 UserRepository 查詢，遵守三層架構
    db = await get_database()
    repo = UserRepository(db)
    user_obj = await repo.get_by_id(user_id)
    if user_obj is None:
        return None

    user = user_obj.model_dump(by_alias=True, exclude={"hashed_password"})

    await set_cached_user(user["_id"], user)
    return user
