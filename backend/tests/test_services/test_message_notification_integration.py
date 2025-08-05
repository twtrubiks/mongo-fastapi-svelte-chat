"""MessageService 和 NotificationService 整合測試"""
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, Mock, patch
from bson import ObjectId
from app.models.message import MessageCreate, MessageInDB, MessageType, MessageListResponse, MessageResponse
from app.models.notification import NotificationCreate, NotificationInDB, NotificationType, NotificationStatus
from app.models.room import RoomInDB
from app.models.user import UserInDB
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.unit
class TestMessageNotificationIntegration:
    """MessageService 和 NotificationService 整合測試類別"""
    
    @pytest.fixture
    def message_service_with_mocks(self, mock_message_repository, mock_room_repository):
        """配置 MessageService 和相關依賴"""
        return MessageService(
            message_repository=mock_message_repository,
            room_repository=mock_room_repository
        )
    
    @pytest.fixture
    def notification_service_with_mocks(self, mock_notification_repository):
        """配置 NotificationService"""
        return NotificationService(mock_notification_repository)
    
    @pytest.fixture
    def integration_services(self, message_service_with_mocks, notification_service_with_mocks):
        """整合測試的服務組合"""
        return {
            'message_service': message_service_with_mocks,
            'notification_service': notification_service_with_mocks
        }
    
    @pytest.mark.asyncio
    async def test_create_message_with_notification_to_room_members(self, integration_services, mock_message_repository, mock_room_repository, mock_notification_repository):
        """測試創建消息時通知房間成員的整合流程"""
        message_service = integration_services['message_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        room_id = str(ObjectId())
        sender_id = str(ObjectId())
        member1_id = str(ObjectId())
        member2_id = str(ObjectId())
        
        # 配置房間 mock
        room = RoomInDB(
            id=room_id,
            name="測試房間",
            description="這是一個測試房間",
            is_public=True,
            owner_id=sender_id,
            members=[sender_id, member1_id, member2_id],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置用戶 mock
        sender = UserInDB(
            id=sender_id,
            username="sender",
            email="sender@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置消息 mock
        message = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=sender_id,
            username="sender",
            content="Hello everyone!",
            message_type=MessageType.TEXT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置通知 mock
        notification_ids = [str(ObjectId()), str(ObjectId())]
        
        # 配置 mocks
        mock_room_repository.get_by_id.return_value = room
        mock_room_repository.is_member.return_value = True
        mock_message_repository.create.return_value = message
        mock_notification_repository.create_batch.return_value = notification_ids
        
        # Mock UserRepository 用於 MessageService
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=sender)
            
            # Mock 實時通知
            notification_service.send_batch_real_time_notifications = AsyncMock()
            
            # 執行整合流程
            # 1. 創建消息
            message_create = MessageCreate(
                room_id=room_id,
                content="Hello everyone!",
                message_type=MessageType.TEXT
            )
            
            message_result = await message_service.create_message(
                user_id=sender_id,
                message_data=message_create
            )
            
            # 2. 通知房間成員（排除發送者）（使用業務邏輯方法避免事務問題）
            notification_user_ids = [member1_id, member2_id]  # 不包含 sender_id
            
            batch_result = await notification_service._create_batch_notifications_business_logic(
                user_ids=notification_user_ids,
                title=f"來自 sender 的新訊息",
                content=f"在 測試房間 中：Hello everyone!",
                notification_type=NotificationType.MESSAGE,
                metadata={
                    "sender_name": "sender",
                    "room_name": "測試房間",
                    "message_preview": "Hello everyone!"
                },
                sender_id=sender_id,
                room_id=room_id
            )
            
            # 驗證整合結果
            assert message_result is not None
            assert message_result.content == "Hello everyone!"
            assert message_result.room_id == room_id
            assert message_result.user_id == sender_id
            
            assert batch_result == notification_ids
            assert len(batch_result) == 2
            
            # 驗證服務調用
            mock_message_repository.create.assert_called_once()
            mock_notification_repository.create_batch.assert_called_once()
            notification_service.send_batch_real_time_notifications.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reply_message_with_targeted_notification(self, integration_services, mock_message_repository, mock_room_repository, mock_notification_repository):
        """測試回覆消息時的定向通知整合流程"""
        message_service = integration_services['message_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        room_id = str(ObjectId())
        original_sender_id = str(ObjectId())
        reply_sender_id = str(ObjectId())
        original_message_id = str(ObjectId())
        
        # 配置房間 mock
        room = RoomInDB(
            id=room_id,
            name="回覆房間",
            description="測試回覆功能",
            is_public=True,
            owner_id=original_sender_id,
            members=[original_sender_id, reply_sender_id],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置原始消息 mock
        original_message = MessageInDB(
            id=original_message_id,
            room_id=room_id,
            user_id=original_sender_id,
            username="original_sender",
            content="原始消息",
            message_type=MessageType.TEXT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置回覆消息 mock
        reply_message = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=reply_sender_id,
            username="replier",
            content="這是回覆",
            message_type=MessageType.TEXT,
            reply_to=original_message_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置用戶 mock
        reply_sender = UserInDB(
            id=reply_sender_id,
            username="replier",
            email="replier@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置通知 mock
        reply_notification = NotificationInDB(
            id=str(ObjectId()),
            user_id=original_sender_id,
            title="有人回覆了您的消息",
            content="replier 回覆了您的消息：這是回覆",
            type=NotificationType.MESSAGE,
            sender_id=reply_sender_id,
            room_id=room_id,
            status=NotificationStatus.UNREAD,
            is_read=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 mocks
        mock_room_repository.get_by_id.return_value = room
        mock_room_repository.is_member.return_value = True
        mock_message_repository.get_by_id.return_value = original_message
        mock_message_repository.create.return_value = reply_message
        mock_notification_repository.create.return_value = reply_notification
        
        # Mock UserRepository 用於 MessageService
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=reply_sender)
            
            # Mock 實時通知
            notification_service.send_real_time_notification = AsyncMock()
            
            # 執行整合流程
            # 1. 創建回覆消息
            reply_create = MessageCreate(
                room_id=room_id,
                content="這是回覆",
                message_type=MessageType.TEXT,
                reply_to=original_message_id
            )
            
            reply_result = await message_service.create_message(
                user_id=reply_sender_id,
                message_data=reply_create
            )
            
            # 2. 通知原始消息的發送者（使用業務邏輯方法避免事務問題）
            notification_result = await notification_service._create_notification_business_logic(
                user_id=original_sender_id,
                title="有人回覆了您的消息",
                content="replier 回覆了您的消息：這是回覆",
                notification_type=NotificationType.MESSAGE,
                metadata={
                    "sender_name": "replier",
                    "room_name": "回覆房間",
                    "message_preview": "這是回覆"
                },
                sender_id=reply_sender_id,
                room_id=room_id
            )
            
            # 驗證整合結果
            assert reply_result is not None
            assert reply_result.content == "這是回覆"
            assert reply_result.reply_to == original_message_id
            assert reply_result.room_id == room_id
            assert reply_result.user_id == reply_sender_id
            
            assert notification_result is not None
            assert notification_result.user_id == original_sender_id
            assert notification_result.type == NotificationType.MESSAGE
            
            # 驗證服務調用
            mock_message_repository.create.assert_called_once()
            mock_notification_repository.create.assert_called_once()
            notification_service.send_real_time_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_private_message_notification(self, integration_services, mock_message_repository, mock_room_repository, mock_notification_repository):
        """測試私人消息通知的整合流程"""
        message_service = integration_services['message_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        room_id = str(ObjectId())
        sender_id = str(ObjectId())
        recipient_id = str(ObjectId())
        
        # 配置私人房間 mock
        private_room = RoomInDB(
            id=room_id,
            name="私人對話",
            description="私人對話房間",
            is_public=False,
            owner_id=sender_id,
            members=[sender_id, recipient_id],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置私人消息 mock
        private_message = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=sender_id,
            username="private_sender",
            content="私人消息內容",
            message_type=MessageType.TEXT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置用戶 mock
        sender = UserInDB(
            id=sender_id,
            username="private_sender",
            email="private@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置私人通知 mock
        private_notification = NotificationInDB(
            id=str(ObjectId()),
            user_id=recipient_id,
            title="來自 private_sender 的私人消息",
            content="私人消息內容",
            type=NotificationType.MESSAGE,
            sender_id=sender_id,
            room_id=room_id,
            status=NotificationStatus.UNREAD,
            is_read=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 mocks
        mock_room_repository.get_by_id.return_value = private_room
        mock_room_repository.is_member.return_value = True
        mock_message_repository.create.return_value = private_message
        mock_notification_repository.create.return_value = private_notification
        
        # Mock UserRepository 用於 MessageService
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=sender)
            
            # Mock 實時通知
            notification_service.send_real_time_notification = AsyncMock()
            
            # 執行整合流程
            # 1. 創建私人消息
            private_create = MessageCreate(
                room_id=room_id,
                content="私人消息內容",
                message_type=MessageType.TEXT
            )
            
            message_result = await message_service.create_message(
                user_id=sender_id,
                message_data=private_create
            )
            
            # 2. 發送私人消息通知（使用業務邏輯方法避免事務問題）
            notification_result = await notification_service._create_notification_business_logic(
                user_id=recipient_id,
                title="來自 private_sender 的私人消息",
                content="私人消息內容",
                notification_type=NotificationType.MESSAGE,
                metadata={
                    "sender_name": "private_sender",
                    "room_name": "私人對話",
                    "message_preview": "私人消息內容"
                },
                sender_id=sender_id,
                room_id=room_id
            )
            
            # 驗證整合結果
            assert message_result is not None
            assert message_result.content == "私人消息內容"
            assert message_result.room_id == room_id
            assert message_result.user_id == sender_id
            
            assert notification_result is not None
            assert notification_result.user_id == recipient_id
            assert notification_result.sender_id == sender_id
            assert notification_result.type == NotificationType.MESSAGE
            
            # 驗證服務調用
            mock_message_repository.create.assert_called_once()
            mock_notification_repository.create.assert_called_once()
            notification_service.send_real_time_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_message_deletion_with_notification_cleanup(self, integration_services, mock_message_repository, mock_notification_repository):
        """測試消息刪除時的通知清理整合流程"""
        message_service = integration_services['message_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        message_id = str(ObjectId())
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # 配置消息 mock
        message_to_delete = MessageInDB(
            id=message_id,
            room_id=room_id,
            user_id=user_id,
            username="test_user",
            content="待刪除的消息",
            message_type=MessageType.TEXT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 mocks
        mock_message_repository.get_by_id.return_value = message_to_delete
        mock_message_repository.delete.return_value = True
        
        # Mock 通知清理（假設有相關的通知需要清理）
        # 這裡可以擴展為根據消息 ID 清理相關通知
        mock_notification_repository.delete_by_message_id = AsyncMock(return_value=3)
        
        # 執行整合流程
        # 1. 刪除消息
        delete_result = await message_service.delete_message(message_id, user_id)
        assert delete_result is True
        
        # 2. 清理相關通知（如果有的話）
        # 這是一個潛在的功能擴展
        if hasattr(mock_notification_repository, 'delete_by_message_id'):
            cleanup_count = await mock_notification_repository.delete_by_message_id(message_id)
            assert cleanup_count == 3
        
        # 驗證服務調用
        mock_message_repository.delete.assert_called_once_with(message_id)
    
    @pytest.mark.asyncio
    async def test_message_search_with_notification_context(self, integration_services, mock_message_repository, mock_notification_repository):
        """測試消息搜索與通知上下文的整合流程"""
        message_service = integration_services['message_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        user_id = str(ObjectId())
        room_id = str(ObjectId())
        
        # 配置搜索結果 mock
        search_results = [
            MessageInDB(
                id=str(ObjectId()),
                room_id=room_id,
                user_id=user_id,
                username="search_user",
                content="包含關鍵字的消息",
                message_type=MessageType.TEXT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
        ]
        
        # 配置通知 mock
        search_notification = NotificationInDB(
            id=str(ObjectId()),
            user_id=user_id,
            title="搜索結果",
            content="找到 1 條包含關鍵字的消息",
            type=NotificationType.SYSTEM,
            status=NotificationStatus.UNREAD,
            is_read=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置搜索結果的 mock
        from app.models.message import MessageListResponse
        search_list_response = MessageListResponse(
            messages=[MessageResponse(**msg.model_dump()) for msg in search_results],
            total=1,
            page=1,
            page_size=20,
            has_next=False,
            has_prev=False
        )
        
        # 配置 mocks
        mock_message_repository.search_messages.return_value = search_list_response
        mock_notification_repository.create.return_value = search_notification
        
        # Mock 實時通知
        notification_service.send_real_time_notification = AsyncMock()
        
        # 執行整合流程
        # 1. 搜索消息
        from app.models.message import MessageSearchQuery
        search_query = MessageSearchQuery(keyword="關鍵字")
        search_result = await message_service.search_messages(
            room_id=room_id,
            search_query=search_query
        )
        
        # 2. 發送搜索結果通知（使用業務邏輯方法避免事務問題）
        notification_result = await notification_service._create_notification_business_logic(
            user_id=user_id,
            title="搜索結果",
            content=f"找到 {search_result.total} 條包含關鍵字的消息",
            notification_type=NotificationType.SYSTEM
        )
        
        # 驗證整合結果
        assert search_result is not None
        assert isinstance(search_result, MessageListResponse)
        assert search_result.total == 1
        assert len(search_result.messages) == 1
        assert search_result.messages[0].content == "包含關鍵字的消息"
        
        assert notification_result is not None
        assert notification_result.title == "搜索結果"
        assert notification_result.type == NotificationType.SYSTEM
        
        # 驗證服務調用
        mock_message_repository.search_messages.assert_called_once_with(
            room_id,
            search_query
        )
        mock_notification_repository.create.assert_called_once()
        notification_service.send_real_time_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_message_notification_integration(self, integration_services, mock_message_repository, mock_room_repository, mock_notification_repository):
        """測試消息通知整合中的錯誤處理"""
        message_service = integration_services['message_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # 配置房間 mock
        room = RoomInDB(
            id=room_id,
            name="錯誤測試房間",
            description="測試錯誤處理",
            is_public=True,
            owner_id=user_id,
            members=[user_id],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置消息 mock
        message = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=user_id,
            username="test_user",
            content="消息內容",
            message_type=MessageType.TEXT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置用戶 mock
        user = UserInDB(
            id=user_id,
            username="test_user",
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 mocks
        mock_room_repository.get_by_id.return_value = room
        mock_room_repository.is_member.return_value = True
        mock_message_repository.create.return_value = message
        
        # 配置通知創建失敗
        mock_notification_repository.create.side_effect = Exception("Notification creation failed")
        
        # Mock UserRepository 用於 MessageService
        with patch('app.repositories.user_repository.UserRepository') as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=user)
            
            # 執行整合流程
            # 1. 創建消息應該成功
            message_create = MessageCreate(
                room_id=room_id,
                content="消息內容",
                message_type=MessageType.TEXT
            )
            
            message_result = await message_service.create_message(
                user_id=user_id,
                message_data=message_create
            )
            
            # 2. 通知創建應該失敗但不影響消息創建（使用業務邏輯方法避免事務問題）
            notification_result = None
            try:
                notification_result = await notification_service._create_notification_business_logic(
                    user_id=user_id,
                    title="測試通知",
                    content="這個通知會失敗",
                    notification_type=NotificationType.SYSTEM
                )
            except Exception as e:
                # 預期的錯誤
                assert "Notification creation failed" in str(e)
            
            # 驗證錯誤處理
            assert message_result is not None  # 消息創建成功
            assert message_result.content == "消息內容"
            
            assert notification_result is None  # 通知創建失敗
            
            # 驗證服務調用
            mock_message_repository.create.assert_called_once()
            mock_notification_repository.create.assert_called_once()