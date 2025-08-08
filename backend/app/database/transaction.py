"""事務管理模組"""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import wraps

from pymongo.asynchronous.client_session import AsyncClientSession

from app.database.mongodb import mongo_client

logger = logging.getLogger(__name__)


class TransactionManager:
    """事務管理器"""

    def __init__(self):
        self.session: AsyncClientSession | None = None

    @asynccontextmanager
    async def transaction(self):
        """
        事務上下文管理器

        使用範例:
            async with transaction_manager.transaction():
                await user_repo.create(user_data)
                await room_repo.add_member(room_id, user_id)
        """
        client = mongo_client.get_client()
        if client is None:
            raise RuntimeError("MongoDB client not initialized")

        async with client.start_session() as session:
            try:
                async with session.start_transaction():
                    self.session = session
                    yield session
                    # 如果沒有異常，事務會自動提交
                    logger.info("Transaction committed successfully")
            except Exception as e:
                logger.error(f"Transaction rolled back due to error: {e}")
                raise
            finally:
                self.session = None

    def get_session(self) -> AsyncClientSession | None:
        """獲取當前事務會話"""
        return self.session


# 全域事務管理器實例
transaction_manager = TransactionManager()


def transactional(func: Callable) -> Callable:
    """
    事務裝飾器

    使用範例:
        @transactional
        async def create_room_with_owner(room_data, owner_id):
            room = await room_repo.create(room_data)
            await user_repo.update_rooms(owner_id, room.id)
            return room
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # 如果已經在事務中，直接執行
        if transaction_manager.get_session():
            return await func(*args, **kwargs)

        # 否則創建新事務
        async with transaction_manager.transaction():
            return await func(*args, **kwargs)

    return wrapper


class TransactionMixin:
    """
    提供事務支援的 Mixin 類別

    讓 Repository 類別繼承此 Mixin 以獲得事務支援
    """

    def _get_session_kwargs(self) -> dict:
        """
        獲取包含事務會話的關鍵字參數

        Returns:
            dict: 如果有活動事務，返回包含 session 的字典，否則返回空字典
        """
        session = transaction_manager.get_session()
        if session:
            return {"session": session}
        return {}

    async def _execute_with_transaction(self, operation: Callable, *args, **kwargs):
        """
        在事務上下文中執行操作

        Args:
            operation: 要執行的操作
            *args: 位置參數
            **kwargs: 關鍵字參數
        """
        # 合併事務會話參數
        kwargs.update(self._get_session_kwargs())
        return await operation(*args, **kwargs)
