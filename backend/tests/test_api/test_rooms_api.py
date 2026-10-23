"""聊天室與訊息 HTTP API 授權測試（經由完整路由、依賴注入與 middleware）

涵蓋 require_room_membership、房間可見性（私人房不洩漏存在性）、
邀請碼僅 owner/admin 可見、加入策略、房主權限，以及訊息讀寫的成員 / 擁有者檢查。
"""

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId

from app.database.mongodb import get_database
from app.models.enums import MemberRole
from app.models.message import MessageInDB
from app.models.room import RoomInDB
from app.models.user import UserInDB

FORM = {"Content-Type": "application/x-www-form-urlencoded"}


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
    return {
        name: await _make_user(async_client, name)
        for name in ("owner", "member", "outsider")
    }


async def _create_room(client, owner: dict, **fields) -> dict:
    response = await client.post(
        "/api/rooms/", json={"name": "room", **fields}, headers=owner["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _join(client, room_id: str, user: dict, body: dict | None = None):
    return await client.post(
        f"/api/rooms/{room_id}/join", json=body, headers=user["headers"]
    )


MEMBER_ONLY_GETS = [
    "/api/rooms/{room_id}/messages",
    "/api/rooms/{room_id}/members",
    "/api/messages/room/{room_id}",
]


@pytest.mark.asyncio
@pytest.mark.integration
class TestRoomMembershipRequired:
    """require_room_membership：成員 200、公開房非成員 403、私人房非成員 404"""

    @pytest.mark.parametrize("path", MEMBER_ONLY_GETS)
    async def test_public_room(self, async_client, users, path):
        room = await _create_room(async_client, users["owner"])
        url = path.format(room_id=room["id"])

        owner = await async_client.get(url, headers=users["owner"]["headers"])
        outsider = await async_client.get(url, headers=users["outsider"]["headers"])

        assert owner.status_code == 200
        assert outsider.status_code == 403

    @pytest.mark.parametrize("path", MEMBER_ONLY_GETS)
    async def test_private_room_hides_existence(self, async_client, users, path):
        room = await _create_room(async_client, users["owner"], room_type="private")
        url = path.format(room_id=room["id"])

        owner = await async_client.get(url, headers=users["owner"]["headers"])
        outsider = await async_client.get(url, headers=users["outsider"]["headers"])
        missing = await async_client.get(
            path.format(room_id=str(ObjectId())), headers=users["owner"]["headers"]
        )

        assert owner.status_code == 200
        assert outsider.status_code == 404
        assert outsider.json() == missing.json()

    async def test_search_requires_membership(self, async_client, users):
        room = await _create_room(async_client, users["owner"])
        await async_client.post(
            f"/api/rooms/{room['id']}/messages",
            json={"room_id": room["id"], "content": "hello world"},
            headers=users["owner"]["headers"],
        )
        url = f"/api/messages/room/{room['id']}/search"

        owner = await async_client.post(
            url, json={"keyword": "hello"}, headers=users["owner"]["headers"]
        )
        outsider = await async_client.post(
            url, json={"keyword": "hello"}, headers=users["outsider"]["headers"]
        )

        assert owner.status_code == 200
        assert [m["content"] for m in owner.json()] == ["hello world"]
        assert outsider.status_code == 403

    async def test_members_list(self, async_client, users):
        room = await _create_room(async_client, users["owner"])
        await _join(async_client, room["id"], users["member"])

        response = await async_client.get(
            f"/api/rooms/{room['id']}/members", headers=users["member"]["headers"]
        )

        assert response.status_code == 200
        assert {m["username"] for m in response.json()} == {"owner", "member"}

    async def test_requires_authentication(self, async_client, users):
        room = await _create_room(async_client, users["owner"])

        response = await async_client.get(f"/api/rooms/{room['id']}/messages")

        assert response.status_code in (401, 403)
        assert response.status_code != 200


@pytest.mark.asyncio
@pytest.mark.integration
class TestRoomVisibility:
    """GET /rooms/{id}、列表與搜尋的可見性"""

    async def test_member_gets_full_details(self, async_client, users):
        room = await _create_room(async_client, users["owner"])

        response = await async_client.get(
            f"/api/rooms/{room['id']}", headers=users["owner"]["headers"]
        )

        assert response.status_code == 200
        body = response.json()
        assert body["members"] == [users["owner"]["id"]]
        assert body["is_member"] is True

    async def test_public_non_member_gets_summary(self, async_client, users):
        room = await _create_room(async_client, users["owner"])

        response = await async_client.get(
            f"/api/rooms/{room['id']}", headers=users["outsider"]["headers"]
        )

        assert response.status_code == 200
        body = response.json()
        assert "members" not in body
        assert "invite_code" not in body
        assert body["is_member"] is False
        assert body["member_count"] == 1

    async def test_private_non_member_gets_404(self, async_client, users):
        room = await _create_room(async_client, users["owner"], room_type="private")

        response = await async_client.get(
            f"/api/rooms/{room['id']}", headers=users["outsider"]["headers"]
        )

        assert response.status_code == 404

    async def test_private_rooms_not_listed_or_searchable(self, async_client, users):
        await _create_room(
            async_client, users["owner"], name="secret room", room_type="private"
        )
        await _create_room(async_client, users["owner"], name="open room")
        headers = users["outsider"]["headers"]

        listed = await async_client.get("/api/rooms", headers=headers)
        explore = await async_client.get(
            "/api/rooms", params={"exclude_joined": True}, headers=headers
        )
        searched = await async_client.get(
            "/api/rooms", params={"search": "room"}, headers=headers
        )

        for response in (listed, explore, searched):
            assert response.status_code == 200
            assert [r["name"] for r in response.json()] == ["open room"]
            assert all(r["is_member"] is False for r in response.json())

    async def test_my_rooms(self, async_client, users):
        room = await _create_room(async_client, users["owner"], name="mine")
        await _create_room(async_client, users["outsider"], name="theirs")
        await _join(async_client, room["id"], users["member"])

        response = await async_client.get(
            "/api/rooms/my", headers=users["member"]["headers"]
        )

        assert [r["name"] for r in response.json()] == ["mine"]
        assert response.json()[0]["is_member"] is True

    async def test_private_room_created_as_invite_only(self, async_client, users):
        room = await _create_room(async_client, users["owner"], room_type="private")

        assert room["room_type"] == "private"
        assert room["is_public"] is False
        assert room["join_policy"] == "invite"
        assert room["invite_code"]

    async def test_rename_keeps_room_public(self, async_client, users):
        room = await _create_room(async_client, users["owner"], name="before")

        updated = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"name": "after"},
            headers=users["owner"]["headers"],
        )

        assert updated.status_code == 200
        assert updated.json()["room_type"] == "public"
        assert updated.json()["is_public"] is True
        listed = await async_client.get(
            "/api/rooms", headers=users["outsider"]["headers"]
        )
        assert [r["name"] for r in listed.json()] == ["after"]

    async def test_switch_to_private_hides_room(self, async_client, users):
        room = await _create_room(async_client, users["owner"])

        updated = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"room_type": "private"},
            headers=users["owner"]["headers"],
        )

        assert updated.json()["is_public"] is False
        listed = await async_client.get(
            "/api/rooms", headers=users["outsider"]["headers"]
        )
        assert listed.json() == []


@pytest.mark.asyncio
@pytest.mark.integration
class TestInviteCodeVisibility:
    """邀請碼僅 owner / admin 可見"""

    async def test_only_owner_sees_invite_code(self, async_client, users):
        room = await _create_room(async_client, users["owner"], room_type="private")
        joined = await _join(
            async_client,
            room["id"],
            users["member"],
            {"invite_code": room["invite_code"]},
        )
        assert joined.status_code == 200

        as_owner = await async_client.get(
            f"/api/rooms/{room['id']}", headers=users["owner"]["headers"]
        )
        as_member = await async_client.get(
            f"/api/rooms/{room['id']}", headers=users["member"]["headers"]
        )

        assert as_owner.json()["invite_code"] == room["invite_code"]
        assert as_member.status_code == 200
        assert as_member.json()["invite_code"] is None

    async def test_update_response_keeps_invite_code_for_owner(
        self, async_client, users
    ):
        room = await _create_room(async_client, users["owner"], room_type="private")

        updated = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"description": "new description"},
            headers=users["owner"]["headers"],
        )

        assert updated.json()["invite_code"] == room["invite_code"]

    async def test_room_lists_never_include_invite_code(self, async_client, users):
        await _create_room(async_client, users["owner"], room_type="private")

        mine = await async_client.get(
            "/api/rooms/my", headers=users["owner"]["headers"]
        )

        assert all("invite_code" not in r for r in mine.json())

    async def test_validate_invitation(self, async_client, users):
        room = await _create_room(async_client, users["owner"], room_type="private")

        valid = await async_client.post(
            "/api/invitations/validate",
            json={"invite_code": room["invite_code"]},
            headers=users["outsider"]["headers"],
        )
        invalid = await async_client.post(
            "/api/invitations/validate",
            json={"invite_code": "not-a-real-code"},
            headers=users["outsider"]["headers"],
        )

        assert valid.status_code == 200
        assert valid.json()["valid"] is True
        assert valid.json()["room_id"] == room["id"]
        assert valid.json()["inviter_name"] == "owner"
        assert invalid.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
class TestJoinPolicies:
    """加入策略：直接、密碼、邀請碼、人數上限"""

    async def _is_member(self, client, room_id: str, user: dict) -> bool:
        response = await client.get(
            f"/api/rooms/{room_id}/messages", headers=user["headers"]
        )
        return response.status_code == 200

    async def test_direct_join(self, async_client, users):
        room = await _create_room(async_client, users["owner"])

        first = await _join(async_client, room["id"], users["member"])
        again = await _join(async_client, room["id"], users["member"])

        assert first.status_code == 200
        assert first.json() == {"message": "成功加入房間"}
        assert again.status_code == 200
        assert again.json() == {"message": "您已經是該房間的成員"}
        assert await self._is_member(async_client, room["id"], users["member"])

    async def test_private_room_rejects_direct_join(self, async_client, users):
        """公開房改成私人後保留 DIRECT 策略，仍不允許直接加入"""
        room = await _create_room(async_client, users["owner"])
        await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"room_type": "private"},
            headers=users["owner"]["headers"],
        )

        response = await _join(async_client, room["id"], users["member"])

        assert response.status_code == 403
        assert not await self._is_member(async_client, room["id"], users["member"])

    async def test_password_policy_without_password_set(self, async_client, users):
        room = await _create_room(async_client, users["owner"], join_policy="password")

        response = await _join(
            async_client, room["id"], users["member"], {"password": "anything"}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "房間未設置密碼"

    @pytest.mark.parametrize(
        ("expires_in", "join_status"),
        [(timedelta(hours=-1), 400), (timedelta(hours=1), 200)],
    )
    async def test_invite_code_expiry(
        self, async_client, isolated_db_manager, users, expires_in, join_status
    ):
        room = await _create_room(async_client, users["owner"], room_type="private")
        await isolated_db_manager.database["rooms"].update_one(
            {"_id": ObjectId(room["id"])},
            {"$set": {"invite_code_expires_at": datetime.now(UTC) + expires_in}},
        )

        validated = await async_client.post(
            "/api/invitations/validate",
            json={"invite_code": room["invite_code"]},
            headers=users["member"]["headers"],
        )
        joined = await _join(
            async_client,
            room["id"],
            users["member"],
            {"invite_code": room["invite_code"]},
        )

        assert validated.status_code == join_status
        assert joined.status_code == join_status
        if join_status == 400:
            assert joined.json()["detail"] == "邀請碼已過期"
            assert validated.json()["detail"] == "邀請碼已過期"

    async def test_password_join(self, async_client, users):
        room = await _create_room(
            async_client, users["owner"], join_policy="password", password="secret123"
        )

        for body in (None, {}, {"password": "wrongpass"}):
            response = await _join(async_client, room["id"], users["member"], body)
            assert response.status_code == 400
        assert not await self._is_member(async_client, room["id"], users["member"])

        ok = await _join(
            async_client, room["id"], users["member"], {"password": "secret123"}
        )
        assert ok.status_code == 200
        assert await self._is_member(async_client, room["id"], users["member"])

    async def test_invite_join(self, async_client, users):
        room = await _create_room(async_client, users["owner"], room_type="private")

        for body in (None, {}, {"invite_code": "wrong-code"}):
            response = await _join(async_client, room["id"], users["member"], body)
            assert response.status_code == 400
        assert not await self._is_member(async_client, room["id"], users["member"])

        ok = await _join(
            async_client,
            room["id"],
            users["member"],
            {"invite_code": room["invite_code"]},
        )
        assert ok.status_code == 200

    async def test_full_room_rejects_join(self, async_client, users):
        room = await _create_room(async_client, users["owner"], max_members=2)

        first = await _join(async_client, room["id"], users["member"])
        second = await _join(async_client, room["id"], users["outsider"])

        assert first.status_code == 200
        assert second.status_code == 400
        assert not await self._is_member(async_client, room["id"], users["outsider"])

    async def test_join_missing_room(self, async_client, users):
        response = await _join(async_client, str(ObjectId()), users["member"])

        assert response.status_code == 404

    async def test_password_change_revokes_old_room_password(self, async_client, users):
        room = await _create_room(
            async_client, users["owner"], join_policy="password", password="oldsecret"
        )
        updated = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"password": "newsecret"},
            headers=users["owner"]["headers"],
        )
        assert updated.status_code == 200

        old = await _join(
            async_client, room["id"], users["member"], {"password": "oldsecret"}
        )
        new = await _join(
            async_client, room["id"], users["outsider"], {"password": "newsecret"}
        )

        assert old.status_code == 400
        assert new.status_code == 200

    async def test_other_update_keeps_room_password(self, async_client, users):
        room = await _create_room(
            async_client, users["owner"], join_policy="password", password="secret123"
        )
        await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"description": "updated"},
            headers=users["owner"]["headers"],
        )

        ok = await _join(
            async_client, room["id"], users["member"], {"password": "secret123"}
        )

        assert ok.status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
class TestRoomOwnership:
    """房主權限：更新、刪除、離開"""

    async def test_only_owner_can_update(self, async_client, users):
        room = await _create_room(async_client, users["owner"])
        await _join(async_client, room["id"], users["member"])

        response = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"name": "hijacked"},
            headers=users["member"]["headers"],
        )

        assert response.status_code == 403

    async def test_owner_can_keep_room_name(self, async_client, users):
        room = await _create_room(async_client, users["owner"], name="same")

        response = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"name": "same", "description": "d"},
            headers=users["owner"]["headers"],
        )

        assert response.status_code == 200

    async def test_rename_to_existing_name_conflicts(self, async_client, users):
        await _create_room(async_client, users["outsider"], name="taken")
        room = await _create_room(async_client, users["owner"], name="mine")

        response = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"name": "taken"},
            headers=users["owner"]["headers"],
        )

        assert response.status_code == 409

    async def test_duplicate_room_name_conflicts(self, async_client, users):
        await _create_room(async_client, users["owner"], name="dup")

        response = await async_client.post(
            "/api/rooms/", json={"name": "dup"}, headers=users["outsider"]["headers"]
        )

        assert response.status_code == 409

    async def test_max_members_cannot_drop_below_member_count(
        self, async_client, users
    ):
        room = await _create_room(async_client, users["owner"])
        await _join(async_client, room["id"], users["member"])
        await _join(async_client, room["id"], users["outsider"])

        too_small = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"max_members": 2},
            headers=users["owner"]["headers"],
        )
        exact = await async_client.put(
            f"/api/rooms/{room['id']}",
            json={"max_members": 3},
            headers=users["owner"]["headers"],
        )

        assert too_small.status_code == 400
        assert exact.status_code == 200
        assert exact.json()["max_members"] == 3
        stored = await async_client.get(
            f"/api/rooms/{room['id']}", headers=users["owner"]["headers"]
        )
        assert stored.json()["max_members"] == 3

    async def test_only_owner_can_delete(self, async_client, users):
        room = await _create_room(async_client, users["owner"])
        await _join(async_client, room["id"], users["member"])

        denied = await async_client.delete(
            f"/api/rooms/{room['id']}", headers=users["member"]["headers"]
        )
        assert denied.status_code == 403

        deleted = await async_client.delete(
            f"/api/rooms/{room['id']}", headers=users["owner"]["headers"]
        )
        assert deleted.status_code == 200
        assert deleted.json() == {"message": "聊天室刪除成功"}
        gone = await async_client.get(
            f"/api/rooms/{room['id']}", headers=users["owner"]["headers"]
        )
        assert gone.status_code == 404

    async def test_member_leave_revokes_access(self, async_client, users):
        room = await _create_room(async_client, users["owner"])
        await _join(async_client, room["id"], users["member"])

        left = await async_client.post(
            f"/api/rooms/{room['id']}/leave", headers=users["member"]["headers"]
        )
        assert left.status_code == 200
        assert left.json() == {"message": "成功離開房間"}

        messages = await async_client.get(
            f"/api/rooms/{room['id']}/messages", headers=users["member"]["headers"]
        )
        assert messages.status_code == 403

    async def test_owner_cannot_leave(self, async_client, users):
        room = await _create_room(async_client, users["owner"])

        response = await async_client.post(
            f"/api/rooms/{room['id']}/leave", headers=users["owner"]["headers"]
        )

        assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
class TestMessageAuthorization:
    """訊息的發送、讀取、修改、刪除授權"""

    async def _send(self, client, room_id: str, user: dict, content: str = "hi"):
        return await client.post(
            f"/api/rooms/{room_id}/messages",
            json={"room_id": room_id, "content": content},
            headers=user["headers"],
        )

    async def test_path_room_id_overrides_body(self, async_client, users):
        """POST /rooms/{room_id}/messages 以路徑的 room_id 為準"""
        target = await _create_room(async_client, users["owner"], name="target")
        other = await _create_room(async_client, users["owner"], name="other")

        response = await async_client.post(
            f"/api/rooms/{target['id']}/messages",
            json={"room_id": other["id"], "content": "where am I"},
            headers=users["owner"]["headers"],
        )

        assert response.status_code == 201
        assert response.json()["room_id"] == target["id"]
        other_history = await async_client.get(
            f"/api/rooms/{other['id']}/messages", headers=users["owner"]["headers"]
        )
        assert other_history.json() == []

    async def test_only_members_can_send(self, async_client, users):
        room = await _create_room(async_client, users["owner"])

        member = await self._send(async_client, room["id"], users["owner"])
        outsider = await self._send(async_client, room["id"], users["outsider"])
        via_messages_api = await async_client.post(
            "/api/messages/",
            json={"room_id": room["id"], "content": "sneaky"},
            headers=users["outsider"]["headers"],
        )

        assert member.status_code == 201
        assert member.json()["content"] == "hi"
        assert outsider.status_code == 403
        assert via_messages_api.status_code == 403

    async def test_users_cannot_post_system_messages(self, async_client, users):
        """system 訊息在前端顯示為系統公告，使用者不可自行建立"""
        room = await _create_room(async_client, users["owner"])
        body = {"room_id": room["id"], "content": "系統公告", "message_type": "system"}

        via_room = await async_client.post(
            f"/api/rooms/{room['id']}/messages",
            json=body,
            headers=users["owner"]["headers"],
        )
        via_messages_api = await async_client.post(
            "/api/messages/", json=body, headers=users["owner"]["headers"]
        )

        assert via_room.status_code == via_messages_api.status_code == 403
        history = await async_client.get(
            f"/api/rooms/{room['id']}/messages", headers=users["owner"]["headers"]
        )
        assert history.json() == []

    async def test_room_messages_returned_in_order(self, async_client, users):
        room = await _create_room(async_client, users["owner"])
        for content in ("first", "second", "third"):
            await self._send(async_client, room["id"], users["owner"], content)

        response = await async_client.get(
            f"/api/rooms/{room['id']}/messages", headers=users["owner"]["headers"]
        )

        assert [m["content"] for m in response.json()] == ["first", "second", "third"]
        assert [m["seq"] for m in response.json()] == [1, 2, 3]

    async def test_get_message_requires_membership(self, async_client, users):
        public = await _create_room(async_client, users["owner"], name="public")
        private = await _create_room(
            async_client, users["owner"], name="private", room_type="private"
        )
        public_msg = (
            await self._send(async_client, public["id"], users["owner"])
        ).json()
        private_msg = (
            await self._send(async_client, private["id"], users["owner"])
        ).json()

        def get(message_id, user):
            return async_client.get(
                f"/api/messages/{message_id}", headers=user["headers"]
            )

        assert (await get(public_msg["id"], users["owner"])).status_code == 200
        assert (await get(private_msg["id"], users["owner"])).status_code == 200
        assert (await get(public_msg["id"], users["outsider"])).status_code == 403
        # 私人房非成員與不存在的訊息回應相同，不洩漏存在性
        hidden = await get(private_msg["id"], users["outsider"])
        missing = await get(str(ObjectId()), users["outsider"])
        assert hidden.status_code == missing.status_code == 404
        assert hidden.json() == missing.json()

    async def test_only_sender_can_edit_or_delete(self, async_client, users):
        room = await _create_room(async_client, users["owner"])
        await _join(async_client, room["id"], users["member"])
        message = (await self._send(async_client, room["id"], users["owner"])).json()
        url = f"/api/messages/{message['id']}"

        edit_denied = await async_client.put(
            url, json={"content": "hacked"}, headers=users["member"]["headers"]
        )
        delete_denied = await async_client.delete(
            url, headers=users["member"]["headers"]
        )
        assert edit_denied.status_code == 403
        assert delete_denied.status_code == 403

        edited = await async_client.put(
            url, json={"content": "edited"}, headers=users["owner"]["headers"]
        )
        assert edited.status_code == 200
        assert edited.json()["content"] == "edited"
        assert edited.json()["edited"] is True

        deleted = await async_client.delete(url, headers=users["owner"]["headers"])
        assert deleted.status_code == 200
        assert deleted.json() == {"message": "訊息刪除成功"}
        history = await async_client.get(
            f"/api/rooms/{room['id']}/messages", headers=users["owner"]["headers"]
        )
        assert history.json() == []


# 比預設分頁筆數（50）多一筆
CROWD = 51

PAGINATED_LISTS = [
    "/api/rooms",
    "/api/rooms/my",
    "/api/rooms/{room_id}/members",
    "/api/rooms/{room_id}/messages",
    "/api/messages/room/{room_id}",
]
MESSAGE_LISTS = PAGINATED_LISTS[3:]


@pytest.fixture
async def crowded(async_client, users) -> str:
    """owner 可見 51 個房間；其中回傳的房間有 51 位成員與 51 則訊息（seq 1~51）"""
    db = await get_database()
    owner_id = users["owner"]["id"]
    room_id = (await _create_room(async_client, users["owner"], name="crowded"))["id"]
    now = datetime.now(UTC)

    await db.rooms.insert_many(
        [
            RoomInDB(
                name=f"filler-{i:02d}",
                owner_id=owner_id,
                owner_name="owner",
                members=[owner_id],
                member_roles={owner_id: MemberRole.OWNER},
            ).model_dump(exclude={"id"})
            for i in range(CROWD - 1)
        ]
    )

    member_ids = [ObjectId() for _ in range(CROWD - 1)]
    await db.users.insert_many(
        [
            {
                "_id": member_id,
                **UserInDB(
                    username=f"crowd{i:02d}",
                    email=f"crowd{i:02d}@example.com",
                    hashed_password="unused",
                ).model_dump(exclude={"id"}),
            }
            for i, member_id in enumerate(member_ids)
        ]
    )
    await db.rooms.update_one(
        {"_id": ObjectId(room_id)},
        {"$push": {"members": {"$each": [str(m) for m in member_ids]}}},
    )

    await db.messages.insert_many(
        [
            MessageInDB(
                room_id=room_id,
                user_id=owner_id,
                username="owner",
                content=f"m{seq}",
                seq=seq,
                created_at=now + timedelta(seconds=seq),
                updated_at=now + timedelta(seconds=seq),
            ).model_dump(exclude={"id"})
            for seq in range(1, CROWD + 1)
        ]
    )
    return room_id


@pytest.mark.asyncio
@pytest.mark.integration
class TestListQueryParams:
    """列表端點的分頁 / 搜尋參數：預設值與上下界"""

    @pytest.mark.parametrize("path", PAGINATED_LISTS)
    async def test_limit_default_and_bounds(self, async_client, users, crowded, path):
        """預設 50 筆；limit 接受 1~100，0 與 101 回 422"""
        url = path.format(room_id=crowded)

        async def fetch(**params):
            return await async_client.get(
                url, params=params, headers=users["owner"]["headers"]
            )

        default = await fetch()
        smallest = await fetch(limit=1)
        largest = await fetch(limit=100)
        below = await fetch(limit=0)
        above = await fetch(limit=101)

        assert [r.status_code for r in (default, smallest, largest)] == [200] * 3
        assert [len(r.json()) for r in (default, smallest, largest)] == [50, 1, CROWD]
        assert below.status_code == above.status_code == 422

    @pytest.mark.parametrize("path", MESSAGE_LISTS)
    async def test_default_page_is_latest_messages(
        self, async_client, users, crowded, path
    ):
        """未帶參數時回傳最新 50 則（由舊到新），不跳過最新的訊息"""
        response = await async_client.get(
            path.format(room_id=crowded), headers=users["owner"]["headers"]
        )

        assert [m["seq"] for m in response.json()] == list(range(2, CROWD + 1))

    @pytest.mark.parametrize("path", MESSAGE_LISTS)
    async def test_before_seq_lower_bound(self, async_client, users, crowded, path):
        """before_seq 最小為 1（取 seq < 1，即空列表）；0 回 422"""
        url = path.format(room_id=crowded)
        headers = users["owner"]["headers"]

        at_bound = await async_client.get(
            url, params={"before_seq": 1}, headers=headers
        )
        next_page = await async_client.get(
            url, params={"before_seq": 3}, headers=headers
        )
        below = await async_client.get(url, params={"before_seq": 0}, headers=headers)

        assert at_bound.status_code == 200
        assert at_bound.json() == []
        assert [m["seq"] for m in next_page.json()] == [1, 2]
        assert below.status_code == 422

    async def test_search_max_length(self, async_client, users):
        await _create_room(async_client, users["owner"], name="a" * 100)
        headers = users["outsider"]["headers"]

        at_limit = await async_client.get(
            "/api/rooms", params={"search": "a" * 100}, headers=headers
        )
        too_long = await async_client.get(
            "/api/rooms", params={"search": "a" * 101}, headers=headers
        )

        assert at_limit.status_code == 200
        assert [r["name"] for r in at_limit.json()] == ["a" * 100]
        assert too_long.status_code == 422

    async def test_trailing_slash_served_without_redirect(self, async_client, users):
        """/api/rooms 與 /api/rooms/ 都直接回 200（不經 307 轉址）"""
        await _create_room(async_client, users["owner"], name="listed")
        headers = users["outsider"]["headers"]

        bare = await async_client.get("/api/rooms", headers=headers)
        slashed = await async_client.get("/api/rooms/", headers=headers)

        assert bare.status_code == slashed.status_code == 200
        assert slashed.json() == bare.json()
        assert [r["name"] for r in slashed.json()] == ["listed"]
