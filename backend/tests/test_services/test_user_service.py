"""
測試使用者服務層
使用 Mock 優先的方式測試所有功能
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId

from app.models.user import UserCreate, UserInDB, UserResponse, UserUpdate
from app.repositories.user_repository import (
    EmailAlreadyExistsError,
    UserAlreadyExistsError,
)
from app.services.user_service import UserService


class TestUserService:
    """測試使用者服務"""

    @pytest.fixture
    def mock_repositories(self):
        """Mock 所有倉儲"""
        user_repo = AsyncMock()
        room_repo = AsyncMock()
        message_repo = AsyncMock()
        return user_repo, room_repo, message_repo

    @pytest.fixture
    def user_service(self, mock_repositories):
        """創建使用者服務實例"""
        user_repo, room_repo, message_repo = mock_repositories
        return UserService(user_repo, room_repo, message_repo)

    @pytest.fixture
    def sample_user(self):
        """創建測試用使用者"""
        return UserInDB(
            id=str(ObjectId()),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, mock_repositories):
        """測試成功創建使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 密碼加密
        with patch("app.services.user_service.get_password_hash") as mock_hash:
            mock_hash.return_value = "hashed_password"

            # Mock 創建成功
            created_user = UserInDB(
                id=str(ObjectId()),
                username="newuser",
                email="new@example.com",
                full_name="New User",
                hashed_password="hashed_password",
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            user_repo.create.return_value = created_user

            # 創建使用者數據
            user_data = UserCreate(
                username="newuser",
                email="new@example.com",
                full_name="New User",
                password="password123",
            )

            # 執行創建
            result = await user_service.create_user(user_data)

            # 驗證
            assert result is not None
            assert result.username == "newuser"
            assert result.email == "new@example.com"
            mock_hash.assert_called_once_with("password123")
            user_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_username_exists(self, user_service, mock_repositories):
        """測試使用者名稱已存在"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 密碼加密
        with patch("app.services.user_service.get_password_hash") as mock_hash:
            mock_hash.return_value = "hashed_password"

            # Mock 使用者名稱已存在
            user_repo.create.side_effect = UserAlreadyExistsError("Username exists")

            # 執行並驗證拋出異常
            with pytest.raises(ValueError) as exc_info:
                await user_service.create_user(
                    UserCreate(
                        username="existing",
                        email="test@example.com",
                        password="password123",
                    )
                )

            assert "使用者名稱已存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_user_email_exists(self, user_service, mock_repositories):
        """測試信箱已存在"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 密碼加密
        with patch("app.services.user_service.get_password_hash") as mock_hash:
            mock_hash.return_value = "hashed_password"

            # Mock 信箱已存在
            user_repo.create.side_effect = EmailAlreadyExistsError("Email exists")

            # 執行並驗證拋出異常
            with pytest.raises(ValueError) as exc_info:
                await user_service.create_user(
                    UserCreate(
                        username="newuser",
                        email="existing@example.com",
                        password="password123",
                    )
                )

            assert "信箱已被使用" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, user_service, mock_repositories, sample_user):
        """測試根據 ID 獲取使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 返回使用者
        user_repo.get_by_id.return_value = sample_user

        # 執行
        result = await user_service.get_user_by_id(sample_user.id)

        # 驗證
        assert result is not None
        assert result.id == sample_user.id
        assert result.username == sample_user.username

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service, mock_repositories):
        """測試獲取不存在的使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 使用者不存在
        user_repo.get_by_id.return_value = None

        # 執行
        result = await user_service.get_user_by_id("invalid_id")

        # 驗證
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_username(
        self, user_service, mock_repositories, sample_user
    ):
        """測試根據用戶名獲取使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 返回使用者
        user_repo.get_by_username.return_value = sample_user

        # 執行
        result = await user_service.get_user_by_username(sample_user.username)

        # 驗證
        assert result is not None
        assert result.username == sample_user.username

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
        self, user_service, mock_repositories, sample_user
    ):
        """測試成功驗證使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_username.return_value = sample_user
        user_repo.update_last_login.return_value = True

        # Mock 密碼驗證和 token 創建
        with patch("app.services.user_service.verify_password") as mock_verify:
            with patch(
                "app.services.user_service.create_access_token"
            ) as mock_access_token:
                with patch(
                    "app.services.user_service.create_refresh_token"
                ) as mock_refresh_token:
                    mock_verify.return_value = True
                    mock_access_token.return_value = "access_token"
                    mock_refresh_token.return_value = "refresh_token"

                    # 執行
                    result = await user_service.authenticate_user(
                        "testuser", "password123"
                    )

                    # 驗證
                    assert result is not None
                    assert result["access_token"] == "access_token"
                    assert result["refresh_token"] == "refresh_token"
                    assert result["user"]["username"] == "testuser"
                    mock_verify.assert_called_once_with(
                        "password123", sample_user.hashed_password
                    )

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(
        self, user_service, mock_repositories, sample_user
    ):
        """測試密碼錯誤"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_username.return_value = sample_user

        # Mock 密碼驗證失敗
        with patch("app.services.user_service.verify_password") as mock_verify:
            mock_verify.return_value = False

            # 執行
            result = await user_service.authenticate_user("testuser", "wrong_password")

            # 驗證
            assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(
        self, user_service, mock_repositories, sample_user
    ):
        """測試不活躍使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # 設置使用者為不活躍
        sample_user.is_active = False
        user_repo.get_by_username.return_value = sample_user

        # Mock 密碼驗證成功
        with patch("app.services.user_service.verify_password") as mock_verify:
            mock_verify.return_value = True

            # 執行
            result = await user_service.authenticate_user("testuser", "password123")

            # 驗證
            assert result is None

    @pytest.mark.asyncio
    async def test_update_user_success(
        self, user_service, mock_repositories, sample_user
    ):
        """測試成功更新使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_id.return_value = sample_user
        user_repo.get_by_email.return_value = None  # 新信箱未被使用

        # Mock 更新後的使用者
        updated_user = UserInDB(**sample_user.model_dump())
        updated_user.full_name = "Updated Name"
        user_repo.update.return_value = updated_user

        # 更新數據
        update_data = UserUpdate(full_name="Updated Name")

        # 執行
        result = await user_service.update_user(
            sample_user.id, update_data, sample_user.id
        )

        # 驗證
        assert result is not None
        assert result.full_name == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_user_permission_denied(
        self, user_service, mock_repositories, sample_user
    ):
        """測試無權限更新他人資料"""
        user_repo, room_repo, message_repo = mock_repositories

        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await user_service.update_user(
                sample_user.id, UserUpdate(), "other_user_id"
            )

        assert "您只能更新自己的資料" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_email_exists(
        self, user_service, mock_repositories, sample_user
    ):
        """測試更新信箱已存在"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_id.return_value = sample_user

        # Mock 信箱已被其他使用者使用
        other_user = Mock(id="other_id", email="existing@example.com")
        user_repo.get_by_email.return_value = other_user

        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await user_service.update_user(
                sample_user.id, UserUpdate(email="existing@example.com"), sample_user.id
            )

        assert "信箱已被使用" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_user_success(
        self, user_service, mock_repositories, sample_user
    ):
        """測試成功刪除使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 刪除成功
        user_repo.delete.return_value = True

        # 執行
        result = await user_service.delete_user(sample_user.id, sample_user.id)

        # 驗證
        assert result is True
        user_repo.delete.assert_called_once_with(sample_user.id)

    @pytest.mark.asyncio
    async def test_delete_user_permission_denied(self, user_service, mock_repositories):
        """測試無權限刪除他人帳號"""
        user_repo, room_repo, message_repo = mock_repositories

        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await user_service.delete_user("user_id", "other_user_id")

        assert "您只能刪除自己的帳號" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_current_user_from_token(
        self, user_service, mock_repositories, sample_user
    ):
        """測試從 token 獲取當前使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock token 解碼
        with patch("app.services.user_service.decode_access_token") as mock_decode:
            mock_decode.return_value = {
                "sub": sample_user.username,
                "user_id": sample_user.id,
            }

            # Mock 獲取使用者
            user_repo.get_by_id.return_value = sample_user

            # 執行
            result = await user_service.get_current_user_from_token("valid_token")

            # 驗證
            assert result is not None
            assert result["_id"] == sample_user.id
            assert result["username"] == sample_user.username

    @pytest.mark.asyncio
    async def test_get_current_user_from_token_invalid(
        self, user_service, mock_repositories
    ):
        """測試無效 token"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock token 解碼失敗
        with patch("app.services.user_service.decode_access_token") as mock_decode:
            mock_decode.return_value = None

            # 執行
            result = await user_service.get_current_user_from_token("invalid_token")

            # 驗證
            assert result is None

    @pytest.mark.asyncio
    async def test_search_users(self, user_service, mock_repositories):
        """測試搜尋使用者"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 搜尋結果
        mock_users = []
        for i in range(3):
            user = UserInDB(
                id=str(ObjectId()),
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password="hash",
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            mock_users.append(user)

        user_repo.search_users.return_value = mock_users

        # 執行
        result = await user_service.search_users("user", limit=10)

        # 驗證
        assert len(result) == 3
        assert all(isinstance(user, UserResponse) for user in result)
        user_repo.search_users.assert_called_once_with("user", 10, None)

    @pytest.mark.asyncio
    async def test_get_user_activity_stats(
        self, user_service, mock_repositories, sample_user
    ):
        """測試獲取使用者活動統計"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_id.return_value = sample_user
        room_repo.count_user_rooms.return_value = 5
        message_repo.get_user_message_stats.return_value = {
            "total_messages": 100,
            "today_messages": 10,
            "week_messages": 50,
        }

        # 執行
        result = await user_service.get_user_activity_stats(sample_user.id)

        # 驗證
        assert result["user_id"] == sample_user.id
        assert result["username"] == sample_user.username
        assert result["joined_rooms"] == 5
        assert result["total_messages"] == 100
        assert result["today_messages"] == 10

    @pytest.mark.asyncio
    async def test_update_last_activity(self, user_service, mock_repositories):
        """測試更新最後活動時間"""
        user_repo, room_repo, message_repo = mock_repositories

        # 執行
        await user_service.update_last_activity("user_id")

        # 驗證
        user_repo.update_last_activity.assert_called_once_with("user_id")

    @pytest.mark.asyncio
    async def test_change_password_success(
        self, user_service, mock_repositories, sample_user
    ):
        """測試成功修改密碼"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_id.return_value = sample_user
        user_repo.change_password.return_value = True

        # Mock 密碼驗證和加密
        with patch("app.services.user_service.verify_password") as mock_verify:
            with patch("app.services.user_service.get_password_hash") as mock_hash:
                mock_verify.return_value = True
                mock_hash.return_value = "new_hashed_password"

                # 執行
                result = await user_service.change_password(
                    sample_user.id, "current_password", "new_password"
                )

                # 驗證
                assert result is True
                mock_verify.assert_called_once_with(
                    "current_password", sample_user.hashed_password
                )
                mock_hash.assert_called_once_with("new_password")
                user_repo.change_password.assert_called_once_with(
                    sample_user.id, "new_hashed_password"
                )

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(
        self, user_service, mock_repositories, sample_user
    ):
        """測試當前密碼錯誤"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_id.return_value = sample_user

        # Mock 密碼驗證失敗
        with patch("app.services.user_service.verify_password") as mock_verify:
            mock_verify.return_value = False

            # 執行並驗證拋出異常
            with pytest.raises(ValueError) as exc_info:
                await user_service.change_password(
                    sample_user.id, "wrong_password", "new_password"
                )

            assert "當前密碼不正確" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_with_password(
        self, user_service, mock_repositories, sample_user
    ):
        """測試更新使用者包含密碼"""
        user_repo, room_repo, message_repo = mock_repositories

        # Mock 設置
        user_repo.get_by_id.return_value = sample_user

        # Mock 密碼加密
        with patch("app.services.user_service.get_password_hash") as mock_hash:
            mock_hash.return_value = "new_hashed_password"

            # Mock 更新後的使用者
            updated_user = UserInDB(**sample_user.model_dump())
            user_repo.update.return_value = updated_user

            # 更新數據包含密碼
            update_data = UserUpdate(password="new_password")

            # 執行
            await user_service.update_user(sample_user.id, update_data, sample_user.id)

            # 驗證密碼被加密
            mock_hash.assert_called_once_with("new_password")
            # 驗證 update 被調用時使用了加密後的密碼
            user_repo.update.assert_called_once()
            call_args = user_repo.update.call_args[0]
            assert call_args[0] == sample_user.id
