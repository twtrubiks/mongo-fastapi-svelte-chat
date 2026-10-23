"""Repository 寫入時間戳契約

時間戳一律取「當下」並截斷到毫秒（MongoDB 的儲存精度），因此方法回傳的值、
DB 讀回的值與當下時間三者必須完全相等。以固定時間（微秒 500_100）凍結 now，
截斷錯誤（變成整秒、或非毫秒倍數）都會直接反映在比對上。
"""

from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from bson import ObjectId

from app.models.enums import MemberRole
from app.models.message import MessageInDB, MessageStatus, MessageUpdate
from app.models.room import RoomInDB, RoomUpdate
from app.repositories.message_repository import MessageRepository
from app.repositories.room_repository import RoomRepository

BASE = "app.repositories.base"
MESSAGE_REPO = "app.repositories.message_repository"

CREATED = datetime(2026, 1, 2, 3, 4, 5, 500_100, tzinfo=UTC)
UPDATED = datetime(2026, 1, 2, 3, 9, 7, 500_100, tzinfo=UTC)


def _stored(at: datetime) -> datetime:
    """當下時間截斷到毫秒後、MongoDB 讀回的樣子（naive UTC）"""
    return at.replace(microsecond=at.microsecond // 1000 * 1000, tzinfo=None)


@contextmanager
def _frozen_now(at: datetime, *modules: str):
    """固定指定模組內的 datetime.now()（以 datetime 子類別實作，isinstance 判斷不受影響）"""

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant

    instant = _FrozenDatetime.fromisoformat(at.isoformat())
    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"{module}.datetime", _FrozenDatetime))
        yield


def _room(owner_id: str, member_id: str) -> RoomInDB:
    # 模型自帶的時間戳刻意設成很久以前，確保結果來自 insert_one 而非模型
    long_ago = datetime(2000, 1, 1, tzinfo=UTC)
    return RoomInDB(
        name="時間戳房間",
        owner_id=owner_id,
        owner_name="owner",
        members=[owner_id, member_id],
        member_roles={owner_id: MemberRole.OWNER, member_id: MemberRole.MEMBER},
        created_at=long_ago,
        updated_at=long_ago,
    )


async def _create_message(repo: MessageRepository) -> MessageInDB:
    with _frozen_now(CREATED, BASE):
        return await repo.create(
            MessageInDB(
                room_id=str(ObjectId()),
                user_id=str(ObjectId()),
                username="testuser",
                content="原始內容",
            )
        )


@pytest.mark.unit
class TestInsertTimestamps:
    """BaseRepository.create / insert_one"""

    @pytest.mark.asyncio
    async def test_create_persists_model_fields_with_truncated_now(self, db_manager):
        """DB 文件恰為模型欄位（不多存 id 或其他欄位），時間戳為截斷到毫秒的當下，回傳值與 DB 一致"""
        repo = RoomRepository(db_manager.database)
        owner_id, member_id = str(ObjectId()), str(ObjectId())
        room = _room(owner_id, member_id)

        with _frozen_now(CREATED, BASE):
            created = await repo.create(room)

        raw = await db_manager.database.rooms.find_one({"_id": ObjectId(created.id)})
        assert raw == {
            "_id": ObjectId(created.id),
            **room.model_dump(exclude={"id"}),
            "created_at": _stored(CREATED),
            "updated_at": _stored(CREATED),
        }
        assert created.created_at == created.updated_at == _stored(CREATED)
        assert created == await repo.get_by_id(created.id)


@pytest.mark.unit
class TestUpdateTimestamps:
    """BaseRepository.update_one：不論是否帶 $set，updated_at 都刷新為截斷到毫秒的當下"""

    @pytest.mark.asyncio
    async def test_set_update_refreshes_updated_at(self, db_manager):
        repo = RoomRepository(db_manager.database)
        with _frozen_now(CREATED, BASE):
            created = await repo.create(_room(str(ObjectId()), str(ObjectId())))

        with _frozen_now(UPDATED, BASE):
            updated = await repo.update(created.id, RoomUpdate(description="新描述"))

        assert updated.description == "新描述"
        assert updated.created_at == _stored(CREATED)
        assert updated.updated_at == _stored(UPDATED)

    @pytest.mark.asyncio
    async def test_update_without_set_refreshes_updated_at(self, db_manager):
        """remove_member 只有 $pull / $unset，updated_at 仍須更新"""
        repo = RoomRepository(db_manager.database)
        owner_id, member_id = str(ObjectId()), str(ObjectId())
        with _frozen_now(CREATED, BASE):
            created = await repo.create(_room(owner_id, member_id))

        with _frozen_now(UPDATED, BASE):
            assert await repo.remove_member(created.id, member_id) is True

        raw = await db_manager.database.rooms.find_one({"_id": ObjectId(created.id)})
        assert raw["members"] == [owner_id]
        assert raw["member_roles"] == {owner_id: MemberRole.OWNER}
        assert raw["created_at"] == _stored(CREATED)
        assert raw["updated_at"] == _stored(UPDATED)
        assert set(raw) == set(RoomInDB.model_fields) - {"id"} | {"_id"}


@pytest.mark.unit
class TestMessageEditTimestamps:
    """MessageRepository.update / delete 的 edited_at"""

    @pytest.mark.asyncio
    async def test_edit_stamps_edited_at(self, db_manager):
        repo = MessageRepository(db_manager.database)
        message = await _create_message(repo)

        with _frozen_now(UPDATED, BASE, MESSAGE_REPO):
            edited = await repo.update(message.id, MessageUpdate(content="新內容"))

        assert edited.content == "新內容"
        assert edited.edited is True
        assert edited.edited_at == edited.updated_at == _stored(UPDATED)
        assert edited.created_at == _stored(CREATED)

    @pytest.mark.asyncio
    async def test_soft_delete_marks_edited(self, db_manager):
        """軟刪除：狀態、替換內容、edited 標記與時間一次寫入，其餘欄位不變"""
        repo = MessageRepository(db_manager.database)
        message = await _create_message(repo)
        collection = db_manager.database.messages
        before = await collection.find_one({"_id": ObjectId(message.id)})

        with _frozen_now(UPDATED, BASE, MESSAGE_REPO):
            assert await repo.delete(message.id) is True

        after = await collection.find_one({"_id": ObjectId(message.id)})
        assert after == {
            **before,
            "status": MessageStatus.DELETED,
            "content": "此訊息已被刪除",
            "edited": True,
            "edited_at": _stored(UPDATED),
            "updated_at": _stored(UPDATED),
        }
