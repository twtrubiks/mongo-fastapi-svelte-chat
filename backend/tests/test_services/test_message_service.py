"""訊息服務整合測試 - 使用 Mock Repository"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import ForbiddenError
from app.models.message import (
    MessageCreate,
    MessageInDB,
    MessageResponse,
    MessageStatus,
    MessageType,
    MessageUpdate,
)
from app.models.user import UserInDB
from app.services.message_service import MessageService


@pytest.mark.unit
class TestMessageServiceIntegration:
    """測試訊息服務"""

    @pytest.mark.asyncio
    async def test_create_message(self, message_service_with_mocks):
        """測試創建訊息"""
        service = message_service_with_mocks
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        username = "testuser"

        # 配置 Mock 回傳值
        mock_message_id = str(ObjectId())
        mock_message = MessageResponse(
            id=mock_message_id,
            content="測試訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username=username,
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # 配置用戶 mock
        mock_user = UserInDB(
            id=user_id,
            username=username,
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 設定 mock 方法的回傳值
        service.message_repo.create.return_value = mock_message
        service.room_repo.get_by_id.return_value = {"_id": room_id, "name": "Test Room"}
        service.room_repo.is_member.return_value = True

        message_data = MessageCreate(
            room_id=room_id, content="測試訊息", message_type=MessageType.TEXT
        )

        # 配置 user_repo mock
        service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

        result = await service.create_message(
            user_id=user_id, message_data=message_data
        )

        assert result.content == "測試訊息"
        assert result.message_type == MessageType.TEXT
        assert result.user_id == user_id
        assert result.room_id == room_id
        assert result.username == username
        assert result.status == MessageStatus.SENT

    @pytest.mark.asyncio
    async def test_create_message_with_reply(self, message_service_with_mocks):
        """測試創建回覆訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        username = "testuser"

        # 配置原始訊息
        original_message_id = str(ObjectId())
        original_message = MessageResponse(
            id=original_message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username=username,
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # 配置回覆訊息
        reply_message_id = str(ObjectId())
        reply_message = MessageResponse(
            id=reply_message_id,
            content="回覆訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username=username,
            status=MessageStatus.SENT,
            edited=False,
            reply_to=original_message_id,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # 設定 mock 方法的回傳值
        service.message_repo.create.side_effect = [original_message, reply_message]
        # reply_to 驗證需要 get_by_id 回傳同房間的訊息
        service.message_repo.get_by_id.return_value = original_message
        service.room_repo.get_by_id.return_value = {"_id": room_id, "name": "Test Room"}
        service.room_repo.is_member.return_value = True

        # 配置用戶 mock
        mock_user = UserInDB(
            id=str(ObjectId()),
            username=username,
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 創建原始訊息
        original_message_data = MessageCreate(
            room_id=room_id, content="原始訊息", message_type=MessageType.TEXT
        )

        # 配置 user_repo mock
        service.user_repo.get_by_id = AsyncMock(return_value=mock_user)

        original_result = await service.create_message(
            user_id=user_id, message_data=original_message_data
        )

        # 創建回覆訊息
        reply_message_data = MessageCreate(
            room_id=room_id,
            content="回覆訊息",
            message_type=MessageType.TEXT,
            reply_to=original_result.id,
        )

        reply_result = await service.create_message(
            user_id=user_id, message_data=reply_message_data
        )

        assert reply_result.reply_to == original_result.id
        assert reply_result.content == "回覆訊息"

    @pytest.mark.asyncio
    async def test_get_message_by_id(self, message_service_with_mocks):
        """測試根據 ID 獲取訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        message_id = str(ObjectId())

        # 配置 Mock 回傳值
        mock_message = MessageResponse(
            id=message_id,
            content="測試訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        service.message_repo.get_with_reply.return_value = mock_message

        # 根據 ID 獲取訊息
        result = await service.get_message_by_id(message_id=message_id)

        assert result.id == message_id
        assert result.content == "測試訊息"
        assert result.user_id == user_id

    @pytest.mark.asyncio
    async def test_get_room_messages(self, message_service_with_mocks):
        """測試獲取房間訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"

        # 配置 Mock 回傳值
        mock_messages = [
            MessageResponse(
                id=str(ObjectId()),
                content=f"訊息 {i}",
                message_type=MessageType.TEXT,
                user_id=user_id,
                room_id=room_id,
                username="testuser",
                status=MessageStatus.SENT,
                edited=False,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for i in range(3)
        ]

        service.message_repo.get_room_messages.return_value = mock_messages
        service.room_repo.is_member.return_value = True

        # 獲取房間訊息
        result = await service.get_room_messages(room_id=room_id)

        assert len(result) == 3
        assert all(msg.room_id == room_id for msg in result)

    @pytest.mark.asyncio
    async def test_update_message(self, message_service_with_mocks):
        """測試更新訊息"""
        service = message_service_with_mocks
        room_id = "test_room_id"
        user_id = "test_user_id"
        message_id = str(ObjectId())

        # 配置原始訊息
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,  # 相同的使用者
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # 配置更新後的訊息
        updated_message = MessageResponse(
            id=message_id,
            content="更新後的訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        service.message_repo.get_by_id.return_value = original_message
        service.message_repo.update.return_value = updated_message

        update_data = MessageUpdate(content="更新後的訊息")

        result = await service.update_message(
            message_id=message_id, user_id=user_id, update_data=update_data
        )

        assert result.content == "更新後的訊息"
        assert result.id == message_id

    @pytest.mark.asyncio
    async def test_delete_message(self, message_service_with_mocks):
        """測試刪除訊息"""
        service = message_service_with_mocks
        message_id = str(ObjectId())
        user_id = "test_user_id"

        # 配置原始訊息
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,  # 相同的使用者
            room_id="test_room_id",
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        service.message_repo.get_by_id.return_value = original_message
        service.message_repo.delete.return_value = True

        await service.delete_message(message_id=message_id, user_id=user_id)

    @pytest.mark.asyncio
    async def test_update_message_unauthorized(self, message_service_with_mocks):
        """測試未授權更新訊息"""
        service = message_service_with_mocks
        message_id = str(ObjectId())
        user_id = "test_user_id"
        other_user_id = "other_user_id"

        # 配置原始訊息（屬於其他使用者）
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=other_user_id,  # 不同的使用者
            room_id="test_room_id",
            username="otheruser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        service.message_repo.get_by_id.return_value = original_message

        update_data = MessageUpdate(content="嘗試更新")

        with pytest.raises(ForbiddenError, match="您只能編輯自己的訊息"):
            await service.update_message(
                message_id=message_id, user_id=user_id, update_data=update_data
            )

    @pytest.mark.asyncio
    async def test_delete_message_unauthorized(self, message_service_with_mocks):
        """測試未授權刪除訊息"""
        service = message_service_with_mocks
        message_id = str(ObjectId())
        user_id = "test_user_id"
        other_user_id = "other_user_id"

        # 配置原始訊息（屬於其他使用者）
        original_message = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=other_user_id,  # 不同的使用者
            room_id="test_room_id",
            username="otheruser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        service.message_repo.get_by_id.return_value = original_message

        with pytest.raises(ForbiddenError, match="您只能刪除自己的訊息"):
            await service.delete_message(message_id=message_id, user_id=user_id)


def _make_user(user_id: str, username: str = "testuser") -> UserInDB:
    """建立測試用使用者"""
    return UserInDB(
        id=user_id,
        username=username,
        email="test@example.com",
        hashed_password="hashed_password",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _setup_create_mocks(service, room_id: str, user_id: str) -> None:
    """配置 create_message 所需的房間/成員/使用者 mock"""
    service.room_repo.get_by_id.return_value = {"_id": room_id, "name": "Test Room"}
    service.room_repo.is_member.return_value = True
    service.user_repo.get_by_id = AsyncMock(return_value=_make_user(user_id))


@pytest.mark.unit
class TestMessageSeqAndIdempotency:
    """測試訊息序號與冪等去重"""

    @pytest.mark.asyncio
    async def test_create_message_assigns_seq(self, message_service_with_mocks):
        """測試創建訊息時取得並寫入房間序號"""
        service = message_service_with_mocks
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        _setup_create_mocks(service, room_id, user_id)

        service.message_repo.next_room_seq.return_value = 42

        async def echo_create(doc):
            # 模擬 repository：注入 id 後原樣回傳
            doc.id = str(ObjectId())
            return doc

        service.message_repo.create.side_effect = echo_create

        result = await service.create_message(
            user_id=user_id,
            message_data=MessageCreate(
                room_id=room_id, content="hello", client_id="client-abc"
            ),
        )

        assert result.seq == 42
        assert result.client_id == "client-abc"
        service.message_repo.next_room_seq.assert_awaited_once_with(room_id)

    @pytest.mark.asyncio
    async def test_create_message_idempotent_fast_path(
        self, message_service_with_mocks
    ):
        """測試相同 client_id 重送時直接回傳既有訊息（不重複建立）"""
        service = message_service_with_mocks
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        _setup_create_mocks(service, room_id, user_id)

        existing = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=user_id,
            username="testuser",
            content="原訊息",
            seq=7,
            client_id="dup-1",
        )
        service.message_repo.get_by_client_id.return_value = existing

        result = await service.create_message(
            user_id=user_id,
            message_data=MessageCreate(
                room_id=room_id, content="原訊息", client_id="dup-1"
            ),
        )

        assert result.id == existing.id
        assert result.seq == 7
        service.message_repo.create.assert_not_awaited()
        service.message_repo.next_room_seq.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_message_idempotent_race(self, message_service_with_mocks):
        """測試併發重送撞唯一索引時回傳既有訊息（原子保底）"""
        service = message_service_with_mocks
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        _setup_create_mocks(service, room_id, user_id)

        existing = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=user_id,
            username="testuser",
            content="原訊息",
            seq=8,
            client_id="race-1",
        )
        # 快速路徑查無（另一請求尚未寫入），create 撞索引後 fallback 查到
        service.message_repo.get_by_client_id.side_effect = [None, existing]
        service.message_repo.next_room_seq.return_value = 9
        service.message_repo.create.side_effect = DuplicateKeyError(
            "E11000 duplicate key"
        )

        result = await service.create_message(
            user_id=user_id,
            message_data=MessageCreate(
                room_id=room_id, content="原訊息", client_id="race-1"
            ),
        )

        assert result.id == existing.id
        assert result.seq == 8


def _make_msg_indb(room_id: str, seq: int, content: str = "msg") -> MessageInDB:
    """建立測試用 MessageInDB"""
    return MessageInDB(
        id=str(ObjectId()),
        room_id=room_id,
        user_id="test_user_id",
        username="testuser",
        content=content,
        seq=seq,
    )


@pytest.mark.unit
class TestMessageSync:
    """測試斷線 gap 補發與游標分頁"""

    @pytest.mark.asyncio
    async def test_sync_no_gap(self, message_service_with_mocks):
        """測試無 gap 時回傳空列表"""
        service = message_service_with_mocks
        service.message_repo.count_after_seq.return_value = 0

        messages, full_reload = await service.sync_messages_since("room-1", 10)

        assert messages == []
        assert full_reload is False
        service.message_repo.get_after_seq.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_sync_small_gap(self, message_service_with_mocks):
        """測試 gap 在上限內時精確補發"""
        service = message_service_with_mocks
        service.message_repo.count_after_seq.return_value = 3
        service.message_repo.get_after_seq.return_value = [
            _make_msg_indb("room-1", seq) for seq in (11, 12, 13)
        ]

        messages, full_reload = await service.sync_messages_since("room-1", 10)

        assert full_reload is False
        assert [m.seq for m in messages] == [11, 12, 13]
        service.message_repo.get_after_seq.assert_awaited_once_with(
            "room-1", 10, limit=200
        )

    @pytest.mark.asyncio
    async def test_sync_large_gap_full_reload(self, message_service_with_mocks):
        """測試 gap 超過上限時改為全量重載"""
        service = message_service_with_mocks
        service.message_repo.count_after_seq.return_value = 500
        service.message_repo.get_room_messages.return_value = [
            _make_msg_indb("room-1", seq) for seq in range(451, 501)
        ]

        messages, full_reload = await service.sync_messages_since("room-1", 10)

        assert full_reload is True
        assert len(messages) == 50
        # 全量重載走 get_room_messages（最新 50 條），不走 get_after_seq
        service.message_repo.get_after_seq.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_room_messages_with_cursor(self, message_service_with_mocks):
        """測試游標分頁參數透傳至 repository"""
        service = message_service_with_mocks
        service.message_repo.get_room_messages.return_value = []

        await service.get_room_messages("room-1", limit=50, before_seq=42)

        service.message_repo.get_room_messages.assert_awaited_once_with(
            room_id="room-1",
            skip=0,
            limit=50,
            message_type=None,
            user_id=None,
            before_seq=42,
        )


@pytest.mark.unit
class TestMessageBroadcast:
    """測試編輯/刪除訊息的 WS 廣播"""

    @pytest.fixture
    def service_with_cm(
        self, mock_message_repository, mock_room_repository, mock_user_repository
    ):
        """帶 mock connection_manager 的訊息服務"""
        cm = AsyncMock()
        service = MessageService(
            mock_message_repository,
            mock_room_repository,
            mock_user_repository,
            connection_manager=cm,
        )
        return service, cm

    @pytest.mark.asyncio
    async def test_update_message_broadcasts_edit(self, service_with_cm):
        """測試更新訊息後廣播 message_edited 事件"""
        service, cm = service_with_cm
        room_id = "test_room_id"
        user_id = "test_user_id"
        message_id = str(ObjectId())

        original = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        updated = original.model_copy(
            update={"content": "更新後的訊息", "edited": True}
        )

        service.message_repo.get_by_id.return_value = original
        service.message_repo.update.return_value = updated

        await service.update_message(
            message_id=message_id,
            user_id=user_id,
            update_data=MessageUpdate(content="更新後的訊息"),
        )

        cm.broadcast_to_room.assert_awaited_once()
        call_args = cm.broadcast_to_room.await_args
        assert call_args.args[0] == room_id
        event = call_args.args[1]
        assert event["type"] == "message_edited"
        assert event["room_id"] == room_id
        assert event["message"]["id"] == message_id
        assert event["message"]["content"] == "更新後的訊息"
        assert event["message"]["edited"] is True

    @pytest.mark.asyncio
    async def test_delete_message_broadcasts(self, service_with_cm):
        """測試刪除訊息後廣播 message_deleted 事件"""
        service, cm = service_with_cm
        room_id = "test_room_id"
        user_id = "test_user_id"
        message_id = str(ObjectId())

        original = MessageResponse(
            id=message_id,
            content="原始訊息",
            message_type=MessageType.TEXT,
            user_id=user_id,
            room_id=room_id,
            username="testuser",
            status=MessageStatus.SENT,
            edited=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        service.message_repo.get_by_id.return_value = original
        service.message_repo.delete.return_value = True

        await service.delete_message(message_id=message_id, user_id=user_id)

        cm.broadcast_to_room.assert_awaited_once()
        call_args = cm.broadcast_to_room.await_args
        assert call_args.args[0] == room_id
        event = call_args.args[1]
        assert event["type"] == "message_deleted"
        assert event["message_id"] == message_id
