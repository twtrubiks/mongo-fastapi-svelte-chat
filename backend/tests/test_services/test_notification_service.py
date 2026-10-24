"""NotificationService 測試（真實 MongoDB）：即時推播內容、房間 / 全部已讀與統計事件"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.models.notification import (
    NotificationInDB,
    NotificationStatus,
    NotificationType,
)
from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import format_datetime_for_json

USER = str(ObjectId())
OTHER_USER = str(ObjectId())


class RecordingManager:
    """記錄送出的 WS 通知與事件的 connection_manager 替身"""

    def __init__(self):
        self.notifications = []
        self.events = []

    async def send_notification(self, user_id, notification):
        self.notifications.append((user_id, notification))

    async def send_event(self, user_id, event):
        self.events.append((user_id, event))


@pytest.fixture
def db(isolated_db_manager):
    return isolated_db_manager.database


@pytest.fixture
def manager():
    return RecordingManager()


@pytest.fixture
def service(db, manager):
    return NotificationService(NotificationRepository(db), connection_manager=manager)


async def _insert(db, **fields) -> str:
    defaults = {
        "user_id": USER,
        "title": "標題",
        "content": "內容",
        "type": NotificationType.MESSAGE,
    }
    document = NotificationInDB(**(defaults | fields)).model_dump(exclude={"id"})
    return str((await db.notifications.insert_one(document)).inserted_id)


async def _doc(db, notification_id: str) -> dict:
    return await db.notifications.find_one({"_id": ObjectId(notification_id)})


def _stats_event(total: int, unread: int, by_type: dict, message: str) -> tuple:
    return (
        USER,
        {
            "type": "notification_stats_update",
            "stats": {"total": total, "unread": unread, "by_type": by_type},
            "message": message,
        },
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestRealTimeNotification:
    async def test_create_pushes_stored_notification(self, service, manager, db):
        room_id, sender_id = str(ObjectId()), str(ObjectId())

        created = await service.create_notification(
            user_id=USER,
            title="來自 bob 的新訊息",
            content="在 大廳 中：嗨",
            notification_type=NotificationType.MESSAGE,
            metadata={"room_id": room_id},
            sender_id=sender_id,
            room_id=room_id,
        )

        stored = await _doc(db, created.id)
        assert stored["content"] == "在 大廳 中：嗨"
        assert manager.notifications == [
            (
                USER,
                {
                    "id": created.id,
                    "user_id": USER,
                    "type": "message",
                    "status": "unread",
                    "title": "來自 bob 的新訊息",
                    "message": "在 大廳 中：嗨",
                    "content": "在 大廳 中：嗨",
                    "data": {"room_id": room_id},
                    "metadata": {"room_id": room_id},
                    "room_id": room_id,
                    "sender_id": sender_id,
                    "created_at": format_datetime_for_json(stored["created_at"]),
                    "updated_at": format_datetime_for_json(stored["updated_at"]),
                },
            )
        ]

    async def test_notification_without_content_is_stored_but_not_pushed(
        self, service, manager, db
    ):
        created = await service.create_notification(
            user_id=USER,
            title="標題",
            content="",
            notification_type=NotificationType.SYSTEM,
        )

        assert await _doc(db, created.id) is not None
        assert manager.notifications == []


@pytest.mark.asyncio
@pytest.mark.integration
class TestMarkAllAsRead:
    async def test_marks_own_unread_and_sends_stats_once(self, service, manager, db):
        unread = await _insert(db)
        earlier = datetime(2026, 1, 1, tzinfo=UTC)
        already_read = await _insert(
            db,
            type=NotificationType.SYSTEM,
            status=NotificationStatus.READ,
            read_at=earlier,
        )
        others = await _insert(db, user_id=OTHER_USER)

        assert await service.mark_all_as_read(USER) == 1
        assert await service.mark_all_as_read(USER) == 0

        marked = await _doc(db, unread)
        assert marked["status"] == "read"
        assert marked["read_at"] is not None
        assert (await _doc(db, already_read))["read_at"] == earlier.replace(tzinfo=None)
        assert (await _doc(db, others))["status"] == "unread"
        assert manager.events == [
            _stats_event(2, 0, {"message": 1, "system": 1}, "已標記 1 則通知為已讀")
        ]


@pytest.mark.asyncio
@pytest.mark.integration
class TestMarkRoomAsRead:
    async def test_matches_top_level_or_metadata_room_id(self, service, db):
        room_id, other_room = str(ObjectId()), str(ObjectId())
        top_level = await _insert(db, room_id=room_id)
        metadata_only = await _insert(db, metadata={"room_id": room_id})
        other = await _insert(db, room_id=other_room, metadata={"room_id": other_room})

        assert await service.mark_room_notifications_as_read(USER, room_id) == 2

        for notification_id in (top_level, metadata_only):
            marked = await _doc(db, notification_id)
            assert marked["status"] == "read"
            assert marked["read_at"] is not None
        assert (await _doc(db, other))["status"] == "unread"

    async def test_sends_stats_only_when_something_changed(self, service, manager, db):
        room_id = str(ObjectId())
        await _insert(db, room_id=room_id)
        await _insert(db, room_id=str(ObjectId()))

        assert await service.mark_room_notifications_as_read(USER, room_id) == 1
        assert await service.mark_room_notifications_as_read(USER, room_id) == 0

        assert manager.events == [
            _stats_event(
                2, 1, {"message": 2}, f"已標記房間 {room_id} 的 1 則通知為已讀"
            )
        ]
