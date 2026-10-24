"""WebSocket 認證鏈測試（真實 MongoDB / Redis）

websocket_auth_middleware → ticket 或 JWT 認證 → _get_user_info（停用帳號、
token_version）→ verify_room_membership，以及一次性 ws ticket 的發放與消費。
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId
from pymongo.errors import AutoReconnect, ServerSelectionTimeoutError
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.datastructures import Headers, QueryParams

from app.auth.jwt_handler import create_access_token, create_refresh_token
from app.database.redis_conn import get_redis
from app.utils.user_cache import set_cached_user
from app.utils.ws_ticket import WS_TICKET_PREFIX, create_ws_ticket, validate_ws_ticket
from app.websocket.auth import (
    authenticate_websocket,
    authenticate_websocket_by_ticket,
    extract_token_from_query,
    websocket_auth_middleware,
)
from app.websocket.handlers import handle_websocket_connection

FORM = {"Content-Type": "application/x-www-form-urlencoded"}
USER_INFO_KEYS = {"id", "username", "email", "full_name", "avatar", "is_active"}


def fake_ws(query: dict | None = None, headers: dict | None = None):
    websocket = Mock()
    websocket.query_params = QueryParams(query or {})
    websocket.headers = Headers(headers or {})
    return websocket


async def _make_user(client, name: str) -> dict:
    password = "password123"
    register = await client.post(
        "/api/auth/register",
        json={
            "username": name,
            "email": f"{name}@example.com",
            "password": password,
            "full_name": name.title(),
        },
    )
    assert register.status_code == 201
    login = await client.post(
        "/api/auth/login", data={"username": name, "password": password}, headers=FORM
    )
    tokens = login.json()
    return {
        "id": register.json()["user"]["id"],
        "username": name,
        "password": password,
        "token": tokens["access_token"],
        "refresh": tokens["refresh_token"],
        "headers": {"Authorization": f"Bearer {tokens['access_token']}"},
    }


@pytest.fixture
async def ctx(async_client, isolated_db_manager):
    """member 是房間成員、outsider 不是"""
    member = await _make_user(async_client, "wsmember")
    outsider = await _make_user(async_client, "wsoutsider")
    room = await async_client.post(
        "/api/rooms/", json={"name": "ws room"}, headers=member["headers"]
    )
    assert room.status_code == 201
    return {"member": member, "outsider": outsider, "room_id": room.json()["id"]}


@pytest.mark.asyncio
@pytest.mark.integration
class TestWsTicket:
    async def test_ticket_valid_once_for_its_room(self, ctx):
        user_id, room_id = ctx["member"]["id"], ctx["room_id"]
        ticket = await create_ws_ticket(user_id, room_id)

        ttl = await (await get_redis()).ttl(f"{WS_TICKET_PREFIX}{ticket}")
        assert 0 < ttl <= 30

        assert await validate_ws_ticket(ticket, room_id) == user_id
        assert await validate_ws_ticket(ticket, room_id) is None

    async def test_ticket_for_other_room_rejected_and_burned(self, ctx):
        user_id, room_id = ctx["member"]["id"], ctx["room_id"]
        ticket = await create_ws_ticket(user_id, room_id)

        assert await validate_ws_ticket(ticket, str(ObjectId())) is None
        assert await validate_ws_ticket(ticket, room_id) is None

    async def test_unknown_or_corrupted_ticket_rejected(self, ctx):
        redis = await get_redis()
        await redis.set(f"{WS_TICKET_PREFIX}corrupted", "not-json", ex=30)

        assert await validate_ws_ticket("does-not-exist", ctx["room_id"]) is None
        assert await validate_ws_ticket("corrupted", ctx["room_id"]) is None

    async def test_tickets_are_unique_and_unguessable(self, ctx):
        tickets = {
            await create_ws_ticket(ctx["member"]["id"], ctx["room_id"])
            for _ in range(5)
        }

        assert len(tickets) == 5
        assert all(len(ticket) >= 40 for ticket in tickets)

    async def test_ticket_endpoint(self, async_client, ctx):
        response = await async_client.post(
            "/api/ws/ticket",
            json={"room_id": ctx["room_id"]},
            headers=ctx["member"]["headers"],
        )
        anonymous = await async_client.post(
            "/api/ws/ticket", json={"room_id": ctx["room_id"]}
        )

        assert response.status_code == 200
        ticket = response.json()["ticket"]
        assert await validate_ws_ticket(ticket, ctx["room_id"]) == ctx["member"]["id"]
        assert anonymous.status_code in (401, 403)


@pytest.mark.unit
class TestExtractToken:
    def test_query_parameter(self):
        assert extract_token_from_query(fake_ws({"token": "abc"})) == "abc"

    def test_bearer_header(self):
        websocket = fake_ws(headers={"Authorization": "Bearer abc"})
        assert extract_token_from_query(websocket) == "abc"

    def test_query_takes_precedence(self):
        websocket = fake_ws({"token": "query"}, {"Authorization": "Bearer header"})
        assert extract_token_from_query(websocket) == "query"

    @pytest.mark.parametrize("header", ["Basic abc", "Token abc"])
    def test_non_bearer_scheme_rejected(self, header):
        assert (
            extract_token_from_query(fake_ws(headers={"Authorization": header})) is None
        )

    def test_missing(self):
        assert extract_token_from_query(fake_ws()) is None


@pytest.mark.asyncio
@pytest.mark.integration
class TestAuthenticateWebsocket:
    async def test_valid_token_returns_user_info(self, async_client, ctx):
        await async_client.put(
            "/api/auth/profile",
            json={"avatar": "/api/files/image/me.png"},
            headers=ctx["member"]["headers"],
        )

        info = await authenticate_websocket(fake_ws(), ctx["member"]["token"])

        assert set(info) == USER_INFO_KEYS
        assert info["id"] == ctx["member"]["id"]
        assert info["username"] == "wsmember"
        assert info["email"] == "wsmember@example.com"
        assert info["full_name"] == "Wsmember"
        assert info["avatar"] == "/api/files/image/me.png"
        assert info["is_active"] is True

    @pytest.mark.parametrize(
        "make_token",
        [
            pytest.param(lambda user: "not-a-jwt", id="garbage"),
            pytest.param(lambda user: user["refresh"], id="refresh-token"),
            pytest.param(
                lambda user: create_access_token({"sub": user["username"]}),
                id="missing-user-id",
            ),
            pytest.param(
                lambda user: create_access_token({"user_id": user["id"]}),
                id="missing-sub",
            ),
            pytest.param(
                lambda user: create_access_token(
                    {"sub": "ghost", "user_id": str(ObjectId())}
                ),
                id="unknown-user",
            ),
        ],
    )
    async def test_invalid_tokens_rejected(self, ctx, make_token):
        assert (
            await authenticate_websocket(fake_ws(), make_token(ctx["member"])) is None
        )

    async def test_refresh_token_type_is_checked(self, ctx):
        """refresh token 的 payload 與 access token 相同，只差 type 欄位"""
        token = create_refresh_token(
            {"sub": "wsmember", "user_id": ctx["member"]["id"], "token_version": 0}
        )
        assert await authenticate_websocket(fake_ws(), token) is None

    async def test_deactivated_user_rejected(self, async_client, ctx):
        member = ctx["member"]
        deleted = await async_client.delete(
            "/api/auth/profile", headers=member["headers"]
        )
        assert deleted.status_code == 200

        assert await authenticate_websocket(fake_ws(), member["token"]) is None
        ticket = await create_ws_ticket(member["id"], ctx["room_id"])
        assert await authenticate_websocket_by_ticket(ticket, ctx["room_id"]) is None

    async def test_token_from_before_password_change_rejected(self, async_client, ctx):
        member = ctx["member"]
        changed = await async_client.put(
            "/api/auth/change-password",
            json={"current_password": member["password"], "new_password": "newpass123"},
            headers=member["headers"],
        )
        assert changed.status_code == 200

        assert await authenticate_websocket(fake_ws(), member["token"]) is None
        fresh = create_access_token(
            {"sub": "wsmember", "user_id": member["id"], "token_version": 1}
        )
        assert (await authenticate_websocket(fake_ws(), fresh))["id"] == member["id"]

    async def test_token_without_version_claim_counts_as_version_zero(
        self, async_client, ctx
    ):
        """token_version 上線前簽發的 token（無此 claim）視為版本 0：改密碼後即失效"""
        member = ctx["member"]
        legacy = create_access_token({"sub": "wsmember", "user_id": member["id"]})

        assert (await authenticate_websocket(fake_ws(), legacy))["id"] == member["id"]

        changed = await async_client.put(
            "/api/auth/change-password",
            json={"current_password": member["password"], "new_password": "newpass123"},
            headers=member["headers"],
        )
        assert changed.status_code == 200
        assert await authenticate_websocket(fake_ws(), legacy) is None

    async def test_cache_entry_without_flags_counts_as_active_version_zero(self, ctx):
        """快取若是欄位上線前寫入的（缺 is_active / token_version），視為啟用中、版本 0"""
        member = ctx["member"]
        legacy_entry = {
            "_id": member["id"],
            "username": "wsmember",
            "email": "wsmember@example.com",
            "full_name": "Wsmember",
            "avatar": None,
        }
        await set_cached_user(member["id"], legacy_entry)

        info = await authenticate_websocket(fake_ws(), member["token"])

        assert info == {
            "id": member["id"],
            "username": "wsmember",
            "email": "wsmember@example.com",
            "full_name": "Wsmember",
            "avatar": None,
            "is_active": True,
        }
        newer = create_access_token(
            {"sub": "wsmember", "user_id": member["id"], "token_version": 1}
        )
        assert await authenticate_websocket(fake_ws(), newer) is None

    async def test_ticket_auth_does_not_need_token_version(self, async_client, ctx):
        """ticket 由已通過 HTTP 認證的請求發放，不再比對 token_version"""
        member = ctx["member"]
        await async_client.put(
            "/api/auth/change-password",
            json={"current_password": member["password"], "new_password": "newpass123"},
            headers=member["headers"],
        )
        ticket = await create_ws_ticket(member["id"], ctx["room_id"])

        info = await authenticate_websocket_by_ticket(ticket, ctx["room_id"])

        assert info["id"] == member["id"]


@pytest.mark.asyncio
@pytest.mark.integration
class TestWebsocketAuthMiddleware:
    async def test_ticket_member(self, ctx):
        ticket = await create_ws_ticket(ctx["member"]["id"], ctx["room_id"])

        info = await websocket_auth_middleware(
            fake_ws({"ticket": ticket}), ctx["room_id"]
        )

        assert info["id"] == ctx["member"]["id"]

    async def test_ticket_non_member(self, ctx):
        ticket = await create_ws_ticket(ctx["outsider"]["id"], ctx["room_id"])

        assert (
            await websocket_auth_middleware(fake_ws({"ticket": ticket}), ctx["room_id"])
            is None
        )

    async def test_invalid_ticket_does_not_fall_back_to_token(self, ctx):
        websocket = fake_ws({"ticket": "bogus", "token": ctx["member"]["token"]})

        assert await websocket_auth_middleware(websocket, ctx["room_id"]) is None

    @pytest.mark.parametrize("via", ["query", "header"])
    async def test_token_member(self, ctx, via):
        token = ctx["member"]["token"]
        websocket = (
            fake_ws({"token": token})
            if via == "query"
            else fake_ws(headers={"Authorization": f"Bearer {token}"})
        )

        info = await websocket_auth_middleware(websocket, ctx["room_id"])

        assert info["id"] == ctx["member"]["id"]

    async def test_token_non_member(self, ctx):
        websocket = fake_ws({"token": ctx["outsider"]["token"]})

        assert await websocket_auth_middleware(websocket, ctx["room_id"]) is None

    async def test_missing_room(self, ctx):
        websocket = fake_ws({"token": ctx["member"]["token"]})

        assert await websocket_auth_middleware(websocket, str(ObjectId())) is None

    async def test_lobby_open_to_any_authenticated_user(self, ctx):
        websocket = fake_ws({"token": ctx["outsider"]["token"]})

        info = await websocket_auth_middleware(websocket, "lobby")

        assert info["id"] == ctx["outsider"]["id"]

    async def test_no_credentials(self, ctx):
        assert await websocket_auth_middleware(fake_ws(), ctx["room_id"]) is None
        assert await websocket_auth_middleware(fake_ws(), "lobby") is None

    # 資料庫或 Redis 暫時故障不是認證失敗：往上拋，由 handler 以 4000 關閉讓前端重連，
    # 不能當成「不是成員」以 4001 拒絕（前端收到 4001 不重連）
    @pytest.mark.parametrize(
        ("target", "error"),
        [
            ("app.websocket.auth.validate_ws_ticket", RedisConnectionError("down")),
            (
                "app.websocket.auth.fetch_user_with_cache",
                ServerSelectionTimeoutError("down"),
            ),
            (
                "app.repositories.room_repository.RoomRepository.is_member",
                AutoReconnect("down"),
            ),
        ],
    )
    async def test_infrastructure_errors_propagate(self, ctx, target, error):
        ticket = await create_ws_ticket(ctx["member"]["id"], ctx["room_id"])

        with (
            patch(target, AsyncMock(side_effect=error)),
            pytest.raises(type(error)),
        ):
            await websocket_auth_middleware(fake_ws({"ticket": ticket}), ctx["room_id"])

    async def test_unexpected_auth_error_still_rejects(self, ctx):
        websocket = fake_ws({"token": ctx["member"]["token"]})

        with patch(
            "app.websocket.auth.decode_access_token", side_effect=ValueError("bad")
        ):
            assert await websocket_auth_middleware(websocket, ctx["room_id"]) is None

    async def test_left_member_can_no_longer_connect(self, async_client, ctx):
        joined = await async_client.post(
            f"/api/rooms/{ctx['room_id']}/join", headers=ctx["outsider"]["headers"]
        )
        assert joined.status_code == 200
        websocket = fake_ws({"token": ctx["outsider"]["token"]})
        assert await websocket_auth_middleware(websocket, ctx["room_id"]) is not None

        await async_client.post(
            f"/api/rooms/{ctx['room_id']}/leave", headers=ctx["outsider"]["headers"]
        )

        assert await websocket_auth_middleware(websocket, ctx["room_id"]) is None


@pytest.mark.asyncio
@pytest.mark.integration
class TestConnectionRejected:
    async def test_accept_then_close_4001_without_connecting(self, ctx):
        """先 accept 再以 4001 關閉（未 accept 就 close 會變成 HTTP 403 握手失敗）"""
        calls = []
        websocket = fake_ws({"token": ctx["outsider"]["token"]})
        websocket.accept = AsyncMock(side_effect=lambda: calls.append("accept"))
        websocket.close = AsyncMock(
            side_effect=lambda **kwargs: calls.append(("close", kwargs["code"]))
        )

        with patch("app.websocket.handlers.connection_manager") as manager:
            manager.connect = AsyncMock()
            await handle_websocket_connection(websocket, ctx["room_id"])

        assert calls == ["accept", ("close", 4001)]
        manager.connect.assert_not_called()
