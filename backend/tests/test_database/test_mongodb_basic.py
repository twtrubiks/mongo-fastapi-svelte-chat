"""MongoDB 資料庫連線的基礎測試"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from app.database.mongodb import (
    MongoDBManager,
    init_database,
    close_database,
    get_database,
    get_client,
    mongo_client
)


class MongoDBTestManager:
    """測試 MongoDBManager 類"""
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """測試成功連線到 MongoDB"""
        manager = MongoDBManager()
        
        with patch('app.database.mongodb.AsyncMongoClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock()
            mock_client.__getitem__.return_value = Mock()  # mock database
            mock_client_class.return_value = mock_client
            
            await manager.connect("mongodb://localhost:27017", "testdb")
            
            assert manager.client is not None
            assert manager.database is not None
            mock_client.admin.command.assert_called_once_with('ping')
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """測試連線 MongoDB 失敗"""
        manager = MongoDBManager()
        
        with patch('app.database.mongodb.AsyncMongoClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client_class.return_value = mock_client
            
            with pytest.raises(Exception) as exc_info:
                await manager.connect("mongodb://invalid:27017", "testdb")
            
            assert "Connection failed" in str(exc_info.value)
            # 連線失敗時，client 已經被建立但連線測試失敗，所以 client 不是 None
            # 這符合實際的代碼邏輯
    
    @pytest.mark.asyncio
    async def test_get_database_not_connected(self):
        """測試在未連線時獲取資料庫"""
        manager = MongoDBManager()
        
        with pytest.raises(RuntimeError) as exc_info:
            await manager.get_database()
        
        assert "Database not connected" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """測試斷開連線"""
        manager = MongoDBManager()
        
        # 先建立連線
        with patch('app.database.mongodb.AsyncMongoClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.admin.command = AsyncMock()
            mock_client.close = AsyncMock()
            mock_client.__getitem__.return_value = Mock()
            mock_client_class.return_value = mock_client
            
            await manager.connect("mongodb://localhost:27017", "testdb")
            assert manager.client is not None
            
            # 斷開連線
            await manager.disconnect()
            
            mock_client.close.assert_called_once()
            assert manager.client is None
            assert manager.database is None


class TestModuleFunctions:
    """測試模組級函數"""
    
    @pytest.mark.asyncio
    async def test_get_database_function(self):
        """測試 get_database 函數"""
        with patch('app.database.mongodb._db_manager') as mock_manager:
            mock_manager.get_database = AsyncMock(return_value=Mock())
            
            result = await get_database()
            
            assert result is not None
            mock_manager.get_database.assert_called_once()
    
    def test_get_client_function(self):
        """測試 get_client 函數"""
        with patch('app.database.mongodb._db_manager') as mock_manager:
            mock_client = Mock()
            mock_manager.client = mock_client
            
            result = get_client()
            
            assert result == mock_client
    
    def test_mongo_client_wrapper(self):
        """測試 MongoClientWrapper"""
        with patch('app.database.mongodb._db_manager') as mock_manager:
            mock_client = Mock()
            mock_manager.client = mock_client
            
            result = mongo_client.get_client()
            
            assert result == mock_client