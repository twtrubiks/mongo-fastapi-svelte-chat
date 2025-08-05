"""訊息服務整合測試 - 使用 Mock Repository"""
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, Mock, patch
from app.services.message_service import MessageService
from app.models.message import MessageCreate, MessageType, MessageStatus, MessageUpdate, MessageResponse
from app.models.user import UserInDB
from bson import ObjectId


@pytest.mark.unit
class TestMessageServiceIntegration:
    """測試訊息服務"""
    
    @pytest.mark.asyncio
    async def test_create_message(self, message_service_with_mocks):
        """測試創建訊息"""
        service = message_service_with_mocks
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        username = "testuser"
        
        # 配置 Mock 回傳值
        mock_message_id = str(ObjectId())
        mock_message = MessageResponse(
            id=mock_message_id,
            content="測試訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username=username,
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 配置用戶 mock
        mock_user = UserInDB(
            id=user_id,
            username=username,
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 設定 mock 方法的回傳值
        service.message_repo.create.return_value = mock_message
        service.room_repo.get_by_id.return_value = {"_id": room_id, "name": "Test Room"}
        service.room_repo.is_member.return_value = True
        
        message_data = MessageCreate(
            room_id=room_id,
            content="測試訊息",
            message_type=MessageType.TEXT
        )
        
        # Mock UserRepository
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
            
            result = await service.create_message(
                user_id=user_id,
                message_data=message_data
            )
            
            assert result.content == "測試訊息"
            assert result.message_type == MessageType.TEXT
            assert result.user_id == user_id
            assert result.room_id == room_id
            assert result.username == username
            assert result.status == MessageStatus.SENT
    
    @pytest.mark.asyncio
    async def test_create_message_with_reply(self, message_service_with_mocks):
        """測試創建回覆訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        username = "testuser"
        
        # 配置原始訊息
        original_message_id = str(ObjectId())
        original_message = MessageResponse(
            id=original_message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username=username,
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 配置回覆訊息
        reply_message_id = str(ObjectId())
        reply_message = MessageResponse(
            id=reply_message_id,
            content="回覆訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username=username,
            status=MessageStatus.SENT,
            edited=False,
            reply_to=original_message_id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 設定 mock 方法的回傳值
        service.message_repo.create.side_effect = [original_message, reply_message]
        service.room_repo.get_by_id.return_value = {"_id": room_id, "name": "Test Room"}
        service.room_repo.is_member.return_value = True
        
        # 配置用戶 mock
        mock_user = UserInDB(
            id=str(ObjectId()),
            username=username,
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 創建原始訊息
        original_message_data = MessageCreate(
            room_id=room_id,
            content="原始訊息",
            message_type=MessageType.TEXT
        )
        
        # Mock UserRepository
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=mock_user)
            
            original_result = await service.create_message(
                user_id=user_id,
                message_data=original_message_data
            )
            
            # 創建回覆訊息
            reply_message_data = MessageCreate(
                room_id=room_id,
                content="回覆訊息",
                message_type=MessageType.TEXT,
                reply_to=original_result.id
            )
            
            reply_result = await service.create_message(
                user_id=user_id,
                message_data=reply_message_data
            )
        
        assert reply_result.reply_to == original_result.id
        assert reply_result.content == "回覆訊息"
    
    @pytest.mark.asyncio
    async def test_get_message_by_id(self, message_service_with_mocks):
        """測試根據 ID 獲取訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        message_id = str(ObjectId())
        
        # 配置 Mock 回傳值
        mock_message = MessageResponse(
            id=message_id,
            content="測試訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        service.message_repo.get_with_reply.return_value = mock_message
        
        # 根據 ID 獲取訊息
        result = await service.get_message_by_id(
            message_id=message_id
        )
        
        assert result.id == message_id
        assert result.content == "測試訊息"
        assert result.user_id == user_id
    
    @pytest.mark.asyncio
    async def test_get_room_messages(self, message_service_with_mocks):
        """測試獲取房間訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        
        # 配置 Mock 回傳值
        mock_messages = [
            MessageResponse(
                id=str(ObjectId()),
                content=f"訊息 {i}",
                message_type=MessageType.TEXT,
                user_id=user_id,
                room_id=room_id,
                username="testuser",
                status=MessageStatus.SENT,
                edited=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ) for i in range(3)
        ]
        
        service.message_repo.get_room_messages.return_value = mock_messages
        service.room_repo.is_member.return_value = True
        
        # 獲取房間訊息
        result = await service.get_room_messages(
            room_id=room_id
        )
        
        assert len(result) == 3
        assert all(msg.room_id == room_id for msg in result)
    
    @pytest.mark.asyncio
    async def test_update_message(self, message_service_with_mocks):
        """測試更新訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        message_id = str(ObjectId())
        
        # 配置原始訊息
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,  # 相同的使用者
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # 配置更新後的訊息
        updated_message = MessageResponse(
            id=message_id,
            content="更新後的訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        service.message_repo.get_by_id.return_value = original_message
        service.message_repo.update.return_value = updated_message
        
        update_data = MessageUpdate(content="更新後的訊息")
        
        result = await service.update_message(
            message_id=message_id,
            user_id=user_id,
            update_data=update_data
        )
        
        assert result.content == "更新後的訊息"
        assert result.id == message_id
    
    @pytest.mark.asyncio
    async def test_delete_message(self, message_service_with_mocks):
        """測試刪除訊息"""
        service = message_service_with_mocks
        message_id = str(ObjectId())
        user_id = "test_user_id"
        
        # 配置原始訊息
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,  # 相同的使用者
            room_id="test_room_id",
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        service.message_repo.get_by_id.return_value = original_message
        service.message_repo.delete.return_value = True
        
        result = await service.delete_message(
            message_id=message_id,
            user_id=user_id
        )
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_get_recent_messages(self, message_service_with_mocks):
        """測試獲取最近訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        
        # 配置 Mock 回傳值
        mock_messages = [
            MessageResponse(
                id=str(ObjectId()),
                content=f"最近訊息 {i}",
                message_type=MessageType.TEXT,
                user_id=user_id,
                room_id=room_id,
                username="testuser",
                status=MessageStatus.SENT,
                edited=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ) for i in range(5)
        ]
        
        service.message_repo.get_recent_messages.return_value = mock_messages
        
        result = await service.get_recent_messages(
            room_id=room_id,
            limit=5
        )
        
        assert len(result) == 5
        assert all("最近訊息" in msg.content for msg in result)
    
    @pytest.mark.asyncio
    async def test_mark_messages_as_read(self, message_service_with_mocks):
        """測試標記訊息為已讀"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        
        service.message_repo.mark_messages_as_read.return_value = 5
        
        result = await service.mark_messages_as_read(
            room_id=room_id,
            user_id=user_id
        )
        
        assert result == 5
    
    @pytest.mark.asyncio
    async def test_get_unread_count(self, message_service_with_mocks):
        """測試獲取未讀訊息數量"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        
        service.message_repo.get_unread_count.return_value = 3
        
        result = await service.get_unread_count(
            room_id=room_id,
            user_id=user_id
        )
        
        assert result == 3
    
    @pytest.mark.asyncio
    async def test_update_message_unauthorized(self, message_service_with_mocks):
        """測試未授權更新訊息"""
        service = message_service_with_mocks
        message_id = str(ObjectId())
        user_id = "test_user_id"
        other_user_id = "other_user_id"
        
        # 配置原始訊息（屬於其他使用者）
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=other_user_id,  # 不同的使用者
            room_id="test_room_id",
            username="otheruser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        service.message_repo.get_by_id.return_value = original_message
        
        update_data = MessageUpdate(content="嘗試更新")
        
        with pytest.raises(ValueError, match="您只能編輯自己的訊息"):
            await service.update_message(
                message_id=message_id,
                user_id=user_id,
                update_data=update_data
            )
    
    @pytest.mark.asyncio
    async def test_delete_message_unauthorized(self, message_service_with_mocks):
        """測試未授權刪除訊息"""
        service = message_service_with_mocks
        message_id = str(ObjectId())
        user_id = "test_user_id"
        other_user_id = "other_user_id"
        
        # 配置原始訊息（屬於其他使用者）
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=other_user_id,  # 不同的使用者
            room_id="test_room_id",
            username="otheruser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        service.message_repo.get_by_id.return_value = original_message
        
        with pytest.raises(ValueError, match="您只能刪除自己的訊息"):
            await service.delete_message(
                message_id=message_id,
                user_id=user_id
            )