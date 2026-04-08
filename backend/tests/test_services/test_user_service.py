"""
測試使用者服務層
使用 Mock 優先的方式測試所有功能
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.models.user import UserCreate, UserInDB, UserUpdate
from app.services.user_service import UserService


class TestUserService:
    """測試使用者服務"""

    @pytest.fixture
    def mock_user_repo(self):
        """Mock UserRepository"""
        return AsyncMock()

    @pytest.fixture
    def user_service(self, mock_user_repo):
        """創建使用者服務實例"""
        return UserService(mock_user_repo)

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
    async def test_create_user_success(self, user_service, mock_user_repo):
        """測試成功創建使用者"""
        user_repo = mock_user_repo

        # Mock 密碼加密
        with patch("app.services.user_service.get_password_hash") as mock_hash:
            mock_hash.return_value = "hashed_password"

            # Mock 唯一性檢查通過
            user_repo.get_by_username.return_value = None
            user_repo.get_by_email.return_value = None

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
    async def test_create_user_username_exists(self, user_service, mock_user_repo):
        """測試使用者名稱已存在"""
        user_repo = mock_user_repo

        # Mock 密碼加密
        with patch("app.services.user_service.get_password_hash") as mock_hash:
            mock_hash.return_value = "hashed_password"

            # Mock Service 層唯一性檢查：get_by_username 返回已存在的使用者
            user_repo.get_by_username.return_value = Mock()

            # 執行並驗證拋出異常
            with pytest.raises(ConflictError) as exc_info:
                await user_service.create_user(
                    UserCreate(
                        username="existing",
                        email="test@example.com",
                        password="password123",
                    )
                )

            assert "使用者名稱已存在" in str(exc_info.value)
            user_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_user_email_exists(self, user_service, mock_user_repo):
        """測試信箱已存在"""
        user_repo = mock_user_repo

        # Mock 密碼加密
        with patch("app.services.user_service.get_password_hash") as mock_hash:
            mock_hash.return_value = "hashed_password"

            # Mock Service 層唯一性檢查：username 不存在但 email 已存在
            user_repo.get_by_username.return_value = None
            user_repo.get_by_email.return_value = Mock()

            # 執行並驗證拋出異常
            with pytest.raises(ConflictError) as exc_info:
                await user_service.create_user(
                    UserCreate(
                        username="newuser",
                        email="existing@example.com",
                        password="password123",
                    )
                )

            assert "信箱已被使用" in str(exc_info.value)
            user_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, user_service, mock_user_repo, sample_user):
        """測試根據 ID 獲取使用者"""
        user_repo = mock_user_repo

        # Mock 返回使用者
        user_repo.get_by_id.return_value = sample_user

        # 執行
        result = await user_service.get_user_by_id(sample_user.id)

        # 驗證
        assert result is not None
        assert result.id == sample_user.id
        assert result.username == sample_user.username

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, user_service, mock_user_repo):
        """測試獲取不存在的使用者"""
        user_repo = mock_user_repo

        # Mock 使用者不存在
        user_repo.get_by_id.return_value = None

        # 執行並驗證拋出異常
        with pytest.raises(NotFoundError):
            await user_service.get_user_by_id("invalid_id")

    @pytest.mark.asyncio
    async def test_get_user_by_username(
        self, user_service, mock_user_repo, sample_user
    ):
        """測試根據用戶名獲取使用者"""
        user_repo = mock_user_repo

        # Mock 返回使用者
        user_repo.get_by_username.return_value = sample_user

        # 執行
        result = await user_service.get_user_by_username(sample_user.username)

        # 驗證
        assert result is not None
        assert result.username == sample_user.username

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
        self, user_service, mock_user_repo, sample_user
    ):
        """測試成功驗證使用者"""
        user_repo = mock_user_repo

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
                    assert result["user"].username == "testuser"
                    mock_verify.assert_called_once_with(
                        "password123", sample_user.hashed_password
                    )

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(
        self, user_service, mock_user_repo, sample_user
    ):
        """測試密碼錯誤"""
        user_repo = mock_user_repo

        # Mock 設置
        user_repo.get_by_username.return_value = sample_user

        # Mock 密碼驗證失敗
        with patch("app.services.user_service.verify_password") as mock_verify:
            mock_verify.return_value = False

            # 執行 — 應拋出 UnauthorizedError
            with pytest.raises(UnauthorizedError):
                await user_service.authenticate_user("testuser", "wrong_password")

    @pytest.mark.asyncio
    async def test_authenticate_user_inactive(
        self, user_service, mock_user_repo, sample_user
    ):
        """測試不活躍使用者"""
        user_repo = mock_user_repo

        # 設置使用者為不活躍
        sample_user.is_active = False
        user_repo.get_by_username.return_value = sample_user

        # Mock 密碼驗證成功
        with patch("app.services.user_service.verify_password") as mock_verify:
            mock_verify.return_value = True

            # 執行 — 應拋出 UnauthorizedError
            with pytest.raises(UnauthorizedError):
                await user_service.authenticate_user("testuser", "password123")

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_service, mock_user_repo, sample_user):
        """測試成功更新使用者"""
        user_repo = mock_user_repo

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
    async def test_update_user_permission_denied(self, user_service, sample_user):
        """測試無權限更新他人資料"""
        # 執行並驗證拋出異常
        with pytest.raises(ForbiddenError) as exc_info:
            await user_service.update_user(
                sample_user.id, UserUpdate(), "other_user_id"
            )

        assert "您只能更新自己的資料" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_email_exists(
        self, user_service, mock_user_repo, sample_user
    ):
        """測試更新信箱已存在"""
        user_repo = mock_user_repo

        # Mock 設置
        user_repo.get_by_id.return_value = sample_user

        # Mock 信箱已被其他使用者使用
        other_user = Mock(id="other_id", email="existing@example.com")
        user_repo.get_by_email.return_value = other_user

        # 執行並驗證拋出異常
        with pytest.raises(ConflictError) as exc_info:
            await user_service.update_user(
                sample_user.id, UserUpdate(email="existing@example.com"), sample_user.id
            )

        assert "信箱已被使用" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service, mock_user_repo, sample_user):
        """測試成功刪除使用者"""
        user_repo = mock_user_repo

        # Mock 刪除成功
        user_repo.delete.return_value = True

        # 執行
        await user_service.delete_user(sample_user.id, sample_user.id)

        # 驗證
        user_repo.delete.assert_called_once_with(sample_user.id)

    @pytest.mark.asyncio
    async def test_delete_user_permission_denied(self, user_service):
        """測試無權限刪除他人帳號"""
        # 執行並驗證拋出異常
        with pytest.raises(ForbiddenError) as exc_info:
            await user_service.delete_user("user_id", "other_user_id")

        assert "您只能刪除自己的帳號" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_with_password(
        self, user_service, mock_user_repo, sample_user
    ):
        """測試更新使用者包含密碼"""
        user_repo = mock_user_repo

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
