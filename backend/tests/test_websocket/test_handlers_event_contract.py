"""WebSocket handler 對外事件契約（真實 MongoDB / Redis）

以替身 connection_manager 收集 handler 送出的每個事件，再對整個 payload 精確比對：
WS 事件結構是前後端契約（見前端 types.ts 的 WebSocketMessage），欄位改名、缺漏、
預設值與各種數量邊界都由這裡鎖住。
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId
from fastapi import WebSocketDisconnect
from starlette.datastructures import Headers, QueryParams

from app.config import settings
from app.core.bot import BOT_USERNAME
from app.core.exceptions import AppError
from app.core.fastapi_integration import create_notification_service
from app.database.mongodb import get_database
from app.database.redis_conn import get_redis
from app.models.message import MessageInDB
from app.models.notification import NotificationType
from app.models.user import UserInDB
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService
from app.utils.datetime_utils import format_datetime_for_json
from app.utils.json_encoder import safe_json_dumps
from app.utils.ws_ticket import create_ws_ticket
from app.websocket.handlers import (
    _background_ai_tasks,
    _spawn_ai_task,
    handle_bot_mention,
    handle_message,
    handle_summary_command,
    handle_websocket_connection,
)

FORM = {"Content-Type": "application/x-www-form-urlencoded"}
ROOM_NAME = "contract room"
AVATAR = "/api/files/image/sender.png"


class _IsoNow:
    """比對 handler 剛產生的時間戳：帶時區的 ISO 8601 字串、且接近現在"""

    def __eq__(self, other):
        if not isinstance(other, str):
            return False
        try:
            parsed = datetime.fromisoformat(other)
        except ValueError:
            return False
        return parsed.tzinfo is not None and abs(
            datetime.now(UTC) - parsed
        ) < timedelta(seconds=30)

    def __repr__(self):
        return "<ISO timestamp near now>"


NOW = _IsoNow()


def _wire(message: dict) -> dict:
    """與 ConnectionManager 相同的序列化：記錄客戶端實際收到的 JSON"""
    return json.loads(safe_json_dumps(message))


class WsRecorder:
    """替身 connection_manager：依序記錄 handler 送出的每個事件（以線上 JSON 形式）"""

    def __init__(self):
        self.sent: list[tuple] = []
        self.room_users: list[dict] = []
        self.online_ids: list[str] = []

    async def connect(self, websocket, user_id, room_id, user_info):
        self.sent.append(("connect", user_id, room_id))

    async def disconnect(self, user_id, room_id, websocket=None):
        self.sent.append(("disconnect", user_id, room_id))

    async def send_personal_message(self, user_id, room_id, message):
        self.sent.append(("personal", user_id, room_id, _wire(message)))

    async def broadcast_to_room(self, room_id, message, exclude_user=None):
        self.sent.append(("room", room_id, _wire(message), exclude_user))

    async def broadcast_message(self, room_id, message, sender_id):
        self.sent.append(("message", room_id, _wire(message), sender_id))

    async def send_event(self, user_id, event_data):
        self.sent.append(("event", user_id, _wire(event_data)))

    def get_room_users(self, room_id):
        return self.room_users

    def get_global_online_user_ids(self):
        return self.online_ids

    async def handle_ping(self, user_id, room_id):
        self.sent.append(("ping", user_id, room_id))


class FakeAI:
    """替身 AI service：記錄呼叫並回傳預設的串流片段／摘要（不打外部 API）"""

    def __init__(self, deltas=(), summary="", error: Exception | None = None):
        self.deltas = deltas
        self.summary = summary
        self.error = error
        self.stream_calls: list[tuple] = []
        self.summarize_calls: list[str] = []

    async def stream_reply(self, question, history=None):
        self.stream_calls.append((question, history))
        if self.error:
            raise self.error
        for delta in self.deltas:
            yield delta

    async def summarize(self, transcript):
        self.summarize_calls.append(transcript)
        return self.summary


def _patch_ai(fake: FakeAI):
    return patch(
        "app.websocket.handlers.create_ai_service", AsyncMock(return_value=fake)
    )


async def _make_user(client, name: str) -> dict:
    password = "password123"
    register = await client.post(
        "/api/auth/register",
        json={"username": name, "email": f"{name}@example.com", "password": password},
    )
    assert register.status_code == 201
    login = await client.post(
        "/api/auth/login", data={"username": name, "password": password}, headers=FORM
    )
    assert login.status_code == 200
    user_id = register.json()["user"]["id"]
    return {
        "id": user_id,
        "username": name,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        "info": {"id": user_id, "username": name, "avatar": None},
    }


@pytest.fixture
def recorder():
    rec = WsRecorder()
    with patch("app.websocket.handlers.connection_manager", rec):
        yield rec


@pytest.fixture
async def ctx(async_client, isolated_db_manager):
    """sender 建立公開房並設定頭像，alice 加入；另種子化一個 bot 使用者"""
    sender = await _make_user(async_client, "sender")
    alice = await _make_user(async_client, "alice")
    profile = await async_client.put(
        "/api/auth/profile", json={"avatar": AVATAR}, headers=sender["headers"]
    )
    assert profile.status_code == 200
    sender["info"]["avatar"] = AVATAR

    room = await async_client.post(
        "/api/rooms/", json={"name": ROOM_NAME}, headers=sender["headers"]
    )
    assert room.status_code == 201
    room_id = room.json()["id"]
    joined = await async_client.post(
        f"/api/rooms/{room_id}/join", headers=alice["headers"]
    )
    assert joined.status_code == 200

    db = await get_database()
    bot = await UserRepository(db).create(
        UserInDB(
            username=BOT_USERNAME,
            email="bot@chatroom.app",
            full_name="聊天室 AI 助理",
            hashed_password="not-a-login-password",
        )
    )
    with patch("app.websocket.handlers.get_bot_user_id", return_value=bot.id):
        yield SimpleNamespace(
            client=async_client,
            db=db,
            sender=sender,
            alice=alice,
            bot_id=bot.id,
            room_id=room_id,
        )


async def _insert_messages(db, room_id: str, rows: list[tuple[str, str, str]]):
    """依序插入 (user_id, username, content)，created_at 每則間隔 1 秒（最舊→最新）"""
    base = datetime.now(UTC).replace(microsecond=0) - timedelta(seconds=len(rows))
    docs = [
        MessageInDB(
            room_id=room_id,
            user_id=user_id,
            username=username,
            content=content,
            seq=index + 1,
            created_at=base + timedelta(seconds=index),
            updated_at=base + timedelta(seconds=index),
        ).model_dump(exclude={"id"})
        for index, (user_id, username, content) in enumerate(rows)
    ]
    result = await db.messages.insert_many(docs)
    return [str(inserted) for inserted in result.inserted_ids]


def _message_payload(doc: dict, avatar: str | None) -> dict:
    """前端 Message 型別：top-level 欄位 + 巢狀 user"""
    return {
        "id": str(doc["_id"]),
        "room_id": doc["room_id"],
        "user_id": doc["user_id"],
        "username": doc["username"],
        "content": doc["content"],
        "message_type": doc["message_type"],
        "status": doc["status"],
        "seq": doc["seq"],
        "client_id": doc["client_id"],
        "created_at": format_datetime_for_json(doc["created_at"]),
        "metadata": doc["metadata"],
        "user": {"id": doc["user_id"], "username": doc["username"], "avatar": avatar},
    }


def _fake_ws(query: dict) -> Mock:
    websocket = Mock()
    websocket.query_params = QueryParams(query)
    websocket.headers = Headers({})
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
    return websocket


@pytest.mark.asyncio
@pytest.mark.integration
class TestConnectionEvents:
    async def test_connect_sends_welcome_then_latest_50_messages(self, ctx, recorder):
        sender = ctx.sender
        await _insert_messages(
            ctx.db,
            ctx.room_id,
            [(sender["id"], "sender", f"歷史 {i:02d}") for i in range(51)],
        )
        ticket = await create_ws_ticket(sender["id"], ctx.room_id)

        await handle_websocket_connection(_fake_ws({"ticket": ticket}), ctx.room_id)

        docs = await ctx.db.messages.find({"room_id": ctx.room_id}).to_list()
        docs.sort(key=lambda doc: doc["created_at"])
        assert recorder.sent == [
            ("connect", sender["id"], ctx.room_id),
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "welcome",
                    "message": "歡迎 sender 加入聊天室！",
                    "timestamp": NOW,
                    "room_id": ctx.room_id,
                },
            ),
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "message_history",
                    # 只送最新 50 則（最舊的一則不送），最舊→最新
                    "messages": [_message_payload(doc, AVATAR) for doc in docs[1:]],
                    "timestamp": NOW,
                    "room_id": ctx.room_id,
                },
            ),
            ("disconnect", sender["id"], ctx.room_id),
        ]

    async def test_history_load_failure_reported_and_connection_kept(
        self, ctx, recorder
    ):
        sender = ctx.sender
        # 損壞的訊息文件（缺 user_id / username）讓歷史載入失敗
        await ctx.db.messages.insert_one(
            {
                "room_id": ctx.room_id,
                "content": "壞資料",
                "created_at": datetime.now(UTC),
            }
        )
        ticket = await create_ws_ticket(sender["id"], ctx.room_id)
        websocket = _fake_ws({"ticket": ticket})
        websocket.receive_text.side_effect = ['{"type": "ping"}', WebSocketDisconnect()]

        await handle_websocket_connection(websocket, ctx.room_id)

        assert recorder.sent[2:] == [
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {"type": "error", "message": "無法載入歷史訊息", "timestamp": NOW},
            ),
            ("ping", sender["id"], ctx.room_id),
            ("disconnect", sender["id"], ctx.room_id),
        ]


@pytest.mark.asyncio
@pytest.mark.integration
class TestChatMessageEvents:
    async def test_ack_then_broadcast(self, ctx, recorder):
        sender = ctx.sender

        await handle_message(
            sender["id"],
            ctx.room_id,
            {"type": "chat_message", "content": "  哈囉  ", "client_id": "c-1"},
            sender["info"],
        )

        doc = await ctx.db.messages.find_one({"room_id": ctx.room_id})
        message_id = str(doc["_id"])
        assert recorder.sent == [
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "ack",
                    "client_id": "c-1",
                    "message_id": message_id,
                    "seq": doc["seq"],
                    "room_id": ctx.room_id,
                    "timestamp": NOW,
                },
            ),
            (
                "message",
                ctx.room_id,
                {
                    "id": message_id,
                    "room_id": ctx.room_id,
                    "user_id": sender["id"],
                    "username": "sender",
                    "content": "哈囉",
                    "message_type": "text",
                    "status": "sent",
                    "seq": doc["seq"],
                    "client_id": "c-1",
                    "created_at": format_datetime_for_json(doc["created_at"]),
                    "metadata": None,
                    "user": {
                        "id": sender["id"],
                        "username": "sender",
                        "avatar": AVATAR,
                    },
                    "temp_id": "c-1",
                },
                None,
            ),
        ]

    @pytest.mark.parametrize(
        ("message_type", "stored_type"), [("image", "image"), ("FILE", "file")]
    )
    async def test_file_message_keeps_type_and_metadata(
        self, ctx, recorder, message_type, stored_type
    ):
        sender = ctx.sender
        metadata = {"filename": "cat.png", "file_size": 2048, "mime_type": "image/png"}

        await handle_message(
            sender["id"],
            ctx.room_id,
            {
                "type": "chat_message",
                "content": "/api/files/cat.png",
                "message_type": message_type,
                "metadata": metadata,
                "client_id": "c-file",
            },
            sender["info"],
        )

        doc = await ctx.db.messages.find_one({"room_id": ctx.room_id})
        assert (doc["message_type"], doc["metadata"]) == (stored_type, metadata)
        kind, _, broadcast, _ = recorder.sent[1]
        assert kind == "message"
        assert (broadcast["message_type"], broadcast["metadata"]) == (
            stored_type,
            metadata,
        )

    async def test_missing_content_rejected_without_persisting(self, ctx, recorder):
        sender = ctx.sender

        await handle_message(
            sender["id"],
            ctx.room_id,
            {"type": "chat_message", "client_id": "c-2"},
            sender["info"],
        )

        assert recorder.sent == [
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "error",
                    "message": "訊息內容不能為空",
                    "timestamp": NOW,
                    "temp_id": "c-2",
                },
            )
        ]
        assert await ctx.db.messages.count_documents({}) == 0

    async def test_system_message_type_rejected(self, ctx, recorder):
        """使用者不可經 WS 建立 system 訊息（前端會顯示為系統公告）"""
        sender = ctx.sender

        await handle_message(
            sender["id"],
            ctx.room_id,
            {
                "type": "chat_message",
                "content": "系統公告：請重新登入",
                "message_type": "system",
                "client_id": "c-sys",
            },
            sender["info"],
        )

        assert recorder.sent == [
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "error",
                    "message": "訊息發送失敗",
                    "timestamp": NOW,
                    "temp_id": "c-sys",
                },
            )
        ]
        assert await ctx.db.messages.count_documents({}) == 0

    async def test_non_member_gets_send_failure(self, ctx, recorder):
        outsider = await _make_user(ctx.client, "outsider")

        await handle_message(
            outsider["id"],
            ctx.room_id,
            {"type": "chat_message", "content": "我不是成員", "client_id": "c-3"},
            outsider["info"],
        )

        assert recorder.sent == [
            (
                "personal",
                outsider["id"],
                ctx.room_id,
                {
                    "type": "error",
                    "message": "訊息發送失敗",
                    "timestamp": NOW,
                    "temp_id": "c-3",
                },
            )
        ]
        assert await ctx.db.messages.count_documents({}) == 0

    @pytest.mark.parametrize(
        "length,expected_preview",
        [
            (50, "0123456789" * 5),
            (51, "0123456789" * 5 + "..."),
        ],
    )
    async def test_notification_preview_truncated_after_50_chars(
        self, ctx, recorder, length, expected_preview
    ):
        content = ("0123456789" * 6)[:length]

        await handle_message(
            ctx.sender["id"],
            ctx.room_id,
            {"type": "chat_message", "content": content},
            ctx.sender["info"],
        )

        notifications = await ctx.db.notifications.find(
            {"user_id": ctx.alice["id"]}
        ).to_list()
        assert len(notifications) == 1
        assert notifications[0]["metadata"]["message_preview"] == expected_preview
        assert notifications[0]["content"] == f"在 {ROOM_NAME} 中：{expected_preview}"
        assert (
            await ctx.db.notifications.count_documents({"user_id": ctx.sender["id"]})
            == 0
        )

    async def test_notification_failure_is_per_member_and_counted(
        self, ctx, recorder, caplog
    ):
        bob = await _make_user(ctx.client, "bob")
        joined = await ctx.client.post(
            f"/api/rooms/{ctx.room_id}/join", headers=bob["headers"]
        )
        assert joined.status_code == 200
        original = NotificationService.send_message_notification

        async def fail_for_bob(self, **kwargs):
            if kwargs["user_id"] == bob["id"]:
                raise RuntimeError("通知寫入失敗")
            return await original(self, **kwargs)

        with (
            patch.object(
                NotificationService, "send_message_notification", fail_for_bob
            ),
            caplog.at_level(logging.INFO, logger="app.websocket.handlers"),
        ):
            await handle_message(
                ctx.sender["id"],
                ctx.room_id,
                {"type": "chat_message", "content": "大家好"},
                ctx.sender["info"],
            )

        assert (
            await ctx.db.notifications.count_documents({"user_id": ctx.alice["id"]})
            == 1
        )
        assert await ctx.db.notifications.count_documents({"user_id": bob["id"]}) == 0
        # 發送者自己與失敗的 bob 都不計入
        assert "Notifications sent to 1 members" in caplog.messages


@pytest.mark.asyncio
@pytest.mark.integration
class TestBotEvents:
    async def test_streams_then_lands_reply_with_quote(self, ctx, recorder):
        [question_id] = await _insert_messages(
            ctx.db, ctx.room_id, [(ctx.sender["id"], "sender", "@bot 問題")]
        )
        fake = FakeAI(deltas=["你", "", "好"])
        bot_user = {"id": ctx.bot_id, "username": BOT_USERNAME, "avatar": None}

        with _patch_ai(fake):
            await handle_bot_mention(ctx.sender["id"], ctx.room_id, "問題", question_id)

        doc = await ctx.db.messages.find_one({"user_id": ctx.bot_id})
        assert recorder.sent == [
            (
                "room",
                ctx.room_id,
                {
                    "type": "bot_typing",
                    "room_id": ctx.room_id,
                    "user": bot_user,
                    "content": delta,
                    "timestamp": NOW,
                },
                None,
            )
            for delta in ("你", "好")
        ] + [
            (
                "message",
                ctx.room_id,
                {
                    "id": str(doc["_id"]),
                    "room_id": ctx.room_id,
                    "user_id": ctx.bot_id,
                    "username": BOT_USERNAME,
                    "content": "你好",
                    "message_type": "text",
                    "status": "sent",
                    "seq": doc["seq"],
                    "client_id": None,
                    "created_at": format_datetime_for_json(doc["created_at"]),
                    "metadata": None,
                    "user": bot_user,
                    "reply_to": question_id,
                    "reply_to_message": {
                        "id": question_id,
                        "content": "@bot 問題",
                        "username": "sender",
                    },
                },
                None,
            )
        ]

    async def test_provider_error_broadcasts_bot_error(self, ctx, recorder):
        fake = FakeAI(error=AppError("AI 助理尚未配置（nvidia 缺少 API key）"))

        with _patch_ai(fake):
            await handle_bot_mention(ctx.sender["id"], ctx.room_id, "問題", "trigger")

        assert recorder.sent == [
            (
                "room",
                ctx.room_id,
                {
                    "type": "bot_error",
                    "room_id": ctx.room_id,
                    "message": "AI 助理尚未配置（nvidia 缺少 API key）",
                    "timestamp": NOW,
                },
                None,
            )
        ]

    async def test_empty_question_hint_sent_only_to_trigger_user(self, ctx, recorder):
        with _patch_ai(FakeAI()):
            await handle_bot_mention(ctx.sender["id"], ctx.room_id, "", "trigger")

        assert recorder.sent == [
            (
                "personal",
                ctx.sender["id"],
                ctx.room_id,
                {
                    "type": "error",
                    "message": "請在 @bot 後面輸入你的問題",
                    "timestamp": NOW,
                },
            )
        ]

    @pytest.mark.parametrize(
        "chitchat,expected_history",
        [
            # 共 50 則（含當前提問）：舊的往返仍在視窗內
            (47, "sender: 舊問題\nAI 助理: 舊回答"),
            # 共 51 則：舊提問被擠出最新 50 則，只剩無提問的回答 → 不成對
            (48, ""),
        ],
    )
    async def test_history_built_from_latest_50_messages(
        self, ctx, recorder, chitchat, expected_history
    ):
        sender, alice = ctx.sender, ctx.alice
        ids = await _insert_messages(
            ctx.db,
            ctx.room_id,
            [
                (sender["id"], "sender", "@bot 舊問題"),
                (ctx.bot_id, BOT_USERNAME, "舊回答"),
            ]
            + [(alice["id"], "alice", f"閒聊 {i}") for i in range(chitchat)]
            + [(sender["id"], "sender", "@bot 新問題")],
        )
        fake = FakeAI(deltas=["好"])

        with _patch_ai(fake):
            await handle_bot_mention(sender["id"], ctx.room_id, "新問題", ids[-1])

        assert fake.stream_calls == [("新問題", expected_history)]

    async def test_summary_uses_latest_30_messages(self, ctx, recorder):
        await _insert_messages(
            ctx.db,
            ctx.room_id,
            [(ctx.sender["id"], "sender", f"第 {i} 則") for i in range(31)],
        )
        fake = FakeAI(summary="重點")

        with _patch_ai(fake):
            await handle_summary_command(ctx.sender["id"], ctx.room_id)

        assert fake.summarize_calls == [
            "\n".join(f"sender: 第 {i} 則" for i in range(1, 31))
        ]
        assert [event[0] for event in recorder.sent] == ["message"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestBotRateLimitWindow:
    async def test_quota_frees_up_exactly_60_seconds_later(self, recorder):
        user_id, room_id = str(ObjectId()), str(ObjectId())
        quota = settings.BOT_RATE_LIMIT_PER_MINUTE
        clock = Mock()
        start = 1_700_000_000

        async def ask_at(offset: int):
            clock.time.return_value = start + offset
            # 空問題：通過限流後立刻回提示，不打 AI，但仍消耗一次額度
            await handle_bot_mention(user_id, room_id, "", "trigger")

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot"),
            patch("app.middleware.rate_limiting.time", clock),
        ):
            for _ in range(quota):
                await ask_at(0)
            await ask_at(59)
            await ask_at(60)
        await (await get_redis()).delete(f"rate_limit:bot:{user_id}")

        outcomes = [
            "limited" if "太頻繁" in event[3]["message"] else "allowed"
            for event in recorder.sent
        ]
        assert outcomes == ["allowed"] * quota + ["limited", "allowed"]


@pytest.mark.asyncio
@pytest.mark.unit
class TestSimpleEvents:
    async def test_typing_without_flag_means_not_typing(self, recorder):
        info = {"id": "u1", "username": "sender", "avatar": None}

        await handle_message("u1", "room1", {"type": "typing"}, info)

        assert recorder.sent == [
            (
                "room",
                "room1",
                {
                    "type": "typing",
                    "user": info,
                    "is_typing": False,
                    "timestamp": NOW,
                    "room_id": "room1",
                },
                "u1",
            )
        ]

    async def test_get_users(self, recorder):
        recorder.room_users = [{"id": "u1", "username": "sender"}]
        recorder.online_ids = ["u1", "u9"]

        await handle_message("u1", "room1", {"type": "get_users"}, {"id": "u1"})

        assert recorder.sent == [
            (
                "personal",
                "u1",
                "room1",
                {
                    "type": "room_users",
                    "users": [{"id": "u1", "username": "sender"}],
                    "global_online_user_ids": ["u1", "u9"],
                    "timestamp": NOW,
                    "room_id": "room1",
                },
            )
        ]

    async def test_unknown_type(self, recorder):
        await handle_message("u1", "room1", {"type": "shout"}, {"id": "u1"})

        assert recorder.sent == [
            (
                "personal",
                "u1",
                "room1",
                {
                    "type": "error",
                    "message": "Unknown message type: shout",
                    "timestamp": NOW,
                },
            )
        ]


async def _notify(user_id: str, room_id: str) -> str:
    service = await create_notification_service()
    created = await service.create_notification(
        user_id=user_id,
        title="新訊息",
        content="內容",
        notification_type=NotificationType.MESSAGE,
        room_id=room_id,
    )
    return created.id


async def _status(db, notification_id: str) -> str:
    doc = await db.notifications.find_one({"_id": ObjectId(notification_id)})
    return doc["status"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestNotificationReadEvents:
    async def test_single_notification_is_the_default_read_type(self, ctx, recorder):
        sender = ctx.sender
        notification_id = await _notify(sender["id"], ctx.room_id)

        await handle_message(
            sender["id"],
            ctx.room_id,
            {"type": "notification_read", "notification_id": notification_id},
            sender["info"],
        )

        assert await _status(ctx.db, notification_id) == "read"
        assert recorder.sent == [
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "read_status_response",
                    "success": True,
                    "data": {
                        "read_type": "notification",
                        "notification_id": notification_id,
                        "target_room_id": ctx.room_id,
                        "timestamp": NOW,
                    },
                },
            ),
            (
                "event",
                sender["id"],
                {
                    "type": "notification_status_changed",
                    "data": {
                        "read_type": "notification",
                        "id": notification_id,
                        "status": "read",
                        "timestamp": NOW,
                    },
                },
            ),
        ]

    async def test_cannot_mark_someone_elses_notification(self, ctx, recorder):
        sender = ctx.sender
        alice_notification = await _notify(ctx.alice["id"], ctx.room_id)

        await handle_message(
            sender["id"],
            ctx.room_id,
            {"type": "notification_read", "notification_id": alice_notification},
            sender["info"],
        )

        assert await _status(ctx.db, alice_notification) == "unread"
        assert recorder.sent == [
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "read_status_response",
                    "success": False,
                    "data": {
                        "read_type": "notification",
                        "notification_id": alice_notification,
                        "target_room_id": ctx.room_id,
                        "timestamp": NOW,
                    },
                },
            )
        ]

    async def test_room_read_marks_whole_room_even_with_notification_id(
        self, ctx, recorder
    ):
        sender = ctx.sender
        first = await _notify(sender["id"], ctx.room_id)
        second = await _notify(sender["id"], ctx.room_id)
        elsewhere = await _notify(sender["id"], str(ObjectId()))

        await handle_message(
            sender["id"],
            ctx.room_id,
            {
                "type": "notification_read",
                "read_type": "room",
                "notification_id": first,
            },
            sender["info"],
        )

        assert [await _status(ctx.db, n) for n in (first, second, elsewhere)] == [
            "read",
            "read",
            "unread",
        ]
        assert recorder.sent[0][3]["success"] is True

    @pytest.mark.parametrize("event_type", ["notification_read", "mark_read"])
    async def test_room_read_with_nothing_unread_still_succeeds(
        self, ctx, recorder, event_type
    ):
        sender = ctx.sender

        await handle_message(
            sender["id"],
            ctx.room_id,
            {"type": event_type, "read_type": "room"},
            sender["info"],
        )

        assert recorder.sent == [
            (
                "personal",
                sender["id"],
                ctx.room_id,
                {
                    "type": "read_status_response",
                    "success": True,
                    "data": {
                        "read_type": "room",
                        "notification_id": None,
                        "target_room_id": ctx.room_id,
                        "timestamp": NOW,
                    },
                },
            ),
            (
                "event",
                sender["id"],
                {
                    "type": "notification_status_changed",
                    "data": {
                        "read_type": "room",
                        "id": ctx.room_id,
                        "status": "read",
                        "timestamp": NOW,
                    },
                },
            ),
        ]

    async def test_read_all_with_one_unread(self, ctx, recorder):
        sender = ctx.sender
        notification_id = await _notify(sender["id"], str(ObjectId()))

        await handle_message(
            sender["id"],
            ctx.room_id,
            {"type": "notification_read", "read_type": "all"},
            sender["info"],
        )

        assert await _status(ctx.db, notification_id) == "read"
        assert [event[0] for event in recorder.sent] == ["personal", "event"]
        assert recorder.sent[0][3]["success"] is True
        assert recorder.sent[1][2]["data"]["read_type"] == "all"

    async def test_read_all_with_nothing_unread_still_succeeds(self, ctx, recorder):
        """與房間已讀、HTTP /read-all 一致：沒有未讀通知也回成功並同步其他裝置"""
        sender = ctx.sender

        await handle_message(
            sender["id"],
            ctx.room_id,
            {"type": "notification_read", "read_type": "all"},
            sender["info"],
        )

        assert [event[0] for event in recorder.sent] == ["personal", "event"]
        assert recorder.sent[0][3]["success"] is True
        assert recorder.sent[1][2]["data"]["read_type"] == "all"


@pytest.mark.asyncio
@pytest.mark.unit
class TestBackgroundAiTasks:
    """背景 AI task：完成即釋放強引用；只有未預期異常記錄為錯誤"""

    async def test_completed_task_released_silently(self, caplog):
        async def answer():
            return "ok"

        with caplog.at_level(logging.ERROR):
            task = _spawn_ai_task(answer())
            assert task in _background_ai_tasks
            await asyncio.wait([task])
            await asyncio.sleep(0)

        assert task not in _background_ai_tasks
        assert caplog.records == []

    async def test_failed_task_logged_and_released(self, caplog):
        async def explode():
            raise RuntimeError("provider exploded")

        with caplog.at_level(logging.ERROR):
            task = _spawn_ai_task(explode())
            await asyncio.wait([task])
            await asyncio.sleep(0)

        assert task not in _background_ai_tasks
        assert [(r.name, r.getMessage()) for r in caplog.records] == [
            ("app.websocket.handlers", "AI background task failed: provider exploded")
        ]

    async def test_cancelled_task_released_without_error(self, caplog):
        with caplog.at_level(logging.ERROR):
            task = _spawn_ai_task(asyncio.Event().wait())
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.wait([task])
            await asyncio.sleep(0)

        assert task not in _background_ai_tasks
        assert caplog.records == []
