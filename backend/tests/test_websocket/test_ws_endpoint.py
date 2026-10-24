"""WebSocket 端點整合測試：經由 ASGI 的真實連線（真實 MongoDB / Redis / ConnectionManager）

從 /ws/{room_id} 端點進入，走過中介層、路由、認證、handler 與連線管理器，
驗證客戶端實際收到的事件順序與內容：首次連線的歷史、重連時依 last_seq 補發、
前端使用的 type: "message" 別名、/summary 分派、ping / 錯誤處理。

Starlette 的 TestClient 會在另一個執行緒與 event loop 執行 app，而測試共用的
MongoDB / Redis 非同步連線綁定在 pytest 的 loop 上，因此改為在同一個 loop 內
直接驅動 ASGI 介面。
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

import pytest
from bson import ObjectId

from app.core.bot import BOT_USERNAME
from app.database.mongodb import get_database
from app.main import app
from app.models.user import UserInDB
from app.repositories.user_repository import UserRepository
from app.websocket import handlers
from app.websocket.manager import ConnectionManager

FORM = {"Content-Type": "application/x-www-form-urlencoded"}


class AsgiWebSocket:
    """在測試的 event loop 內直接驅動 app 的一條 WebSocket 連線"""

    def __init__(self, path: str, query: dict[str, str]):
        self._to_app: asyncio.Queue = asyncio.Queue()
        self._from_app: asyncio.Queue = asyncio.Queue()
        self._scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "scheme": "ws",
            "http_version": "1.1",
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "query_string": urlencode(query).encode(),
            "headers": [(b"host", b"testserver")],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "subprotocols": [],
            "state": {},
        }
        self._task: asyncio.Task | None = None

    async def open(self) -> dict:
        """送出連線請求，回傳 app 的第一個回應（accept 或 close）"""
        self._to_app.put_nowait({"type": "websocket.connect"})
        self._task = asyncio.create_task(
            app(self._scope, self._to_app.get, self._from_app.put)
        )
        return await self._next()

    async def _next(self) -> dict:
        return await asyncio.wait_for(self._from_app.get(), timeout=5)

    async def receive_json(self) -> dict:
        event = await self._next()
        assert event["type"] == "websocket.send", event
        return json.loads(event["text"])

    async def receive_close(self) -> dict:
        event = await self._next()
        assert event["type"] == "websocket.close", event
        return event

    def send_json(self, data: dict) -> None:
        self.send_text(json.dumps(data))

    def send_text(self, text: str) -> None:
        self._to_app.put_nowait({"type": "websocket.receive", "text": text})

    async def assert_silent(self) -> None:
        """讓其他 task 跑完一輪後，確認沒有多送任何事件"""
        await asyncio.sleep(0.05)
        assert self._from_app.empty(), self._from_app.get_nowait()

    async def disconnect(self) -> None:
        self._to_app.put_nowait({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self._task, timeout=5)


@pytest.fixture
async def manager(monkeypatch):
    """換上獨立的 ConnectionManager（debounce 0 秒），測試結束時清掉殘留計時器"""
    fresh = ConnectionManager()
    fresh._disconnect_debounce_seconds = 0
    fresh._room_rejoin_debounce_seconds = 0
    monkeypatch.setattr("app.websocket.manager.connection_manager", fresh)
    monkeypatch.setattr(handlers, "connection_manager", fresh)
    yield fresh
    pending = [*fresh._pending_offline.values(), *fresh._pending_room_leave.values()]
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


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
    return {
        "id": register.json()["user"]["id"],
        "username": name,
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


@pytest.fixture
async def ctx(async_client, isolated_db_manager, manager):
    """owner 建立公開房、member 加入"""
    owner = await _make_user(async_client, "owner")
    member = await _make_user(async_client, "member")
    room = await async_client.post(
        "/api/rooms/", json={"name": "ws endpoint room"}, headers=owner["headers"]
    )
    room_id = room.json()["id"]
    joined = await async_client.post(
        f"/api/rooms/{room_id}/join", headers=member["headers"]
    )
    assert joined.status_code == 200
    return SimpleNamespace(
        client=async_client, owner=owner, member=member, room_id=room_id
    )


async def _connect(ctx, user: dict, **query) -> AsgiWebSocket:
    ticket = await ctx.client.post(
        "/api/ws/ticket", json={"room_id": ctx.room_id}, headers=user["headers"]
    )
    websocket = AsgiWebSocket(
        f"/ws/{ctx.room_id}", {"ticket": ticket.json()["ticket"], **query}
    )
    accepted = await websocket.open()
    assert accepted["type"] == "websocket.accept", accepted
    return websocket


async def _post_messages(ctx, user: dict, contents: list[str]) -> None:
    for content in contents:
        response = await ctx.client.post(
            f"/api/rooms/{ctx.room_id}/messages",
            json={"room_id": ctx.room_id, "content": content},
            headers=user["headers"],
        )
        assert response.status_code == 201


async def _connection_preamble(websocket: AsgiWebSocket) -> dict:
    """連線後依序收到：房內在線列表、歡迎訊息、歷史（或補發），回傳第三個事件"""
    assert (await websocket.receive_json())["type"] == "room_users"
    assert (await websocket.receive_json())["type"] == "welcome"
    return await websocket.receive_json()


@pytest.mark.asyncio
@pytest.mark.integration
class TestConnectionHistory:
    async def test_first_connect_receives_recent_history(self, ctx):
        await _post_messages(ctx, ctx.owner, ["一", "二", "三"])

        websocket = await _connect(ctx, ctx.owner)
        history = await _connection_preamble(websocket)
        await websocket.disconnect()

        assert history["type"] == "message_history"
        assert history["room_id"] == ctx.room_id
        assert [(m["seq"], m["content"]) for m in history["messages"]] == [
            (1, "一"),
            (2, "二"),
            (3, "三"),
        ]

    async def test_reconnect_with_last_seq_receives_only_the_gap(self, ctx):
        await _post_messages(ctx, ctx.owner, ["一", "二", "三", "四", "五"])

        websocket = await _connect(ctx, ctx.owner, last_seq="3")
        sync = await _connection_preamble(websocket)
        await websocket.disconnect()

        assert sync["type"] == "message_sync"
        assert sync["last_seq"] == 3
        assert sync["full_reload"] is False
        assert sync["room_id"] == ctx.room_id
        assert isinstance(sync["timestamp"], str)
        assert [(m["seq"], m["content"]) for m in sync["messages"]] == [
            (4, "四"),
            (5, "五"),
        ]

    async def test_reconnect_up_to_date_receives_empty_sync(self, ctx):
        await _post_messages(ctx, ctx.owner, ["一"])

        websocket = await _connect(ctx, ctx.owner, last_seq="1")
        sync = await _connection_preamble(websocket)
        await websocket.disconnect()

        assert (sync["type"], sync["messages"]) == ("message_sync", [])

    async def test_gap_sync_failure_falls_back_to_history(self, ctx):
        """補發查詢失敗時退回送最近歷史，而不是讓客戶端什麼都收不到"""
        await _post_messages(ctx, ctx.owner, ["一", "二"])

        with patch(
            "app.services.message_service.MessageService.sync_messages_since",
            side_effect=RuntimeError("db hiccup"),
        ):
            websocket = await _connect(ctx, ctx.owner, last_seq="1")
            history = await _connection_preamble(websocket)
        await websocket.disconnect()

        assert history["type"] == "message_history"
        assert [m["content"] for m in history["messages"]] == ["一", "二"]

    @pytest.mark.parametrize("last_seq", ["", "abc", "-1"])
    async def test_invalid_last_seq_falls_back_to_history(self, ctx, last_seq):
        await _post_messages(ctx, ctx.owner, ["一"])

        websocket = await _connect(ctx, ctx.owner, last_seq=last_seq)
        history = await _connection_preamble(websocket)
        await websocket.disconnect()

        assert history["type"] == "message_history"
        assert [m["content"] for m in history["messages"]] == ["一"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestChatOverWebsocket:
    async def test_frontend_message_type_is_persisted_and_broadcast(self, ctx):
        """前端送的是 type: "message"：寫入 DB、回 ack、廣播給房內所有人並通知其他成員"""
        owner_ws = await _connect(ctx, ctx.owner)
        await _connection_preamble(owner_ws)
        member_ws = await _connect(ctx, ctx.member)
        await _connection_preamble(member_ws)
        joined = await owner_ws.receive_json()
        assert (joined["type"], joined["user"]["id"]) == (
            "user_joined",
            ctx.member["id"],
        )

        member_ws.send_json({"type": "message", "content": "嗨", "client_id": "c-1"})

        ack = await member_ws.receive_json()
        member_copy = await member_ws.receive_json()
        owner_copy = await owner_ws.receive_json()
        notification = await owner_ws.receive_json()
        await member_ws.assert_silent()
        await owner_ws.assert_silent()

        db = await get_database()
        stored = await db.messages.find_one({"room_id": ctx.room_id})
        assert (stored["content"], stored["user_id"], stored["client_id"]) == (
            "嗨",
            ctx.member["id"],
            "c-1",
        )
        assert ack["type"] == "ack"
        assert (ack["client_id"], ack["message_id"], ack["seq"]) == (
            "c-1",
            str(stored["_id"]),
            stored["seq"],
        )
        assert member_copy == owner_copy
        assert member_copy["type"] == "message"
        assert member_copy["room_id"] == ctx.room_id
        assert isinstance(member_copy["timestamp"], str)
        assert member_copy["payload"]["id"] == str(stored["_id"])
        assert member_copy["payload"]["content"] == "嗨"
        assert member_copy["payload"]["user"]["id"] == ctx.member["id"]

        # 即時通知的內容與 DB 中的通知一致（前端以 id 標記已讀，且必填欄位缺一即丟棄）
        stored_notification = await db.notifications.find_one(
            {"user_id": ctx.owner["id"]}
        )
        data = notification["data"]
        assert notification["type"] == "notification"
        assert data["id"] == str(stored_notification["_id"])
        assert data["user_id"] == ctx.owner["id"]
        assert data["title"] == stored_notification["title"]
        assert data["message"] == data["content"] == stored_notification["content"]
        assert data["metadata"] == data["data"] == stored_notification["metadata"]
        assert data["metadata"]["room_id"] == ctx.room_id
        assert data["room_id"] == ctx.room_id
        assert data["sender_id"] == ctx.member["id"]
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)

        await member_ws.disconnect()
        await owner_ws.disconnect()

    async def test_summary_runs_only_for_the_command(self, ctx):
        """一般訊息不觸發摘要；/summary 以房內對話產生摘要並以 bot 身分廣播"""
        db = await get_database()
        bot = await UserRepository(db).create(
            UserInDB(
                username=BOT_USERNAME,
                email="bot@chatroom.app",
                hashed_password="not-a-login-password",
            )
        )
        ai = AsyncMock()
        ai.summarize.return_value = "大家在打招呼"
        websocket = await _connect(ctx, ctx.owner)
        await _connection_preamble(websocket)

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value=bot.id),
            patch(
                "app.websocket.handlers.create_ai_service",
                AsyncMock(return_value=ai),
            ),
        ):
            websocket.send_json({"type": "message", "content": "大家好"})
            assert (await websocket.receive_json())["type"] == "ack"
            assert (await websocket.receive_json())["payload"]["content"] == "大家好"
            await websocket.assert_silent()
            ai.summarize.assert_not_awaited()

            websocket.send_json({"type": "message", "content": "/summary"})
            assert (await websocket.receive_json())["type"] == "ack"
            assert (await websocket.receive_json())["payload"]["content"] == "/summary"
            summary = await websocket.receive_json()

        await websocket.disconnect()

        ai.summarize.assert_awaited_once_with("owner: 大家好\nowner: /summary")
        assert summary["type"] == "message"
        assert summary["payload"]["user_id"] == bot.id
        assert summary["payload"]["content"] == "📋 對話摘要\n大家在打招呼"


@pytest.mark.asyncio
@pytest.mark.integration
class TestProtocolErrors:
    async def test_ping_invalid_json_and_unknown_type(self, ctx):
        websocket = await _connect(ctx, ctx.owner)
        await _connection_preamble(websocket)

        websocket.send_json({"type": "ping"})
        pong = await websocket.receive_json()
        websocket.send_text("not json")
        invalid = await websocket.receive_json()
        websocket.send_json({"type": "bogus"})
        unknown = await websocket.receive_json()
        await websocket.disconnect()

        assert pong["type"] == "pong"
        assert isinstance(pong["timestamp"], str)
        assert (invalid["type"], invalid["message"]) == (
            "error",
            "Invalid message format",
        )
        assert isinstance(invalid["timestamp"], str)
        assert unknown["type"] == "error"

    async def test_endpoint_closes_with_4000_on_unexpected_error(self, ctx):
        """連線處理本身拋出未預期的例外（例如清理連線失敗）時，端點以 4000 關閉"""

        async def broken_handler(websocket, room_id):
            await websocket.accept()
            raise RuntimeError("cleanup failed")

        with patch("app.websocket.routes.handle_websocket_connection", broken_handler):
            websocket = AsgiWebSocket(f"/ws/{ctx.room_id}", {})
            await websocket.open()
            closed = await websocket.receive_close()

        assert (closed["code"], closed["reason"]) == (4000, "Internal server error")

    async def test_invalid_ticket_closed_with_4001(self, ctx, manager):
        websocket = AsgiWebSocket(f"/ws/{ctx.room_id}", {"ticket": "bogus"})

        accepted = await websocket.open()
        closed = await websocket.receive_close()

        assert accepted["type"] == "websocket.accept"
        assert closed["code"] == 4001
        assert manager.active_connections == {}

    async def test_disconnect_leaves_room_and_goes_offline(self, ctx, manager):
        owner_ws = await _connect(ctx, ctx.owner)
        await _connection_preamble(owner_ws)
        member_ws = await _connect(ctx, ctx.member)
        await _connection_preamble(member_ws)
        await owner_ws.receive_json()  # user_joined

        await member_ws.disconnect()
        left = await owner_ws.receive_json()
        offline = await owner_ws.receive_json()
        await owner_ws.disconnect()

        assert (left["type"], left["user"]["id"]) == ("user_left", ctx.member["id"])
        assert (offline["type"], offline["user_id"], offline["is_online"]) == (
            "user_status_changed",
            ctx.member["id"],
            False,
        )
        assert ctx.member["id"] not in manager.active_connections


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unknown_room_rejected(async_client, isolated_db_manager, manager):
    user = await _make_user(async_client, "lonely")
    token = user["headers"]["Authorization"].removeprefix("Bearer ")
    websocket = AsgiWebSocket(f"/ws/{ObjectId()}", {"token": token})

    await websocket.open()
    closed = await websocket.receive_close()

    assert closed["code"] == 4001
