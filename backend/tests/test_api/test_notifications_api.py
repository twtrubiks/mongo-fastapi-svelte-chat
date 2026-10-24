"""通知 HTTP API 測試（經由完整路由、依賴注入與 middleware）

涵蓋列表 / 未讀 / 統計的回應內容與分頁參數邊界、單筆與全部標記已讀、
刪除與清空，以及「只能操作自己的通知」。
"""

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from app.database.mongodb import get_database
from app.models.notification import (
    NotificationInDB,
    NotificationStatus,
    NotificationType,
)

FORM = {"Content-Type": "application/x-www-form-urlencoded"}
BASE = datetime(2026, 1, 1, tzinfo=UTC)


async def _make_user(client, name: str) -> dict:
    password = "password123"
    register = await client.post(
        "/api/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": password},
    )
    assert register.status_code == 201
    login = await client.post(
        "/api/auth/login",
        data={"username": name, "password": password},
        headers=FORM,
    )
    assert login.status_code == 200
    return {
        "id": register.json()["user"]["id"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


@pytest.fixture
async def users(async_client, isolated_db_manager):
    return {name: await _make_user(async_client, name) for name in ("alice", "bob")}


async def _notify(user: dict, minute: int, **fields) -> str:
    """直接寫入一筆通知並回傳 id；created_at 依 minute 遞增，數字越大越新"""
    at = BASE + timedelta(minutes=minute)
    defaults = {
        "user_id": user["id"],
        "title": f"通知 {minute}",
        "content": f"內容 {minute}",
        "type": NotificationType.MESSAGE,
        "created_at": at,
        "updated_at": at,
    }
    document = NotificationInDB(**(defaults | fields)).model_dump(exclude={"id"})
    db = await get_database()
    return str((await db.notifications.insert_one(document)).inserted_id)


async def _notify_many(user: dict, count: int, **fields) -> list[str]:
    return [await _notify(user, minute, **fields) for minute in range(count)]


async def _list(client, user: dict, path: str = "/api/notifications/", **params):
    response = await client.get(path, params=params, headers=user["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def _titles(body: dict) -> list[str]:
    return [n["title"] for n in body["notifications"]]


@pytest.mark.asyncio
@pytest.mark.integration
class TestListNotifications:
    async def test_lists_own_notifications_newest_first(self, async_client, users):
        alice, bob = users["alice"], users["bob"]
        room_id, sender_id = str(ObjectId()), str(ObjectId())
        newest = await _notify(
            alice,
            2,
            metadata={"room_id": room_id, "sender_name": "bob"},
            room_id=room_id,
            sender_id=sender_id,
        )
        await _notify(alice, 1, status=NotificationStatus.READ)
        await _notify(alice, 0, type=NotificationType.SYSTEM)
        await _notify(bob, 3)

        body = await _list(async_client, alice)

        assert _titles(body) == ["通知 2", "通知 1", "通知 0"]
        assert body["unread_count"] == 2
        assert body["notifications"][0] == {
            "id": newest,
            "user_id": alice["id"],
            "title": "通知 2",
            "content": "內容 2",
            "type": "message",
            "status": "unread",
            "metadata": {"room_id": room_id, "sender_name": "bob"},
            "sender_id": sender_id,
            "room_id": room_id,
            "read_at": None,
            "created_at": "2026-01-01T00:02:00Z",
            "updated_at": "2026-01-01T00:02:00Z",
        }

    async def test_default_page_is_newest_twenty(self, async_client, users):
        await _notify_many(users["alice"], 21)

        first_page = await _list(async_client, users["alice"])
        rest = await _list(async_client, users["alice"], skip=20)

        assert _titles(first_page) == [f"通知 {i}" for i in range(20, 0, -1)]
        assert _titles(rest) == ["通知 0"]

    async def test_filters_by_status_and_type(self, async_client, users):
        alice = users["alice"]
        await _notify(alice, 0)
        await _notify(alice, 1, status=NotificationStatus.READ)
        await _notify(alice, 2, type=NotificationType.SYSTEM)

        read = await _list(async_client, alice, status="read")
        system = await _list(async_client, alice, type="system")

        assert _titles(read) == ["通知 1"]
        assert _titles(system) == ["通知 2"]

    @pytest.mark.parametrize(
        ("params", "status_code"),
        [
            ({"limit": 1}, 200),
            ({"limit": 100}, 200),
            ({"limit": 0}, 422),
            ({"limit": 101}, 422),
            ({"skip": 0}, 200),
            ({"skip": -1}, 422),
        ],
    )
    async def test_paging_bounds(self, async_client, users, params, status_code):
        response = await async_client.get(
            "/api/notifications/", params=params, headers=users["alice"]["headers"]
        )
        assert response.status_code == status_code

    async def test_requires_login(self, async_client, isolated_db_manager):
        response = await async_client.get("/api/notifications/")
        assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
class TestUnreadNotifications:
    async def test_default_returns_newest_fifty_unread(self, async_client, users):
        alice = users["alice"]
        await _notify_many(alice, 51)
        await _notify(alice, 99, status=NotificationStatus.READ)

        body = await _list(async_client, alice, "/api/notifications/unread")

        assert _titles(body) == [f"通知 {i}" for i in range(50, 0, -1)]
        assert body["unread_count"] == 51

    @pytest.mark.parametrize(
        ("limit", "status_code"), [(1, 200), (100, 200), (0, 422), (101, 422)]
    )
    async def test_limit_bounds(self, async_client, users, limit, status_code):
        response = await async_client.get(
            "/api/notifications/unread",
            params={"limit": limit},
            headers=users["alice"]["headers"],
        )
        assert response.status_code == status_code


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationStats:
    async def test_counts_by_status_and_type(self, async_client, users):
        alice = users["alice"]
        await _notify(alice, 0)
        await _notify(alice, 1, status=NotificationStatus.READ)
        await _notify(alice, 2, type=NotificationType.SYSTEM)
        await _notify(alice, 3)
        await _notify(users["bob"], 4)

        stats = await _list(async_client, alice, "/api/notifications/stats")

        recent = stats.pop("recent_activity")
        assert stats == {
            "total_count": 4,
            "unread_count": 3,
            "read_count": 1,
            "type_counts": {"message": 3, "system": 1},
        }
        # 時間與其他 API 同格式（UTC 以 Z 結尾）
        assert recent == [
            {
                "type": "message",
                "title": "通知 3",
                "created_at": "2026-01-01T00:03:00Z",
            },
            {"type": "system", "title": "通知 2", "created_at": "2026-01-01T00:02:00Z"},
            {
                "type": "message",
                "title": "通知 1",
                "created_at": "2026-01-01T00:01:00Z",
            },
            {
                "type": "message",
                "title": "通知 0",
                "created_at": "2026-01-01T00:00:00Z",
            },
        ]

    async def test_empty(self, async_client, users):
        stats = await _list(async_client, users["alice"], "/api/notifications/stats")

        assert stats == {
            "total_count": 0,
            "unread_count": 0,
            "read_count": 0,
            "type_counts": {},
            "recent_activity": [],
        }


@pytest.mark.asyncio
@pytest.mark.integration
class TestMarkRead:
    async def test_marks_one_and_keeps_metadata(self, async_client, users):
        alice = users["alice"]
        target = await _notify(alice, 1, metadata={"room_id": "r1"})
        await _notify(alice, 0)
        before = datetime.now(UTC)

        response = await async_client.post(
            f"/api/notifications/{target}/read", headers=alice["headers"]
        )

        after = datetime.now(UTC)
        assert response.status_code == 200
        assert response.json() == {"message": "通知已標記為已讀"}
        body = await _list(async_client, alice)
        marked, other = body["notifications"]
        assert (marked["id"], marked["status"]) == (target, "read")
        assert marked["metadata"] == {"room_id": "r1"}
        read_at = datetime.fromisoformat(marked["read_at"])
        assert before - timedelta(milliseconds=1) <= read_at <= after
        assert (other["status"], other["read_at"]) == ("unread", None)
        assert body["unread_count"] == 1

    @pytest.mark.parametrize(
        "notification_id",
        ["5f0000000000000000000000", "not-an-id"],
        ids=["nonexistent", "malformed"],
    )
    async def test_missing_notification_is_404(
        self, async_client, users, notification_id
    ):
        response = await async_client.post(
            f"/api/notifications/{notification_id}/read",
            headers=users["alice"]["headers"],
        )
        assert response.status_code == 404

    async def test_cannot_mark_others_notification(self, async_client, users):
        target = await _notify(users["alice"], 0)

        response = await async_client.post(
            f"/api/notifications/{target}/read", headers=users["bob"]["headers"]
        )

        assert response.status_code == 403
        assert (await _list(async_client, users["alice"]))["unread_count"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
class TestMarkAllRead:
    async def test_marks_only_own_unread(self, async_client, users):
        alice, bob = users["alice"], users["bob"]
        earlier = datetime(2026, 1, 1, 12, tzinfo=UTC)
        await _notify(alice, 2)
        await _notify(alice, 1)
        await _notify(alice, 0, status=NotificationStatus.READ, read_at=earlier)
        await _notify(bob, 3)

        first = await async_client.post(
            "/api/notifications/read-all", headers=alice["headers"]
        )
        again = await async_client.post(
            "/api/notifications/read-all", headers=alice["headers"]
        )

        assert first.status_code == again.status_code == 200
        assert first.json() == {"message": "已標記 2 個通知為已讀", "count": 2}
        assert again.json() == {"message": "已標記 0 個通知為已讀", "count": 0}
        body = await _list(async_client, alice)
        assert body["unread_count"] == 0
        newly_read, _, already_read = body["notifications"]
        assert newly_read["status"] == "read"
        assert newly_read["read_at"] is not None
        assert already_read["read_at"] == "2026-01-01T12:00:00Z"
        assert (await _list(async_client, bob))["unread_count"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
class TestDeleteNotifications:
    async def test_delete_own(self, async_client, users):
        alice = users["alice"]
        target = await _notify(alice, 1)
        await _notify(alice, 0)

        response = await async_client.delete(
            f"/api/notifications/{target}", headers=alice["headers"]
        )
        again = await async_client.delete(
            f"/api/notifications/{target}", headers=alice["headers"]
        )

        assert response.status_code == 200
        assert response.json() == {"message": "通知已刪除"}
        assert again.status_code == 404
        assert _titles(await _list(async_client, alice)) == ["通知 0"]

    async def test_cannot_delete_others_notification(self, async_client, users):
        target = await _notify(users["alice"], 0)

        response = await async_client.delete(
            f"/api/notifications/{target}", headers=users["bob"]["headers"]
        )

        assert response.status_code == 403
        assert _titles(await _list(async_client, users["alice"])) == ["通知 0"]

    async def test_clear_all_only_own(self, async_client, users):
        alice, bob = users["alice"], users["bob"]
        await _notify_many(alice, 3)
        await _notify(bob, 0)

        response = await async_client.delete(
            "/api/notifications/", headers=alice["headers"]
        )
        again = await async_client.delete(
            "/api/notifications/", headers=alice["headers"]
        )

        assert response.status_code == 200
        assert response.json() == {"message": "已清空 3 個通知", "count": 3}
        assert again.json() == {"message": "已清空 0 個通知", "count": 0}
        assert _titles(await _list(async_client, alice)) == []
        assert _titles(await _list(async_client, bob)) == ["通知 0"]
