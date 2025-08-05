"""使用者 Repository 測試"""
import pytest
from datetime import datetime, UTC
from bson import ObjectId
from app.repositories.user_repository import UserRepository
from app.models.user import UserInDB, UserCreate, UserUpdate


@pytest.mark.unit
class TestUserRepository:
    """使用者 Repository 整合測試類別"""
    
    @pytest.mark.asyncio
    async def test_create_user(self, db_manager_sync):
        """測試創建使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 創建使用者資料
        user_data = UserInDB(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        # 執行創建
        result = await repo.create(user_data)
        
        # 驗證結果
        assert result is not None
        assert result.id is not None
        assert result.username == "testuser"
        assert result.email == "test@example.com"
        assert result.full_name == "Test User"
        assert result.is_active is True
    
    @pytest.mark.asyncio
    async def test_get_by_id(self, db_manager_sync):
        """測試根據 ID 獲取使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        
        # 根據 ID 獲取使用者
        retrieved_user = await repo.get_by_id(created_user.id)
        
        # 驗證結果
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == "testuser"
        assert retrieved_user.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_manager_sync):
        """測試獲取不存在的使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 嘗試獲取不存在的使用者
        non_existent_id = str(ObjectId())
        result = await repo.get_by_id(non_existent_id)
        
        # 驗證結果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_by_username(self, db_manager_sync):
        """測試根據使用者名稱獲取使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="unique_username",
            email="unique@example.com",
            full_name="Unique User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        
        # 根據使用者名稱獲取使用者
        retrieved_user = await repo.get_by_username("unique_username")
        
        # 驗證結果
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == "unique_username"
    
    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, db_manager_sync):
        """測試獲取不存在使用者名稱的使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 嘗試獲取不存在的使用者
        result = await repo.get_by_username("nonexistent_username")
        
        # 驗證結果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_by_email(self, db_manager_sync):
        """測試根據電子郵件獲取使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="emailtest",
            email="unique_email@example.com",
            full_name="Email Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        
        # 根據電子郵件獲取使用者
        retrieved_user = await repo.get_by_email("unique_email@example.com")
        
        # 驗證結果
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.email == "unique_email@example.com"
    
    @pytest.mark.asyncio
    async def test_get_by_email_not_found(self, db_manager_sync):
        """測試獲取不存在電子郵件的使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 嘗試獲取不存在的使用者
        result = await repo.get_by_email("nonexistent@example.com")
        
        # 驗證結果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_user(self, db_manager_sync):
        """測試更新使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="updatetest",
            email="update@example.com",
            full_name="Original Name",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        
        # 更新使用者
        update_data = UserUpdate(
            full_name="Updated Name",
            email="updated@example.com"
        )
        updated_user = await repo.update(created_user.id, update_data)
        
        # 驗證結果
        assert updated_user is not None
        assert updated_user.id == created_user.id
        assert updated_user.full_name == "Updated Name"
        assert updated_user.email == "updated@example.com"
        assert updated_user.username == "updatetest"  # 應該保持不變
        assert updated_user.updated_at > created_user.updated_at
    
    @pytest.mark.asyncio
    async def test_update_user_avatar(self, db_manager_sync):
        """測試更新使用者頭像"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="avatartest",
            email="avatar@example.com",
            full_name="Avatar Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        assert created_user.avatar is None  # 初始沒有頭像
        
        # 更新頭像
        update_data = UserUpdate(
            avatar="/api/files/image/test_avatar.png"
        )
        updated_user = await repo.update(created_user.id, update_data)
        
        # 驗證結果
        assert updated_user is not None
        assert updated_user.id == created_user.id
        assert updated_user.avatar == "/api/files/image/test_avatar.png"
        assert updated_user.username == "avatartest"  # 其他欄位應該保持不變
        assert updated_user.email == "avatar@example.com"
        assert updated_user.full_name == "Avatar Test User"
        
        # 再次更新頭像
        update_data = UserUpdate(
            avatar="/api/files/image/new_avatar.png"
        )
        updated_user2 = await repo.update(created_user.id, update_data)
        
        # 驗證更新成功
        assert updated_user2 is not None
        assert updated_user2.avatar == "/api/files/image/new_avatar.png"
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_user(self, db_manager_sync):
        """測試更新不存在的使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 嘗試更新不存在的使用者
        non_existent_id = str(ObjectId())
        update_data = UserUpdate(full_name="New Name")
        result = await repo.update(non_existent_id, update_data)
        
        # 驗證結果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_user(self, db_manager_sync):
        """測試軟刪除使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="deletetest",
            email="delete@example.com",
            full_name="Delete Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        
        # 軟刪除使用者
        result = await repo.delete(created_user.id)
        
        # 驗證刪除成功
        assert result is True
        
        # 驗證使用者被軟刪除（仍存在但標記為不活躍）
        deleted_user = await repo.get_by_id(created_user.id)
        assert deleted_user is not None
        assert deleted_user.is_active is False
    
    @pytest.mark.asyncio
    async def test_hard_delete_user(self, db_manager_sync):
        """測試硬刪除使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="harddeletetest",
            email="harddelete@example.com",
            full_name="Hard Delete Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        
        # 硬刪除使用者
        result = await repo.hard_delete(created_user.id)
        
        # 驗證刪除成功
        assert result is True
        
        # 驗證使用者完全被刪除
        deleted_user = await repo.get_by_id(created_user.id)
        assert deleted_user is None
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_user(self, db_manager_sync):
        """測試刪除不存在的使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 嘗試刪除不存在的使用者
        non_existent_id = str(ObjectId())
        result = await repo.delete(non_existent_id)
        
        # 驗證結果
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_username_exists(self, db_manager_sync):
        """測試檢查使用者名稱是否存在"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="existing_username",
            email="existing@example.com",
            full_name="Existing User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        await repo.create(user_data)
        
        # 檢查使用者名稱是否存在
        assert await repo.check_username_exists("existing_username") is True
        assert await repo.check_username_exists("nonexistent_username") is False
    
    @pytest.mark.asyncio
    async def test_check_email_exists(self, db_manager_sync):
        """測試檢查電子郵件是否存在"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="emailcheck",
            email="existing_email@example.com",
            full_name="Email Check User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        await repo.create(user_data)
        
        # 檢查電子郵件是否存在
        assert await repo.check_email_exists("existing_email@example.com") is True
        assert await repo.check_email_exists("nonexistent@example.com") is False
    
    @pytest.mark.asyncio
    async def test_update_last_login(self, db_manager_sync):
        """測試更新最後登入時間"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="logintest",
            email="login@example.com",
            full_name="Login Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        assert created_user.last_login_at is None
        
        # 更新最後登入時間
        result = await repo.update_last_login(created_user.id)
        
        # 驗證結果
        assert result is True
        
        # 檢查最後登入時間已更新
        updated_user = await repo.get_by_id(created_user.id)
        assert updated_user is not None
        assert updated_user.last_login_at is not None
    
    @pytest.mark.asyncio
    async def test_change_password(self, db_manager_sync):
        """測試更改密碼"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="passwordtest",
            email="password@example.com",
            full_name="Password Test User",
            hashed_password="old_hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        
        # 更改密碼
        new_hashed_password = "new_hashed_password"
        result = await repo.change_password(created_user.id, new_hashed_password)
        
        # 驗證結果
        assert result is True
        
        # 檢查密碼已更新
        updated_user = await repo.get_by_id(created_user.id)
        assert updated_user is not None
        assert updated_user.hashed_password == new_hashed_password
    
    @pytest.mark.asyncio
    async def test_activate_deactivate_user(self, db_manager_sync):
        """測試啟用和停用使用者"""
        repo = UserRepository(db_manager_sync.database)
        
        # 先創建一個使用者
        user_data = UserInDB(
            username="activatetest",
            email="activate@example.com",
            full_name="Activate Test User",
            hashed_password="hashed_password_123",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_user = await repo.create(user_data)
        assert created_user is not None
        assert created_user.is_active is True
        
        # 停用使用者
        result = await repo.deactivate_user(created_user.id)
        assert result is True
        
        # 檢查使用者已被停用
        deactivated_user = await repo.get_by_id(created_user.id)
        assert deactivated_user is not None
        assert deactivated_user.is_active is False
        
        # 重新啟用使用者
        result = await repo.activate_user(created_user.id)
        assert result is True
        
        # 檢查使用者已被啟用
        activated_user = await repo.get_by_id(created_user.id)
        assert activated_user is not None
        assert activated_user.is_active is True
    
    @pytest.mark.asyncio
    async def test_count_users(self, db_manager_sync):
        """測試統計使用者數量"""
        repo = UserRepository(db_manager_sync.database)
        
        # 創建活躍使用者
        for i in range(3):
            user_data = UserInDB(
                username=f"active_user_{i}",
                email=f"active_{i}@example.com",
                full_name=f"Active User {i}",
                hashed_password="hashed_password_123",
                is_active=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(user_data)
        
        # 創建非活躍使用者
        for i in range(2):
            user_data = UserInDB(
                username=f"inactive_user_{i}",
                email=f"inactive_{i}@example.com",
                full_name=f"Inactive User {i}",
                hashed_password="hashed_password_123",
                is_active=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(user_data)
        
        # 統計活躍使用者
        active_count = await repo.count_users(include_inactive=False)
        assert active_count >= 3
        
        # 統計所有使用者
        total_count = await repo.count_users(include_inactive=True)
        assert total_count >= 5
        assert total_count > active_count
    
    @pytest.mark.asyncio
    async def test_error_handling(self, db_manager_sync):
        """測試錯誤處理"""
        repo = UserRepository(db_manager_sync.database)
        
        # 測試無效的 ObjectId
        result = await repo.get_by_id("invalid_id")
        assert result is None
        
        # 測試空字串 ID
        result = await repo.get_by_id("")
        assert result is None
        
        # 測試 None ID
        result = await repo.get_by_id(None)
        assert result is None