"""UserService 和 NotificationService 整合測試"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId

from app.models.notification import (
    NotificationInDB,
    NotificationStatus,
    NotificationType,
)
from app.models.user import UserCreate, UserInDB, UserUpdate
from app.services.notification_service import NotificationService
from app.services.user_service import UserService


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.unit
class TestUserNotificationIntegration:
    """UserService 和 NotificationService 整合測試類別"""

    @pytest.fixture
    def user_service_with_mocks(self, mock_user_repository):
        """配置 UserService 和相關依賴"""
        return UserService(user_repository=mock_user_repository)

    @pytest.fixture
    def notification_service_with_mocks(self, mock_notification_repository):
        """配置 NotificationService"""
        return NotificationService(mock_notification_repository)

    @pytest.fixture
    def integration_services(
        self, user_service_with_mocks, notification_service_with_mocks
    ):
        """整合測試的服務組合"""
        return {
            "user_service": user_service_with_mocks,
            "notification_service": notification_service_with_mocks,
        }

    @pytest.mark.asyncio
    async def test_user_registration_with_welcome_notification(
        self, integration_services, mock_user_repository, mock_notification_repository
    ):
        """測試用戶註冊時發送歡迎通知的整合流程"""
        user_service = integration_services["user_service"]
        notification_service = integration_services["notification_service"]

        # 準備測試數據
        user_id = str(ObjectId())
        user_create = UserCreate(
            username="newuser", email="newuser@example.com", password="password123"
        )

        created_user = UserInDB(
            id=user_id,
            username="newuser",
            email="newuser@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置 UserService mock（唯一性檢查通過）
        mock_user_repository.get_by_username.return_value = None
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.create.return_value = created_user

        # 配置 NotificationService mock
        welcome_notification = NotificationInDB(
            id=str(ObjectId()),
            user_id=user_id,
            title="歡迎加入！",
            content="歡迎來到聊天室，開始你的對話吧！",
            type=NotificationType.SYSTEM,
            status=NotificationStatus.UNREAD,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
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
            notification_type=NotificationType.SYSTEM,
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
    async def test_user_profile_update_with_notification(
        self, integration_services, mock_user_repository, mock_notification_repository
    ):
        """測試用戶資料更新時的通知流程"""
        user_service = integration_services["user_service"]
        notification_service = integration_services["notification_service"]

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
            updated_at=datetime.now(UTC),
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
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
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
            notification_type=NotificationType.SYSTEM,
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
    async def test_error_handling_in_user_notification_flow(
        self, integration_services, mock_user_repository, mock_notification_repository
    ):
        """測試用戶通知流程中的錯誤處理"""
        user_service = integration_services["user_service"]
        notification_service = integration_services["notification_service"]

        # 準備測試數據
        user_id = str(ObjectId())
        user_create = UserCreate(
            username="erroruser", email="error@example.com", password="password123"
        )

        created_user = UserInDB(
            id=user_id,
            username="erroruser",
            email="error@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置 UserService mock - 唯一性檢查通過 + 成功創建用戶
        mock_user_repository.get_by_username.return_value = None
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.create.return_value = created_user

        # 配置 NotificationService mock - 通知創建失敗
        mock_notification_repository.create.side_effect = Exception(
            "Notification creation failed"
        )
        notification_service.send_real_time_notification = AsyncMock()

        # 執行整合流程
        # 1. 創建用戶應該成功
        result_user = await user_service.create_user(user_create)
        assert result_user is not None
        assert result_user.username == "erroruser"

        # 2. 發送通知應該失敗但不影響用戶創建（使用業務邏輯方法避免事務問題）
        welcome_result = None
        try:
            welcome_result = (
                await notification_service._create_notification_business_logic(
                    user_id=user_id,
                    title="歡迎加入！",
                    content="歡迎來到聊天室，開始你的對話吧！",
                    notification_type=NotificationType.SYSTEM,
                )
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
