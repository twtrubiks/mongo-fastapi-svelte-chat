"""房間 Repository 測試"""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.models.enums import MemberRole
from app.models.room import RoomInDB, RoomUpdate
from app.repositories.room_repository import RoomRepository


@pytest.mark.unit
class TestRoomRepository:
    """房間 Repository 整合測試類別"""

    @pytest.mark.asyncio
    async def test_create_room(self, db_manager):
        """測試創建房間"""
        repo = RoomRepository(db_manager.database)

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
    async def test_get_by_id(self, db_manager):
        """測試根據 ID 獲取房間"""
        repo = RoomRepository(db_manager.database)

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
    async def test_get_by_id_not_found(self, db_manager):
        """測試獲取不存在的房間"""
        repo = RoomRepository(db_manager.database)

        # 嘗試獲取不存在的房間
        non_existent_id = str(ObjectId())
        result = await repo.get_by_id(non_existent_id)

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_name(self, db_manager):
        """測試根據名稱獲取房間"""
        repo = RoomRepository(db_manager.database)

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
    async def test_get_by_name_not_found(self, db_manager):
        """測試獲取不存在名稱的房間"""
        repo = RoomRepository(db_manager.database)

        # 嘗試獲取不存在的房間
        result = await repo.get_by_name("不存在的房間名稱")

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_update_room(self, db_manager):
        """測試更新房間"""
        repo = RoomRepository(db_manager.database)

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
        assert updated_room.updated_at >= created_room.updated_at

    @pytest.mark.asyncio
    async def test_update_nonexistent_room(self, db_manager):
        """測試更新不存在的房間"""
        repo = RoomRepository(db_manager.database)

        # 嘗試更新不存在的房間
        non_existent_id = str(ObjectId())
        update_data = RoomUpdate(name="新名稱")
        result = await repo.update(non_existent_id, update_data)

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_room(self, db_manager):
        """測試刪除房間"""
        repo = RoomRepository(db_manager.database)

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
    async def test_delete_nonexistent_room(self, db_manager):
        """測試刪除不存在的房間"""
        repo = RoomRepository(db_manager.database)

        # 嘗試刪除不存在的房間
        non_existent_id = str(ObjectId())
        result = await repo.delete(non_existent_id)

        # 驗證結果
        assert result is False

    @pytest.mark.asyncio
    async def test_add_member(self, db_manager):
        """測試新增房間成員"""
        repo = RoomRepository(db_manager.database)
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

        # 新增成員（原子操作：含 max_members 檢查 + 角色設定）
        result = await repo.add_member(
            created_room.id, new_member_id, MemberRole.MEMBER
        )

        # 驗證結果
        assert result is True

        # 驗證成員已被新增且角色已設定
        updated_room = await repo.get_by_id(created_room.id)
        assert updated_room is not None
        assert new_member_id in updated_room.members
        assert len(updated_room.members) == 2
        assert updated_room.member_roles.get(new_member_id) == MemberRole.MEMBER

    @pytest.mark.asyncio
    async def test_add_member_rejected_when_room_full(self, db_manager):
        """max_members 由 update 的原子條件把關（service 先查後寫擋不住併發）"""
        repo = RoomRepository(db_manager.database)
        members = [str(ObjectId()), str(ObjectId())]
        room = await repo.create(
            RoomInDB(
                name="full room",
                owner_id=members[0],
                members=members,
                member_roles={
                    members[0]: MemberRole.OWNER,
                    members[1]: MemberRole.MEMBER,
                },
                max_members=2,
            )
        )
        newcomer = str(ObjectId())

        assert await repo.add_member(room.id, newcomer, MemberRole.MEMBER) is False

        unchanged = await repo.get_by_id(room.id)
        assert unchanged.members == members
        assert newcomer not in unchanged.member_roles

    @pytest.mark.asyncio
    async def test_add_member_fills_last_seat(self, db_manager):
        repo = RoomRepository(db_manager.database)
        owner = str(ObjectId())
        room = await repo.create(
            RoomInDB(
                name="one seat left", owner_id=owner, members=[owner], max_members=2
            )
        )
        newcomer = str(ObjectId())

        assert await repo.add_member(room.id, newcomer, MemberRole.MEMBER) is True
        assert (
            await repo.add_member(room.id, str(ObjectId()), MemberRole.MEMBER) is False
        )

        updated = await repo.get_by_id(room.id)
        assert updated.members == [owner, newcomer]
        assert updated.member_roles[newcomer] == MemberRole.MEMBER

    @pytest.mark.asyncio
    async def test_remove_member(self, db_manager):
        """測試移除房間成員（同時清除 member_roles）"""
        repo = RoomRepository(db_manager.database)
        owner_id = str(ObjectId())
        member_id = str(ObjectId())

        # 先創建一個有兩個成員的房間（含 member_roles）
        room_data = RoomInDB(
            name="測試房間",
            description="測試移除成員",
            owner_id=owner_id,
            members=[owner_id, member_id],
            member_roles={owner_id: MemberRole.OWNER, member_id: MemberRole.MEMBER},
            is_public=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_room = await repo.create(room_data)
        assert created_room is not None

        # 不是成員的使用者：不動資料，回傳 False
        assert await repo.remove_member(created_room.id, str(ObjectId())) is False

        # 移除成員
        result = await repo.remove_member(created_room.id, member_id)

        # 驗證結果
        assert result is True
        # 已移除後再移除一次：回傳 False（同時離開與被移出時只有一方成功）
        assert await repo.remove_member(created_room.id, member_id) is False

        # 驗證成員已被移除
        updated_room = await repo.get_by_id(created_room.id)
        assert updated_room is not None
        assert member_id not in updated_room.members
        assert len(updated_room.members) == 1
        assert owner_id in updated_room.members

        # 驗證 member_roles 已同步清除
        assert member_id not in updated_room.member_roles
        assert owner_id in updated_room.member_roles

    @pytest.mark.asyncio
    async def test_ban_and_unban(self, db_manager):
        """封鎖時一併移出成員；被封鎖的人加不進來（原子條件），解除後可以"""
        repo = RoomRepository(db_manager.database)
        owner_id, member_id, other_id = (str(ObjectId()) for _ in range(3))
        room = await repo.create(
            RoomInDB(
                name="封鎖測試",
                owner_id=owner_id,
                members=[owner_id, member_id],
                member_roles={owner_id: MemberRole.OWNER, member_id: MemberRole.MEMBER},
            )
        )

        # 回傳更新前的房間，呼叫端據此判斷對方原本是否為成員
        before = await repo.ban_user(room.id, member_id)
        assert member_id in before.members
        banned = await repo.get_by_id(room.id)
        assert banned.banned_users == [member_id]
        assert member_id not in banned.members
        assert member_id not in banned.member_roles

        # 不是成員也能封鎖；再封鎖一次不重複
        assert other_id not in (await repo.ban_user(room.id, other_id)).members
        again = await repo.ban_user(room.id, other_id)
        assert again.banned_users == [member_id, other_id]
        assert (await repo.get_by_id(room.id)).banned_users == [member_id, other_id]
        assert await repo.ban_user(str(ObjectId()), other_id) is None

        assert await repo.add_member(room.id, member_id, MemberRole.MEMBER) is False

        assert await repo.unban_user(room.id, owner_id) is False
        assert await repo.unban_user(room.id, member_id) is True
        assert (await repo.get_by_id(room.id)).banned_users == [other_id]
        assert await repo.add_member(room.id, member_id, MemberRole.MEMBER) is True

    @pytest.mark.asyncio
    async def test_room_without_ban_field_accepts_members(self, db_manager):
        """封鎖功能之前建立的房間沒有 banned_users 欄位，照常可加入"""
        repo = RoomRepository(db_manager.database)
        owner_id = str(ObjectId())
        room_id = await repo.insert_one(
            {
                "name": "舊房間",
                "owner_id": owner_id,
                "members": [owner_id],
                "max_members": 10,
            }
        )

        assert (
            await repo.add_member(room_id, str(ObjectId()), MemberRole.MEMBER) is True
        )
        assert (await repo.get_by_id(room_id)).banned_users == []

    @pytest.mark.asyncio
    async def test_is_member(self, db_manager):
        """測試檢查是否為房間成員"""
        repo = RoomRepository(db_manager.database)
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
        # 房間不存在或 ID 格式錯誤都不是成員
        assert await repo.is_member(str(ObjectId()), owner_id) is False
        assert await repo.is_member("not-an-object-id", owner_id) is False

    @pytest.mark.asyncio
    async def test_member_id_queries(self, db_manager):
        """成員 ID 與使用者所屬房間：房間不存在或 ID 格式錯誤時略過"""
        repo = RoomRepository(db_manager.database)
        alice, bob = str(ObjectId()), str(ObjectId())

        async def make(name: str, members: list[str]) -> str:
            room = await repo.create(
                RoomInDB(
                    name=name,
                    owner_id=members[0],
                    members=members,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            return room.id

        shared = await make("共同房", [alice, bob])
        alice_only = await make("alice 的房", [alice])
        missing = str(ObjectId())

        assert sorted(await repo.get_member_ids(shared)) == sorted([alice, bob])
        assert await repo.get_member_ids(missing) == []
        assert await repo.get_member_ids("lobby") == []

        rooms = [shared, alice_only, missing, "lobby"]
        assert sorted(await repo.get_room_ids_with_member(alice, rooms)) == sorted(
            [shared, alice_only]
        )
        assert await repo.get_room_ids_with_member(bob, rooms) == [shared]
        assert await repo.get_room_ids_with_member(bob, ["lobby"]) == []

    @pytest.mark.asyncio
    async def test_get_public_rooms(self, db_manager):
        """測試獲取公開房間列表"""
        repo = RoomRepository(db_manager.database)

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
    async def test_get_user_rooms(self, db_manager):
        """測試獲取使用者房間列表"""
        repo = RoomRepository(db_manager.database)
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
    async def test_get_rooms_for_user(self, db_manager):
        """測試獲取公開房間 + 使用者已加入的私人房間"""
        repo = RoomRepository(db_manager.database)
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())

        # 創建公開房間（使用者未加入）→ 應出現
        await repo.create(
            RoomInDB(
                name="公開房間",
                description="所有人可見",
                owner_id=other_user_id,
                members=[other_user_id],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 創建使用者已加入的私人房間 → 應出現
        await repo.create(
            RoomInDB(
                name="已加入私人房間",
                description="使用者已加入",
                owner_id=other_user_id,
                members=[other_user_id, user_id],
                is_public=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 創建使用者未加入的私人房間 → 不應出現
        await repo.create(
            RoomInDB(
                name="未加入私人房間",
                description="使用者未加入",
                owner_id=other_user_id,
                members=[other_user_id],
                is_public=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 執行查詢
        rooms = await repo.get_rooms_for_user(user_id)
        room_names = [r.name for r in rooms]

        # 驗證：公開 + 已加入私人，不含未加入私人
        assert "公開房間" in room_names
        assert "已加入私人房間" in room_names
        assert "未加入私人房間" not in room_names

    @pytest.mark.asyncio
    async def test_get_rooms_for_user_pagination(self, db_manager):
        """測試 get_rooms_for_user 分頁功能"""
        repo = RoomRepository(db_manager.database)
        user_id = str(ObjectId())

        # 創建 5 個公開房間
        for i in range(5):
            await repo.create(
                RoomInDB(
                    name=f"分頁房間 {i}",
                    description=f"分頁測試 {i}",
                    owner_id=str(ObjectId()),
                    members=[str(ObjectId())],
                    is_public=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )

        # 取前 2 筆
        page1 = await repo.get_rooms_for_user(user_id, skip=0, limit=2)
        assert len(page1) == 2

        # 取第 3 筆起的 2 筆
        page2 = await repo.get_rooms_for_user(user_id, skip=2, limit=2)
        assert len(page2) == 2

        # 兩頁不應重疊
        page1_ids = {r.id for r in page1}
        page2_ids = {r.id for r in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_search_rooms(self, db_manager):
        """測試搜尋房間（名稱和描述）"""
        repo = RoomRepository(db_manager.database)

        # 名稱包含關鍵字的公開房間
        await repo.create(
            RoomInDB(
                name="Python 討論區",
                description="程式語言討論",
                owner_id=str(ObjectId()),
                members=[str(ObjectId())],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 描述包含關鍵字的公開房間
        await repo.create(
            RoomInDB(
                name="一般閒聊",
                description="歡迎討論 Python 話題",
                owner_id=str(ObjectId()),
                members=[str(ObjectId())],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 名稱包含關鍵字的私人房間
        await repo.create(
            RoomInDB(
                name="Python 私人群組",
                description="私密討論",
                owner_id=str(ObjectId()),
                members=[str(ObjectId())],
                is_public=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 搜尋 "Python"（public_only=True）
        results = await repo.search_rooms("Python", public_only=True)
        result_names = [r.name for r in results]
        assert "Python 討論區" in result_names
        assert "一般閒聊" in result_names  # 描述匹配
        assert "Python 私人群組" not in result_names  # 私人被排除

        # 搜尋 "Python"（public_only=False）
        results_all = await repo.search_rooms("Python", public_only=False)
        result_names_all = [r.name for r in results_all]
        assert "Python 私人群組" in result_names_all  # 私人也應出現

        # 搜尋不存在的關鍵字
        results_empty = await repo.search_rooms("不存在的關鍵字xyz")
        assert len(results_empty) == 0

    @pytest.mark.asyncio
    async def test_get_explore_rooms(self, db_manager):
        """測試探索用房間列表：排除使用者已加入的公開房間"""
        repo = RoomRepository(db_manager.database)
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())

        # 公開 + 使用者未加入 → 應出現
        await repo.create(
            RoomInDB(
                name="可探索房間",
                description="",
                owner_id=other_user_id,
                members=[other_user_id],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 公開 + 使用者已加入 → 不應出現
        await repo.create(
            RoomInDB(
                name="已加入公開房間",
                description="",
                owner_id=other_user_id,
                members=[other_user_id, user_id],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 私人 + 使用者未加入 → 不應出現（非公開）
        await repo.create(
            RoomInDB(
                name="私人房間",
                description="",
                owner_id=other_user_id,
                members=[other_user_id],
                is_public=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        rooms = await repo.get_explore_rooms(user_id)
        room_names = [r.name for r in rooms]

        assert "可探索房間" in room_names
        assert "已加入公開房間" not in room_names
        assert "私人房間" not in room_names

    @pytest.mark.asyncio
    async def test_search_rooms_exclude_user(self, db_manager):
        """測試搜尋時排除使用者已加入的房間"""
        repo = RoomRepository(db_manager.database)
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())

        # 使用者未加入 → 搜尋應出現
        await repo.create(
            RoomInDB(
                name="FastAPI 新手",
                description="",
                owner_id=other_user_id,
                members=[other_user_id],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 使用者已加入 → 搜尋應排除
        await repo.create(
            RoomInDB(
                name="FastAPI 進階",
                description="",
                owner_id=other_user_id,
                members=[other_user_id, user_id],
                is_public=True,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )

        # 有 exclude_user_id
        results = await repo.search_rooms(
            "FastAPI", public_only=True, exclude_user_id=user_id
        )
        result_names = [r.name for r in results]
        assert "FastAPI 新手" in result_names
        assert "FastAPI 進階" not in result_names

        # 無 exclude_user_id → 兩個都出現
        results_all = await repo.search_rooms("FastAPI", public_only=True)
        result_names_all = [r.name for r in results_all]
        assert "FastAPI 新手" in result_names_all
        assert "FastAPI 進階" in result_names_all

    @pytest.mark.asyncio
    async def test_error_handling(self, db_manager):
        """測試錯誤處理"""
        repo = RoomRepository(db_manager.database)

        # 測試無效的 ObjectId
        result = await repo.get_by_id("invalid_id")
        assert result is None

        # 測試空字串 ID
        result = await repo.get_by_id("")
        assert result is None

        # 測試 None ID
        result = await repo.get_by_id(None)
        assert result is None


async def _insert_rooms(collection, owner_id: str, rows):
    """依序插入房間（_id 遞增）；rows 為 (名稱, created_at 分鐘, updated_at 分鐘)"""
    base = datetime(2026, 1, 1)
    await collection.insert_many(
        [
            {
                "_id": ObjectId(),
                **RoomInDB(
                    name=name,
                    owner_id=owner_id,
                    members=[owner_id],
                    created_at=base + timedelta(minutes=created),
                    updated_at=base + timedelta(minutes=updated),
                ).model_dump(exclude={"id"}),
            }
            for name, created, updated in rows
        ]
    )


@pytest.mark.unit
class TestRoomListOrdering:
    """各房間列表的排序（刻意讓排序欄位與 _id 順序不一致）"""

    @pytest.mark.asyncio
    async def test_lists_sorted_by_created_at(self, db_manager):
        """公開 / 可見 / 探索列表依 created_at 由新到舊"""
        repo = RoomRepository(db_manager.database)
        # created_at：b 最新、a 次之、c 最舊
        await _insert_rooms(
            repo.collection, str(ObjectId()), [("a", 1, 0), ("b", 2, 0), ("c", 0, 0)]
        )
        outsider = str(ObjectId())

        public = await repo.get_public_rooms()
        for_user = await repo.get_rooms_for_user(outsider)
        explore = await repo.get_explore_rooms(outsider)

        for rooms in (public, for_user, explore):
            assert [room.name for room in rooms] == ["b", "a", "c"]

    @pytest.mark.asyncio
    async def test_my_rooms_by_updated_at_and_search_by_name(self, db_manager):
        """「我的房間」依最近更新由新到舊；搜尋結果依名稱字母序"""
        repo = RoomRepository(db_manager.database)
        owner_id = str(ObjectId())
        # updated_at：room c 最新、room b 次之、room a 最舊
        await _insert_rooms(
            repo.collection,
            owner_id,
            [("room b", 0, 1), ("room a", 0, 0), ("room c", 0, 2)],
        )

        mine = await repo.get_user_rooms(owner_id)
        found = await repo.search_rooms("room")

        assert [room.name for room in mine] == ["room c", "room b", "room a"]
        assert [room.name for room in found] == ["room a", "room b", "room c"]


@pytest.mark.unit
class TestMembershipLogging:
    """成員異動的 log 只在實際成功時記錄（失敗時不可誤記為已加入 / 已移除）"""

    @pytest.mark.asyncio
    async def test_logs_only_successful_changes(self, db_manager, caplog):
        repo = RoomRepository(db_manager.database)
        owner_id = str(ObjectId())
        room = await repo.create(
            RoomInDB(
                name="log room", owner_id=owner_id, members=[owner_id], max_members=2
            )
        )
        joiner, latecomer = str(ObjectId()), str(ObjectId())
        missing_room = str(ObjectId())
        caplog.set_level(logging.INFO, logger="app.repositories.room_repository")

        assert await repo.add_member(room.id, joiner, MemberRole.MEMBER) is True
        # 房間已滿
        assert await repo.add_member(room.id, latecomer, MemberRole.MEMBER) is False
        assert await repo.remove_member(room.id, joiner) is True
        assert await repo.remove_member(missing_room, joiner) is False

        logged = [
            record.getMessage()
            for record in caplog.records
            if record.name == "app.repositories.room_repository"
        ]
        assert len(logged) == 2
        assert all(joiner in message and room.id in message for message in logged)
        assert not any(latecomer in m or missing_room in m for m in logged)


@pytest.mark.unit
class TestRoomRepositoryErrorPropagation:
    """驗證 DB 異常正確傳播而非被吞掉"""

    @pytest.mark.asyncio
    async def test_find_propagates_db_error(self, db_manager):
        """測試查詢時 DB 異常正確傳播"""
        repo = RoomRepository(db_manager.database)
        with patch.object(
            repo.collection, "find_one", side_effect=PyMongoError("connection lost")
        ):
            with pytest.raises(PyMongoError):
                await repo.get_by_id(str(ObjectId()))

    @pytest.mark.asyncio
    async def test_insert_propagates_db_error(self, db_manager):
        """測試寫入時 DB 異常正確傳播"""
        repo = RoomRepository(db_manager.database)
        with patch.object(
            repo.collection, "insert_one", side_effect=PyMongoError("disk full")
        ):
            with pytest.raises(PyMongoError):
                room_data = RoomInDB(
                    name="test-room",
                    description="Test Room",
                    owner_id=str(ObjectId()),
                    members=[str(ObjectId())],
                    is_public=True,
                    max_members=100,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                await repo.create(room_data)

    @pytest.mark.asyncio
    async def test_delete_propagates_db_error(self, db_manager):
        """測試刪除時 DB 異常正確傳播"""
        repo = RoomRepository(db_manager.database)
        with patch.object(
            repo.collection, "delete_one", side_effect=PyMongoError("write conflict")
        ):
            with pytest.raises(PyMongoError):
                await repo.delete(str(ObjectId()))
