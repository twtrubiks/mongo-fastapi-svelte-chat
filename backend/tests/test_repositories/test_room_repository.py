"""房間 Repository 測試"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.models.room import RoomInDB, RoomUpdate
from app.repositories.room_repository import RoomRepository


@pytest.mark.unit
class TestRoomRepository:
    """房間 Repository 整合測試類別"""

    @pytest.mark.asyncio
    async def test_create_room(self, db_manager_sync):
        """測試創建房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 創建房間資料
        owner_id = str(ObjectId())
        room_data = RoomInDB(
            name="測試房間",
            description="這是一個測試房間",
            owner_id=owner_id,
            members=[owner_id],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 執行創建
        result = await repo.create(room_data)

        # 驗證結果
        assert result is not None
        assert result.id is not None
        assert result.name == "測試房間"
        assert result.description == "這是一個測試房間"
        assert result.is_public is True
        assert len(result.members) == 1

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_manager_sync):
        """測試根據 ID 獲取房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 先創建一個房間
        room_data = RoomInDB(
            name="測試房間",
            description="這是一個測試房間",
            owner_id=str(ObjectId()),
            members=[str(ObjectId())],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 根據 ID 獲取房間
        retrieved_room = await repo.get_by_id(created_room.id)

        # 驗證結果
        assert retrieved_room is not None
        assert retrieved_room.id == created_room.id
        assert retrieved_room.name == "測試房間"
        assert retrieved_room.description == "這是一個測試房間"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_manager_sync):
        """測試獲取不存在的房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 嘗試獲取不存在的房間
        non_existent_id = str(ObjectId())
        result = await repo.get_by_id(non_existent_id)

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name(self, db_manager_sync):
        """測試根據名稱獲取房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 先創建一個房間
        room_data = RoomInDB(
            name="唯一房間名稱",
            description="這是一個唯一名稱的房間",
            owner_id=str(ObjectId()),
            members=[str(ObjectId())],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 根據名稱獲取房間
        retrieved_room = await repo.get_by_name("唯一房間名稱")

        # 驗證結果
        assert retrieved_room is not None
        assert retrieved_room.id == created_room.id
        assert retrieved_room.name == "唯一房間名稱"

    @pytest.mark.asyncio
    async def test_get_by_name_not_found(self, db_manager_sync):
        """測試獲取不存在名稱的房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 嘗試獲取不存在的房間
        result = await repo.get_by_name("不存在的房間名稱")

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_update_room(self, db_manager_sync):
        """測試更新房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 先創建一個房間
        room_data = RoomInDB(
            name="原始房間名稱",
            description="原始描述",
            owner_id=str(ObjectId()),
            members=[str(ObjectId())],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 更新房間
        update_data = RoomUpdate(name="更新後的房間名稱", description="更新後的描述")
        updated_room = await repo.update(created_room.id, update_data)

        # 驗證結果
        assert updated_room is not None
        assert updated_room.id == created_room.id
        assert updated_room.name == "更新後的房間名稱"
        assert updated_room.description == "更新後的描述"
        assert updated_room.updated_at > created_room.updated_at

    @pytest.mark.asyncio
    async def test_update_nonexistent_room(self, db_manager_sync):
        """測試更新不存在的房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 嘗試更新不存在的房間
        non_existent_id = str(ObjectId())
        update_data = RoomUpdate(name="新名稱")
        result = await repo.update(non_existent_id, update_data)

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_room(self, db_manager_sync):
        """測試刪除房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 先創建一個房間
        room_data = RoomInDB(
            name="要刪除的房間",
            description="這個房間將被刪除",
            owner_id=str(ObjectId()),
            members=[str(ObjectId())],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 刪除房間
        result = await repo.delete(created_room.id)

        # 驗證刪除成功
        assert result is True

        # 驗證房間確實被刪除
        deleted_room = await repo.get_by_id(created_room.id)
        assert deleted_room is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_room(self, db_manager_sync):
        """測試刪除不存在的房間"""
        repo = RoomRepository(db_manager_sync.database)

        # 嘗試刪除不存在的房間
        non_existent_id = str(ObjectId())
        result = await repo.delete(non_existent_id)

        # 驗證結果
        assert result is False

    @pytest.mark.asyncio
    async def test_add_member(self, db_manager_sync):
        """測試新增房間成員"""
        repo = RoomRepository(db_manager_sync.database)
        owner_id = str(ObjectId())
        new_member_id = str(ObjectId())

        # 先創建一個房間
        room_data = RoomInDB(
            name="測試房間",
            description="測試新增成員",
            owner_id=owner_id,
            members=[owner_id],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 新增成員
        result = await repo.add_member(created_room.id, new_member_id)

        # 驗證結果
        assert result is True

        # 驗證成員已被新增
        updated_room = await repo.get_by_id(created_room.id)
        assert updated_room is not None
        assert new_member_id in updated_room.members
        assert len(updated_room.members) == 2

    @pytest.mark.asyncio
    async def test_remove_member(self, db_manager_sync):
        """測試移除房間成員"""
        repo = RoomRepository(db_manager_sync.database)
        owner_id = str(ObjectId())
        member_id = str(ObjectId())

        # 先創建一個有兩個成員的房間
        room_data = RoomInDB(
            name="測試房間",
            description="測試移除成員",
            owner_id=owner_id,
            members=[owner_id, member_id],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 移除成員
        result = await repo.remove_member(created_room.id, member_id)

        # 驗證結果
        assert result is True

        # 驗證成員已被移除
        updated_room = await repo.get_by_id(created_room.id)
        assert updated_room is not None
        assert member_id not in updated_room.members
        assert len(updated_room.members) == 1
        assert owner_id in updated_room.members

    @pytest.mark.asyncio
    async def test_is_member(self, db_manager_sync):
        """測試檢查是否為房間成員"""
        repo = RoomRepository(db_manager_sync.database)
        owner_id = str(ObjectId())
        member_id = str(ObjectId())
        non_member_id = str(ObjectId())

        # 先創建一個房間
        room_data = RoomInDB(
            name="測試房間",
            description="測試成員檢查",
            owner_id=owner_id,
            members=[owner_id, member_id],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 檢查成員狀態
        assert await repo.is_member(created_room.id, owner_id) is True
        assert await repo.is_member(created_room.id, member_id) is True
        assert await repo.is_member(created_room.id, non_member_id) is False

    @pytest.mark.asyncio
    async def test_is_owner(self, db_manager_sync):
        """測試檢查是否為房間擁有者"""
        repo = RoomRepository(db_manager_sync.database)
        owner_id = str(ObjectId())
        member_id = str(ObjectId())

        # 先創建一個房間
        room_data = RoomInDB(
            name="測試房間",
            description="測試擁有者檢查",
            owner_id=owner_id,
            members=[owner_id, member_id],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 檢查擁有者狀態
        assert await repo.is_owner(created_room.id, owner_id) is True
        assert await repo.is_owner(created_room.id, member_id) is False

    @pytest.mark.asyncio
    async def test_get_member_count(self, db_manager_sync):
        """測試獲取房間成員數量"""
        repo = RoomRepository(db_manager_sync.database)
        owner_id = str(ObjectId())
        member1_id = str(ObjectId())
        member2_id = str(ObjectId())

        # 先創建一個房間
        room_data = RoomInDB(
            name="測試房間",
            description="測試成員數量",
            owner_id=owner_id,
            members=[owner_id, member1_id, member2_id],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 獲取成員數量
        count = await repo.get_member_count(created_room.id)

        # 驗證結果
        assert count == 3

    @pytest.mark.asyncio
    async def test_get_public_rooms(self, db_manager_sync):
        """測試獲取公開房間列表"""
        repo = RoomRepository(db_manager_sync.database)

        # 創建公開和私人房間
        for i in range(3):
            room_data = RoomInDB(
                name=f"公開房間 {i}",
                description=f"這是公開房間 {i}",
                owner_id=str(ObjectId()),
                members=[str(ObjectId())],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await repo.create(room_data)

        for i in range(2):
            room_data = RoomInDB(
                name=f"私人房間 {i}",
                description=f"這是私人房間 {i}",
                owner_id=str(ObjectId()),
                members=[str(ObjectId())],
                is_public=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await repo.create(room_data)

        # 獲取公開房間
        public_rooms = await repo.get_public_rooms()

        # 驗證結果
        assert public_rooms is not None
        assert len(public_rooms) >= 3
        assert all(room.is_public for room in public_rooms)

    @pytest.mark.asyncio
    async def test_get_user_rooms(self, db_manager_sync):
        """測試獲取使用者房間列表"""
        repo = RoomRepository(db_manager_sync.database)
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())

        # 創建使用者參與的房間
        for i in range(2):
            room_data = RoomInDB(
                name=f"使用者房間 {i}",
                description=f"使用者參與的房間 {i}",
                owner_id=str(ObjectId()),
                members=[user_id, str(ObjectId())],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await repo.create(room_data)

        # 創建使用者不參與的房間
        room_data = RoomInDB(
            name="其他房間",
            description="使用者不參與的房間",
            owner_id=other_user_id,
            members=[other_user_id],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        await repo.create(room_data)

        # 獲取使用者房間
        user_rooms = await repo.get_user_rooms(user_id)

        # 驗證結果
        assert user_rooms is not None
        assert len(user_rooms) >= 2
        assert all(user_id in room.members for room in user_rooms)

    @pytest.mark.asyncio
    async def test_check_room_name_exists(self, db_manager_sync):
        """測試檢查房間名稱是否存在"""
        repo = RoomRepository(db_manager_sync.database)

        # 先創建一個房間
        room_data = RoomInDB(
            name="存在的房間名稱",
            description="這個名稱已經存在",
            owner_id=str(ObjectId()),
            members=[str(ObjectId())],
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        await repo.create(room_data)

        # 檢查名稱是否存在
        assert await repo.check_room_name_exists("存在的房間名稱") is True
        assert await repo.check_room_name_exists("不存在的房間名稱") is False

    @pytest.mark.asyncio
    async def test_error_handling(self, db_manager_sync):
        """測試錯誤處理"""
        repo = RoomRepository(db_manager_sync.database)

        # 測試無效的 ObjectId
        result = await repo.get_by_id("invalid_id")
        assert result is None

        # 測試空字串 ID
        result = await repo.get_by_id("")
        assert result is None

        # 測試 None ID
        result = await repo.get_by_id(None)
        assert result is None
