"""
資料庫事務的完整測試
測試事務管理、隔離性、並發處理等
"""
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from contextlib import asynccontextmanager
import asyncio
from app.database.transaction import TransactionManager, transactional, transaction_manager


class TestTransactionManager:
    """測試 TransactionManager 類"""
    
    @pytest.fixture
    def mock_client(self):
        """模擬 MongoDB 客戶端"""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def mock_session(self):
        """模擬 MongoDB session"""
        session = AsyncMock()
        # 模擬 start_transaction 返回一個異步上下文管理器
        @asynccontextmanager
        async def mock_transaction():
            yield
        
        session.start_transaction = Mock(return_value=mock_transaction())
        return session
    
    @pytest.mark.asyncio
    async def test_transaction_manager_init(self):
        """測試 TransactionManager 初始化"""
        tm = TransactionManager()
        assert tm.session is None
    
    @pytest.mark.asyncio
    async def test_transaction_success(self, mock_client, mock_session):
        """測試事務成功執行"""
        # 設置 mock
        mock_client.start_session = MagicMock()
        
        @asynccontextmanager
        async def mock_start_session():
            yield mock_session
            
        mock_client.start_session.return_value = mock_start_session()
        
        with patch('app.database.transaction.mongo_client') as mock_mongo:
            mock_mongo.get_client.return_value = mock_client
            
            tm = TransactionManager()
            
            # 測試事務
            async with tm.transaction() as session:
                assert session == mock_session
                assert tm.session == mock_session
            
            # 事務結束後，session 應該被清空
            assert tm.session is None
    
    @pytest.mark.asyncio
    async def test_transaction_with_error(self, mock_client, mock_session):
        """測試事務執行時發生錯誤"""
        # 設置 mock
        mock_client.start_session = MagicMock()
        
        @asynccontextmanager
        async def mock_start_session():
            yield mock_session
            
        mock_client.start_session.return_value = mock_start_session()
        
        with patch('app.database.transaction.mongo_client') as mock_mongo:
            mock_mongo.get_client.return_value = mock_client
            
            tm = TransactionManager()
            
            # 測試事務中拋出異常
            with pytest.raises(ValueError):
                async with tm.transaction():
                    assert tm.session == mock_session
                    raise ValueError("測試錯誤")
            
            # 事務結束後，session 應該被清空
            assert tm.session is None
    
    @pytest.mark.asyncio
    async def test_transaction_no_client(self):
        """測試沒有 MongoDB 客戶端的情況"""
        with patch('app.database.transaction.mongo_client') as mock_mongo:
            mock_mongo.get_client.return_value = None
            
            tm = TransactionManager()
            
            # 應該拋出 RuntimeError
            with pytest.raises(RuntimeError, match="MongoDB client not initialized"):
                async with tm.transaction():
                    pass
    
    @pytest.mark.asyncio
    async def test_get_session(self):
        """測試獲取當前 session"""
        tm = TransactionManager()
        
        # 初始時應該返回 None
        assert tm.get_session() is None
        
        # 設置 session
        mock_session = Mock()
        tm.session = mock_session
        
        # 應該返回設置的 session
        assert tm.get_session() == mock_session


class TestTransactionalDecorator:
    """測試 transactional 裝飾器"""
    
    @pytest.mark.asyncio
    async def test_transactional_without_existing_transaction(self):
        """測試沒有現有事務的情況"""
        result = []
        
        @transactional
        async def test_func(value):
            result.append(value)
            return f"Result: {value}"
        
        # Mock transaction_manager
        with patch('app.database.transaction.transaction_manager') as mock_tm:
            mock_tm.get_session.return_value = None
            
            # Mock transaction context
            @asynccontextmanager
            async def mock_transaction():
                yield
            
            mock_tm.transaction.return_value = mock_transaction()
            
            # 執行函數
            ret = await test_func("test")
            
            assert ret == "Result: test"
            assert result == ["test"]
            
            # 應該創建新事務
            mock_tm.transaction.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_transactional_with_existing_transaction(self):
        """測試已有事務的情況"""
        result = []
        
        @transactional
        async def test_func(value):
            result.append(value)
            return f"Result: {value}"
        
        # Mock transaction_manager
        with patch('app.database.transaction.transaction_manager') as mock_tm:
            # 模擬已有事務
            mock_tm.get_session.return_value = Mock()
            
            # 執行函數
            ret = await test_func("test")
            
            assert ret == "Result: test"
            assert result == ["test"]
            
            # 不應該創建新事務
            mock_tm.transaction.assert_not_called()


class TestTransactionMixin:
    """測試 TransactionMixin"""
    
    def test_get_session_kwargs_with_session(self):
        """測試有活動事務時獲取 session kwargs"""
        from app.database.transaction import TransactionMixin
        
        mixin = TransactionMixin()
        
        with patch('app.database.transaction.transaction_manager') as mock_tm:
            mock_session = Mock()
            mock_tm.get_session.return_value = mock_session
            
            kwargs = mixin._get_session_kwargs()
            
            assert kwargs == {"session": mock_session}
    
    def test_get_session_kwargs_without_session(self):
        """測試沒有活動事務時獲取 session kwargs"""
        from app.database.transaction import TransactionMixin
        
        mixin = TransactionMixin()
        
        with patch('app.database.transaction.transaction_manager') as mock_tm:
            mock_tm.get_session.return_value = None
            
            kwargs = mixin._get_session_kwargs()
            
            assert kwargs == {}
    
    @pytest.mark.asyncio
    async def test_execute_with_transaction(self):
        """測試在事務上下文中執行操作"""
        from app.database.transaction import TransactionMixin
        
        mixin = TransactionMixin()
        
        # Mock operation
        async def mock_operation(arg1, arg2, **kwargs):
            return {"arg1": arg1, "arg2": arg2, "kwargs": kwargs}
        
        with patch('app.database.transaction.transaction_manager') as mock_tm:
            mock_session = Mock()
            mock_tm.get_session.return_value = mock_session
            
            result = await mixin._execute_with_transaction(
                mock_operation, 
                "value1", 
                "value2",
                extra="extra_value"
            )
            
            assert result == {
                "arg1": "value1",
                "arg2": "value2",
                "kwargs": {
                    "extra": "extra_value",
                    "session": mock_session
                }
            }