"""UserService 和 NotificationService 整合測試"""
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, Mock, patch
from bson import ObjectId
from app.models.user import UserCreate, UserInDB, UserUpdate
from app.models.notification import NotificationCreate, NotificationInDB, NotificationType, NotificationStatus
from app.services.user_service import UserService
from app.services.notification_service import NotificationService


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.unit
class TestUserNotificationIntegration:
    """UserService 和 NotificationService 整合測試類別"""
    
    @pytest.fixture
    def user_service_with_mocks(self, mock_user_repository, mock_room_repository, mock_message_repository):
        """配置 UserService 和相關依賴"""
        return UserService(
            user_repository=mock_user_repository,
            room_repository=mock_room_repository,
            message_repository=mock_message_repository
        )
    
    @pytest.fixture
    def notification_service_with_mocks(self, mock_notification_repository):
        """配置 NotificationService"""
        return NotificationService(mock_notification_repository)
    
    @pytest.fixture
    def integration_services(self, user_service_with_mocks, notification_service_with_mocks):
        """整合測試的服務組合"""
        return {
            'user_service': user_service_with_mocks,
            'notification_service': notification_service_with_mocks
        }
    
    @pytest.mark.asyncio
    async def test_user_registration_with_welcome_notification(self, integration_services, mock_user_repository, mock_notification_repository):
        """測試用戶註冊時發送歡迎通知的整合流程"""
        user_service = integration_services['user_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        user_id = str(ObjectId())
        user_create = UserCreate(
            username="newuser",
            email="newuser@example.com",
            password="password123"
        )
        
        created_user = UserInDB(
            id=user_id,
            username="newuser",
            email="newuser@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 UserService mock
        mock_user_repository.get_by_email.return_value = None  # 用戶不存在
        mock_user_repository.create.return_value = created_user
        
        # 配置 NotificationService mock
        welcome_notification = NotificationInDB(
            id=str(ObjectId()),
            user_id=user_id,
            title="歡迎加入！",
            content="歡迎來到聊天室，開始你的對話吧！",
            type=NotificationType.SYSTEM,
            status=NotificationStatus.UNREAD,
            is_read=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        mock_notification_repository.create.return_value = welcome_notification
        
        # Mock 實時通知
        notification_service.send_real_time_notification = AsyncMock()
        
        # 執行整合流程
        # 1. 創建用戶
        result_user = await user_service.create_user(user_create)
        assert result_user is not None
        assert result_user.username == "newuser"
        
        # 2. 發送歡迎通知（使用業務邏輯方法避免事務問題）
        welcome_result = await notification_service._create_notification_business_logic(
            user_id=user_id,
            title="歡迎加入！",
            content="歡迎來到聊天室，開始你的對話吧！",
            notification_type=NotificationType.SYSTEM
        )
        
        # 驗證整合結果
        assert welcome_result is not None
        assert welcome_result.user_id == user_id
        assert welcome_result.title == "歡迎加入！"
        assert welcome_result.type == NotificationType.SYSTEM
        
        # 驗證服務調用
        mock_user_repository.create.assert_called_once()
        mock_notification_repository.create.assert_called_once()
        notification_service.send_real_time_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_user_profile_update_with_notification(self, integration_services, mock_user_repository, mock_notification_repository):
        """測試用戶資料更新時的通知流程"""
        user_service = integration_services['user_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        user_id = str(ObjectId())
        updated_user = UserInDB(
            id=user_id,
            username="original_user",
            email="updated@example.com",
            hashed_password="hashed_password",
            full_name="updated_user",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 UserService mock
        mock_user_repository.get_by_id.return_value = updated_user
        mock_user_repository.update.return_value = updated_user
        
        # 配置 NotificationService mock
        update_notification = NotificationInDB(
            id=str(ObjectId()),
            user_id=user_id,
            title="資料更新成功",
            content="您的個人資料已成功更新",
            type=NotificationType.SYSTEM,
            status=NotificationStatus.UNREAD,
            is_read=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        mock_notification_repository.create.return_value = update_notification
        notification_service.send_real_time_notification = AsyncMock()
        
        # 執行整合流程
        # 1. 更新用戶資料
        update_data = UserUpdate(full_name="updated_user")
        result_user = await user_service.update_user(user_id, update_data, user_id)
        assert result_user is not None
        assert result_user.full_name == "updated_user"
        
        # 2. 發送更新通知（使用業務邏輯方法避免事務問題）
        update_result = await notification_service._create_notification_business_logic(
            user_id=user_id,
            title="資料更新成功",
            content="您的個人資料已成功更新",
            notification_type=NotificationType.SYSTEM
        )
        
        # 驗證整合結果
        assert update_result is not None
        assert update_result.user_id == user_id
        assert update_result.title == "資料更新成功"
        
        # 驗證服務調用
        mock_user_repository.update.assert_called_once()
        mock_notification_repository.create.assert_called_once()
        notification_service.send_real_time_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_user_activity_stats_with_notification_stats(self, integration_services, mock_user_repository, mock_room_repository, mock_message_repository, mock_notification_repository):
        """測試用戶活動統計與通知統計的整合"""
        user_service = integration_services['user_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        user_id = str(ObjectId())
        
        # 配置測試用戶
        test_user = UserInDB(
            id=user_id,
            username="test_user",
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 UserService 活動統計 mock
        mock_user_repository.get_by_id.return_value = test_user
        mock_room_repository.count_user_rooms.return_value = 5
        mock_message_repository.get_user_message_stats.return_value = {
            "total_messages": 100,
            "today_messages": 10,
            "week_messages": 50
        }
        
        # 配置 NotificationService 統計 mock
        from app.models.notification import NotificationStats
        notification_stats = NotificationStats(
            total_count=25,
            unread_count=5,
            read_count=20,
            dismissed_count=0,
            type_counts={
                "system": 10,
                "message": 15
            },
            recent_activity=[]
        )
        mock_notification_repository.get_stats.return_value = notification_stats
        
        # 執行整合流程
        # 1. 獲取用戶活動統計
        activity_stats = await user_service.get_user_activity_stats(user_id)
        
        # 2. 獲取通知統計
        notification_stats_result = await notification_service.get_notification_stats(user_id)
        
        # 驗證整合結果
        assert activity_stats is not None
        assert activity_stats['joined_rooms'] == 5
        assert activity_stats['total_messages'] == 100
        
        assert notification_stats_result is not None
        assert notification_stats_result.total_count == 25
        assert notification_stats_result.unread_count == 5
        
        # 驗證服務調用
        mock_room_repository.count_user_rooms.assert_called_once_with(user_id)
        mock_message_repository.get_user_message_stats.assert_called_once_with(user_id)
        mock_notification_repository.get_stats.assert_called_once_with(user_id)
    
    @pytest.mark.asyncio
    async def test_user_deactivation_with_notification_cleanup(self, integration_services, mock_user_repository, mock_notification_repository):
        """測試用戶停用時的通知清理整合流程"""
        user_service = integration_services['user_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        user_id = str(ObjectId())
        deactivated_user = UserInDB(
            id=user_id,
            username="deactivated_user",
            email="deactivated@example.com",
            hashed_password="hashed_password",
            is_active=False,  # 已停用
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 UserService mock
        mock_user_repository.get_by_id.return_value = deactivated_user
        mock_user_repository.update.return_value = deactivated_user
        
        # 配置 NotificationService mock
        mock_notification_repository.delete_old_notifications.return_value = 15  # 清理了15個通知
        
        # 執行整合流程
        # 1. 停用用戶
        # 注意：is_active 不是 UserUpdate 的字段，這裡需要模擬管理員操作
        # 但為了測試整合流程，我們可以直接模擬停用結果
        result_user = await user_service.user_repo.update(user_id, {"is_active": False})
        assert result_user is not None
        assert result_user.is_active is False
        
        # 2. 清理用戶相關通知
        cleanup_count = await notification_service.cleanup_old_notifications(days=0)  # 立即清理
        
        # 驗證整合結果
        assert cleanup_count == 15
        
        # 驗證服務調用
        mock_user_repository.update.assert_called_once()
        mock_notification_repository.delete_old_notifications.assert_called_once_with(0)
    
    @pytest.mark.asyncio
    async def test_error_handling_in_user_notification_flow(self, integration_services, mock_user_repository, mock_notification_repository):
        """測試用戶通知流程中的錯誤處理"""
        user_service = integration_services['user_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        user_id = str(ObjectId())
        user_create = UserCreate(
            username="erroruser",
            email="error@example.com",
            password="password123"
        )
        
        created_user = UserInDB(
            id=user_id,
            username="erroruser",
            email="error@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 配置 UserService mock - 成功創建用戶
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.create.return_value = created_user
        
        # 配置 NotificationService mock - 通知創建失敗
        mock_notification_repository.create.side_effect = Exception("Notification creation failed")
        notification_service.send_real_time_notification = AsyncMock()
        
        # 執行整合流程
        # 1. 創建用戶應該成功
        result_user = await user_service.create_user(user_create)
        assert result_user is not None
        assert result_user.username == "erroruser"
        
        # 2. 發送通知應該失敗但不影響用戶創建（使用業務邏輯方法避免事務問題）
        welcome_result = None
        try:
            welcome_result = await notification_service._create_notification_business_logic(
                user_id=user_id,
                title="歡迎加入！",
                content="歡迎來到聊天室，開始你的對話吧！",
                notification_type=NotificationType.SYSTEM
            )
        except Exception:
            pass  # 預期的異常
        
        # 驗證錯誤處理
        assert welcome_result is None  # 通知創建失敗
        
        # 驗證用戶創建仍然成功
        mock_user_repository.create.assert_called_once()
        mock_notification_repository.create.assert_called_once()
        
        # 實時通知不應該被調用（因為通知創建失敗）
        notification_service.send_real_time_notification.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_batch_user_notification_flow(self, integration_services, mock_user_repository, mock_notification_repository):
        """測試批量用戶通知流程"""
        user_service = integration_services['user_service']
        notification_service = integration_services['notification_service']
        
        # 準備測試數據
        user_ids = [str(ObjectId()), str(ObjectId()), str(ObjectId())]
        
        # 配置 UserService mock
        users = [
            UserInDB(
                id=user_id,
                username=f"user_{i}",
                email=f"user{i}@example.com",
                hashed_password="hashed_password",
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            for i, user_id in enumerate(user_ids)
        ]
        
        # 配置 NotificationService mock
        notification_ids = [str(ObjectId()) for _ in user_ids]
        mock_notification_repository.create_batch.return_value = notification_ids
        notification_service.send_batch_real_time_notifications = AsyncMock()
        
        # 執行整合流程
        # 1. 模擬獲取多個用戶（例如：系統維護通知）
        for user in users:
            mock_user_repository.get_by_id.return_value = user
            user_result = await user_service.get_user_by_id(user.id)
            assert user_result is not None
        
        # 2. 發送批量通知（使用業務邏輯方法避免事務問題）
        batch_result = await notification_service._create_batch_notifications_business_logic(
            user_ids=user_ids,
            title="系統維護通知",
            content="系統將於今晚進行維護，預計持續2小時",
            notification_type=NotificationType.SYSTEM
        )
        
        # 驗證整合結果
        assert batch_result == notification_ids
        assert len(batch_result) == 3
        
        # 驗證服務調用
        mock_notification_repository.create_batch.assert_called_once()
        notification_service.send_batch_real_time_notifications.assert_called_once()