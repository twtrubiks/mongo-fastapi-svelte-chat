"""
改進的事務管理模組

解決以下問題：
1. 事件循環衝突問題
2. 嵌套事務管理
3. 併發控制優化
4. 更好的錯誤處理和恢復機制
"""
import asyncio
from typing import Optional, Callable, Any, Dict, Set
from functools import wraps
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pymongo.asynchronous.client_session import AsyncClientSession
from app.database.mongodb import mongo_client
import logging
import uuid
from weakref import WeakValueDictionary

logger = logging.getLogger(__name__)


class TransactionContext:
    """事務上下文，存儲單一事務的狀態"""
    
    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        self.session: Optional[AsyncClientSession] = None
        self.nested_level = 0
        self.is_active = False
        self.operations_count = 0
    
    def __repr__(self):
        return f"TransactionContext(id={self.transaction_id}, level={self.nested_level}, active={self.is_active})"


class ImprovedTransactionManager:
    """
    改進的事務管理器
    
    特點：
    1. 支援嵌套事務
    2. 更好的事件循環管理
    3. 併發安全
    4. 操作計數和監控
    """
    
    def __init__(self):
        # 使用 ContextVar 來避免事件循環衝突
        self._current_context: ContextVar[Optional[TransactionContext]] = ContextVar(
            'transaction_context', default=None
        )
        # 存儲所有活動的事務上下文（用於監控和調試）
        self._active_contexts: Dict[str, TransactionContext] = {}
        # 保護併發操作的鎖
        self._lock = asyncio.Lock()
    
    def _generate_transaction_id(self) -> str:
        """生成唯一的事務 ID"""
        return f"tx_{uuid.uuid4().hex[:8]}"
    
    def get_current_context(self) -> Optional[TransactionContext]:
        """獲取當前事務上下文"""
        return self._current_context.get()
    
    def get_session(self) -> Optional[AsyncClientSession]:
        """獲取當前事務會話"""
        context = self.get_current_context()
        return context.session if context else None
    
    def is_in_transaction(self) -> bool:
        """檢查是否在事務中"""
        context = self.get_current_context()
        return context is not None and context.is_active
    
    @asynccontextmanager
    async def transaction(self, isolation_level: Optional[str] = None):
        """
        改進的事務上下文管理器
        
        Args:
            isolation_level: MongoDB 事務隔離級別（暫時保留，MongoDB 主要使用快照隔離）
            
        使用範例:
            async with improved_transaction_manager.transaction():
                await user_repo.create(user_data)
                await room_repo.add_member(room_id, user_id)
        """
        current_context = self.get_current_context()
        
        # 如果已經在事務中，使用嵌套事務
        if current_context and current_context.is_active:
            async with self._handle_nested_transaction(current_context):
                yield current_context.session
            return
        
        # 創建新事務
        async with self._handle_new_transaction(isolation_level) as session:
            yield session
    
    @asynccontextmanager
    async def _handle_nested_transaction(self, context: TransactionContext):
        """處理嵌套事務"""
        async with self._lock:
            context.nested_level += 1
            logger.debug(f"Entering nested transaction level {context.nested_level} for {context.transaction_id}")
        
        try:
            yield context.session
            logger.debug(f"Nested transaction level {context.nested_level} completed for {context.transaction_id}")
        finally:
            async with self._lock:
                context.nested_level -= 1
    
    @asynccontextmanager
    async def _handle_new_transaction(self, isolation_level: Optional[str] = None):
        """處理新事務"""
        transaction_id = self._generate_transaction_id()
        context = TransactionContext(transaction_id)
        
        client = mongo_client.get_client()
        if client is None:
            raise RuntimeError("MongoDB client not initialized")
        
        async with self._lock:
            self._active_contexts[transaction_id] = context
        
        try:
            async with client.start_session() as session:
                try:
                    # 配置事務選項
                    transaction_options = {}
                    if isolation_level:
                        # MongoDB 主要使用快照隔離，這裡保留參數以便未來擴展
                        logger.info(f"Transaction isolation level requested: {isolation_level}")
                    
                    await session.start_transaction(**transaction_options)
                    context.session = session
                    context.is_active = True
                    self._current_context.set(context)
                    
                    logger.info(f"Transaction {transaction_id} started")
                    
                    try:
                        yield session
                        # 如果沒有異常，手動提交事務
                        await session.commit_transaction()
                        logger.info(f"Transaction {transaction_id} committed successfully (operations: {context.operations_count})")
                    except Exception as e:
                        # 回滾事務
                        try:
                            await session.abort_transaction()
                        except Exception:
                            pass  # 忽略回滾錯誤
                        logger.error(f"Transaction {transaction_id} failed: {e}")
                        raise
                    finally:
                        context.is_active = False
                        self._current_context.set(None)
                            
                except Exception as e:
                    logger.error(f"Transaction {transaction_id} rolled back due to error: {e}")
                    raise
        finally:
            async with self._lock:
                self._active_contexts.pop(transaction_id, None)
    
    def increment_operation_count(self):
        """增加操作計數（用於監控）"""
        context = self.get_current_context()
        if context:
            context.operations_count += 1
    
    async def get_transaction_stats(self) -> Dict[str, Any]:
        """獲取事務統計資訊"""
        async with self._lock:
            active_count = len(self._active_contexts)
            contexts_info = [
                {
                    "id": ctx.transaction_id,
                    "nested_level": ctx.nested_level,
                    "operations_count": ctx.operations_count,
                    "is_active": ctx.is_active
                }
                for ctx in self._active_contexts.values()
            ]
        
        return {
            "active_transactions": active_count,
            "contexts": contexts_info
        }


# 全域改進事務管理器實例
improved_transaction_manager = ImprovedTransactionManager()


def improved_transactional(
    retry_count: int = 0,
    retry_delay: float = 0.1,
    timeout: Optional[float] = None
):
    """
    改進的事務裝飾器
    
    Args:
        retry_count: 重試次數（預設不重試）
        retry_delay: 重試延遲（秒）
        timeout: 事務超時（秒）
    
    使用範例:
        @improved_transactional(retry_count=3, timeout=30.0)
        async def create_room_with_owner(room_data, owner_id):
            room = await room_repo.create(room_data)
            await user_repo.update_rooms(owner_id, room.id)
            return room
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 如果已經在事務中，直接執行
            if improved_transaction_manager.is_in_transaction():
                improved_transaction_manager.increment_operation_count()
                return await func(*args, **kwargs)
            
            # 嘗試執行事務
            last_exception = None
            for attempt in range(retry_count + 1):
                try:
                    if timeout:
                        # 使用超時控制
                        async with asyncio.timeout(timeout):
                            async with improved_transaction_manager.transaction():
                                improved_transaction_manager.increment_operation_count()
                                return await func(*args, **kwargs)
                    else:
                        async with improved_transaction_manager.transaction():
                            improved_transaction_manager.increment_operation_count()
                            return await func(*args, **kwargs)
                            
                except Exception as e:
                    last_exception = e
                    if attempt < retry_count:
                        logger.warning(f"Transaction attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}")
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"Transaction failed after {retry_count + 1} attempts: {e}")
                        raise
            
            # 這行理論上不會執行到，但為了安全性保留
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class ImprovedTransactionMixin:
    """
    改進的事務支援 Mixin 類別
    
    提供更完善的事務操作支援
    """
    
    def _get_session_kwargs(self) -> dict:
        """
        獲取包含事務會話的關鍵字參數
        
        Returns:
            dict: 如果有活動事務，返回包含 session 的字典，否則返回空字典
        """
        session = improved_transaction_manager.get_session()
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
        # 增加操作計數
        improved_transaction_manager.increment_operation_count()
        
        # 合併事務會話參數
        kwargs.update(self._get_session_kwargs())
        return await operation(*args, **kwargs)
    
    def _is_in_transaction(self) -> bool:
        """檢查當前是否在事務中"""
        return improved_transaction_manager.is_in_transaction()
    
    async def _get_transaction_info(self) -> Optional[Dict[str, Any]]:
        """獲取當前事務資訊（用於調試）"""
        context = improved_transaction_manager.get_current_context()
        if context:
            return {
                "transaction_id": context.transaction_id,
                "nested_level": context.nested_level,
                "operations_count": context.operations_count,
                "is_active": context.is_active
            }
        return None


# 向後相容性的別名
TransactionManager = ImprovedTransactionManager
transaction_manager = improved_transaction_manager
transactional = improved_transactional
TransactionMixin = ImprovedTransactionMixin