"""RoomService 房間事件廣播（真實 MongoDB）

加入 / 更新 / 離開房間後，看得到該房間的在線使用者都要收到 room_updated，
內容是不分收件者的房間摘要；離開時另廣播 user_left 並斷開離開者在該房的連線。
"""

from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.room import RoomCreate, RoomUpdate
from app.models.user import UserInDB
from app.repositories.message_repository import MessageRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.services.room_service import RoomService

SUMMARY_FIELDS = ("id", "name", "member_count", "is_member", "room_type")


class RoomEventRecorder:
    """記錄房間事件的 connection_manager 替身；online 為在線使用者"""

    def __init__(self, online: list[str]):
        self.active_connections = {user_id: {} for user_id in online}
        self.user_info: dict[str, dict] = {}
        self.events: list[tuple[str, dict]] = []
        self.room_broadcasts: list[tuple[str, dict]] = []
        self.disconnected: list[tuple[str, str]] = []
        self.notices: list[dict] = []

    async def send_event(self, user_id, event):
        self.events.append((user_id, event))

    async def broadcast_to_room(self, room_id, message, exclude_user=None):
        self.room_broadcasts.append((room_id, message))

    async def force_disconnect(self, user_id, room_id, reason="", notice=None):
        self.disconnected.append((user_id, room_id))
        self.notices.append(notice)


@pytest.fixture
async def users(isolated_db_manager):
    repo = UserRepository(isolated_db_manager.database)
    created = {}
    for name in ("owner", "member", "outsider"):
        user = await repo.create(
            UserInDB(
                username=name,
                email=f"{name}@example.com",
                hashed_password="not-a-login-password",
            )
        )
        created[name] = user.id
    return created


@pytest.fixture
def recorder(users):
    return RoomEventRecorder(list(users.values()))


@pytest.fixture
def service(isolated_db_manager, recorder):
    db = isolated_db_manager.database
    return RoomService(
        RoomRepository(db),
        UserRepository(db),
        MessageRepository(db),
        connection_manager=recorder,
    )


def _room_updates(recorder: RoomEventRecorder) -> list[tuple[str, dict]]:
    """取出 room_updated 事件的收件者與摘要欄位，並清空紀錄"""
    updates = []
    for user_id, event in recorder.events:
        assert set(event) == {"type", "room"}
        assert event["type"] == "room_updated"
        updates.append((user_id, {k: event["room"][k] for k in SUMMARY_FIELDS}))
    recorder.events.clear()
    return sorted(updates, key=lambda update: update[0])


@pytest.mark.asyncio
@pytest.mark.integration
class TestRoomUpdatedEvents:
    async def test_join_update_and_leave_broadcast_summary(
        self, service, recorder, users
    ):
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        recorder.events.clear()

        def expected(name: str, member_count: int) -> list[tuple[str, dict]]:
            summary = {
                "id": room.id,
                "name": name,
                "member_count": member_count,
                # 同一份摘要送給所有人，不能帶任何收件者的成員身分
                "is_member": False,
                "room_type": "public",
            }
            return sorted((user_id, summary) for user_id in users.values())

        await service.join_room(room.id, users["member"])
        assert _room_updates(recorder) == expected("lobby", 2)

        await service.update_room(room.id, users["owner"], RoomUpdate(name="hall"))
        assert _room_updates(recorder) == expected("hall", 2)

        await service.leave_room(room.id, users["member"])
        assert _room_updates(recorder) == expected("hall", 1)

    async def test_owner_removing_member_notifies_and_disconnects(
        self, service, recorder, users
    ):
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        await service.join_room(room.id, users["member"])
        recorder.events.clear()

        await service.remove_member(room.id, users["owner"], users["member"])

        [(room_id, event)] = recorder.room_broadcasts
        event.pop("timestamp")
        assert room_id == room.id
        # 被移出的成員不在線：名稱從資料庫補上
        assert event == {
            "type": "user_left",
            "user": {"id": users["member"], "username": "member"},
            "room_id": room.id,
            "removed": True,
            "kicked": True,
            "banned": False,
        }
        assert recorder.disconnected == [(users["member"], room.id)]
        # 被移出者在斷線前收到同一則 user_left（前端據此離開房間）
        assert recorder.notices == [event]
        updates = _room_updates(recorder)
        assert [user_id for user_id, _ in updates] == sorted(users.values())
        assert {summary["member_count"] for _, summary in updates} == {1}

    async def test_offline_member_leaving_is_identified_by_name(
        self, service, recorder, users
    ):
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        await service.join_room(room.id, users["member"])

        await service.leave_room(room.id, users["member"])

        [(room_id, event)] = recorder.room_broadcasts
        event.pop("timestamp")
        assert room_id == room.id
        assert event == {
            "type": "user_left",
            "user": {"id": users["member"], "username": "member"},
            "room_id": room.id,
            "removed": True,
            "kicked": False,
            "banned": False,
        }
        assert recorder.disconnected == [(users["member"], room.id)]
        assert recorder.notices == [event]

    # 不是成員就沒有可離開的：不能藉此在任何房間（含私人房）洗出「離開了聊天室」
    async def test_non_member_cannot_leave(self, service, recorder, users):
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        recorder.events.clear()

        with pytest.raises(NotFoundError):
            await service.leave_room(room.id, users["outsider"])

        assert recorder.room_broadcasts == []
        assert recorder.events == []
        assert recorder.disconnected == []

    async def test_member_already_gone_cannot_be_removed_twice(
        self, service, recorder, users
    ):
        """檢查完成員資格後對方剛好自己離開：移除改以原子條件判斷，不再廣播第二次"""
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        await service.join_room(room.id, users["member"])
        stale = await service.room_repo.get_by_id(room.id)
        await service.leave_room(room.id, users["member"])
        recorder.room_broadcasts.clear()
        service.room_repo.get_by_id = AsyncMock(return_value=stale)

        with pytest.raises(NotFoundError):
            await service.remove_member(room.id, users["owner"], users["member"])

        assert recorder.room_broadcasts == []

    async def test_banned_while_joining_is_told_about_ban(self, service, users):
        """檢查時還沒被封鎖、寫入前剛好被封鎖：原子條件擋下，並說明是被封鎖而非房間已滿"""
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        before_ban = await service.room_repo.get_by_id(room.id)
        await service.join_room(room.id, users["member"])
        await service.remove_member(room.id, users["owner"], users["member"], ban=True)
        latest = service.room_repo.get_by_id
        service.room_repo.get_by_id = AsyncMock(
            side_effect=[before_ban, await latest(room.id)]
        )

        with pytest.raises(ForbiddenError, match="你已被房主禁止加入此聊天室"):
            await service.join_room(room.id, users["member"])

    async def test_banning_member_tells_them_they_are_banned(
        self, service, recorder, users
    ):
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        await service.join_room(room.id, users["member"])
        recorder.room_broadcasts.clear()

        await service.ban_user(room.id, users["owner"], users["member"])

        [(_, event)] = recorder.room_broadcasts
        assert (event["type"], event["kicked"], event["banned"]) == (
            "user_left",
            True,
            True,
        )
        assert recorder.notices == [event]
        assert recorder.disconnected == [(users["member"], room.id)]

    async def test_banning_non_member_does_not_broadcast(
        self, service, recorder, users
    ):
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        recorder.events.clear()

        message = await service.ban_user(room.id, users["owner"], users["outsider"])

        assert message == "已封鎖"
        assert recorder.room_broadcasts == []
        assert recorder.disconnected == []
        assert recorder.events == []

    async def test_ban_follows_membership_at_write_time(self, service, recorder, users):
        """檢查時還不是成員、寫入前剛好加入：以寫入當下為準，一併移出並斷線"""
        room = await service.create_room(users["owner"], RoomCreate(name="lobby"))
        before_join = await service.room_repo.get_by_id(room.id)
        await service.join_room(room.id, users["member"])
        service.room_repo.get_by_id = AsyncMock(return_value=before_join)

        message = await service.ban_user(room.id, users["owner"], users["member"])

        assert message == "已將成員移出並封鎖"
        assert recorder.disconnected == [(users["member"], room.id)]
