"""訊息 HTTP API 行為測試（經由完整路由、依賴注入與 middleware）

涵蓋建立訊息的預設值、長度上限與 client_id 冪等重送、列表的引用預覽、
編輯（去除前後空白、拒絕空白、保留檔案資訊、只改 metadata）與搜尋排除已刪除訊息。
授權相關情境見 test_rooms_api.py。
"""

from datetime import UTC, datetime

import pytest
from bson import ObjectId

from app.database.mongodb import get_database
from app.models.message import MAX_CONTENT_LENGTH

FORM = {"Content-Type": "application/x-www-form-urlencoded"}
FILE_INFO = {
    "filename": "report.pdf",
    "file_size": 1024,
    "mime_type": "application/pdf",
}


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


async def _create_room(client, owner: dict, name: str) -> str:
    response = await client.post(
        "/api/rooms/", json={"name": name}, headers=owner["headers"]
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.fixture
async def chat(async_client, isolated_db_manager):
    """owner 建立公開房，member 加入"""
    owner = await _make_user(async_client, "owner")
    member = await _make_user(async_client, "member")
    room_id = await _create_room(async_client, owner, "lobby")
    joined = await async_client.post(
        f"/api/rooms/{room_id}/join", headers=member["headers"]
    )
    assert joined.status_code == 200
    return {"owner": owner, "member": member, "room_id": room_id}


async def _post(client, user: dict, room_id: str, content: str, **fields):
    return await client.post(
        "/api/messages/",
        json={"room_id": room_id, "content": content, **fields},
        headers=user["headers"],
    )


async def _send(client, user: dict, room_id: str, content: str, **fields) -> dict:
    response = await _post(client, user, room_id, content, **fields)
    assert response.status_code == 201, response.text
    return response.json()


async def _stored(message_id: str) -> dict:
    db = await get_database()
    return await db.messages.find_one({"_id": ObjectId(message_id)})


@pytest.mark.asyncio
@pytest.mark.integration
class TestCreateMessage:
    async def test_new_message_is_not_edited(self, async_client, chat):
        sent = await _send(async_client, chat["owner"], chat["room_id"], "嗨")

        stored = await _stored(sent["id"])
        assert (sent["edited"], sent["edited_at"]) == (False, None)
        assert (stored["edited"], stored["edited_at"]) == (False, None)

    @pytest.mark.parametrize(
        ("length", "status_code"),
        [(MAX_CONTENT_LENGTH, 201), (MAX_CONTENT_LENGTH + 1, 422)],
    )
    async def test_content_length_limit(self, async_client, chat, length, status_code):
        response = await _post(
            async_client, chat["owner"], chat["room_id"], "字" * length
        )

        assert response.status_code == status_code

    async def test_resend_with_same_client_id_returns_existing(
        self, async_client, chat
    ):
        owner, room_id = chat["owner"], chat["room_id"]
        other_room_id = await _create_room(async_client, owner, "other")

        first = await _send(async_client, owner, room_id, "原訊息", client_id="c-1")
        resent = await _send(async_client, owner, room_id, "重送", client_id="c-1")
        elsewhere = await _send(
            async_client, owner, other_room_id, "別房", client_id="c-1"
        )

        assert resent == first
        assert elsewhere["id"] != first["id"]
        db = await get_database()
        assert await db.messages.count_documents({"room_id": room_id}) == 1


@pytest.mark.asyncio
@pytest.mark.integration
class TestReplyPreviews:
    @pytest.mark.parametrize(
        "path", ["/api/messages/room/{room_id}", "/api/rooms/{room_id}/messages"]
    )
    async def test_list_includes_quoted_message(self, async_client, chat, path):
        owner, member, room_id = chat["owner"], chat["member"], chat["room_id"]
        question = await _send(async_client, owner, room_id, "晚餐吃什麼？")
        answer = await _send(
            async_client, member, room_id, "拉麵", reply_to=question["id"]
        )

        response = await async_client.get(
            path.format(room_id=room_id), headers=owner["headers"]
        )

        assert response.status_code == 200
        listed = response.json()
        assert [m["id"] for m in listed] == [question["id"], answer["id"]]
        assert listed[0]["reply_to_message"] is None
        quoted = listed[1]["reply_to_message"]
        # 引用預覽的時間沒有時區標記（前端不使用此欄位），只比對時間值
        quoted_at = datetime.fromisoformat(quoted.pop("created_at"))
        assert quoted_at.replace(tzinfo=UTC) == datetime.fromisoformat(
            question["created_at"]
        )
        assert quoted == {
            "id": question["id"],
            "content": "晚餐吃什麼？",
            "username": "owner",
        }


@pytest.mark.asyncio
@pytest.mark.integration
class TestEditMessage:
    async def _edit(self, client, user: dict, message_id: str, body: dict):
        return await client.put(
            f"/api/messages/{message_id}", json=body, headers=user["headers"]
        )

    async def test_edit_strips_content_and_keeps_file_info(self, async_client, chat):
        owner = chat["owner"]
        sent = await _send(
            async_client, owner, chat["room_id"], "附件", metadata=FILE_INFO
        )

        response = await self._edit(
            async_client, owner, sent["id"], {"content": "  更新說明  "}
        )

        assert response.status_code == 200
        edited = response.json()
        assert (edited["content"], edited["edited"]) == ("更新說明", True)
        assert edited["metadata"] == FILE_INFO
        stored = await _stored(sent["id"])
        assert (stored["content"], stored["metadata"]) == ("更新說明", FILE_INFO)

    async def test_blank_edit_rejected(self, async_client, chat):
        owner = chat["owner"]
        sent = await _send(async_client, owner, chat["room_id"], "原內容")

        response = await self._edit(async_client, owner, sent["id"], {"content": "   "})

        assert response.status_code == 400
        stored = await _stored(sent["id"])
        assert (stored["content"], stored["edited"]) == ("原內容", False)

    async def test_metadata_only_edit_keeps_content(self, async_client, chat):
        owner = chat["owner"]
        sent = await _send(async_client, owner, chat["room_id"], "附件")

        response = await self._edit(
            async_client, owner, sent["id"], {"metadata": FILE_INFO}
        )

        assert response.status_code == 200
        edited = response.json()
        assert (edited["content"], edited["metadata"]) == ("附件", FILE_INFO)
        assert edited["edited"] is False


@pytest.mark.asyncio
@pytest.mark.integration
class TestSearchMessages:
    async def test_deleted_messages_not_found(self, async_client, chat):
        owner, room_id = chat["owner"], chat["room_id"]
        await _send(async_client, owner, room_id, "蘋果派")
        removed = await _send(async_client, owner, room_id, "香蕉船")
        deleted = await async_client.delete(
            f"/api/messages/{removed['id']}", headers=owner["headers"]
        )
        assert deleted.status_code == 200

        async def search(body: dict) -> list[str]:
            response = await async_client.post(
                f"/api/messages/room/{room_id}/search",
                json=body,
                headers=owner["headers"],
            )
            assert response.status_code == 200, response.text
            return [m["content"] for m in response.json()]

        assert await search({}) == ["蘋果派"]
        assert await search({"keyword": "已被刪除"}) == []
        assert await search({"start_date": datetime(2000, 1, 1).isoformat()}) == [
            "蘋果派"
        ]
