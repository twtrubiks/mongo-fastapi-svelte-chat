"""
測試房間服務層
使用 Mock 優先的方式測試所有功能
"""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import bcrypt
import pytest
from bson import ObjectId

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.models.enums import JoinPolicy, MemberRole, RoomType
from app.models.room import (
    RoomCreate,
    RoomInDB,
    RoomJoinRequest,
    RoomResponse,
    RoomUpdate,
)
from app.services.room_service import RoomService


class TestRoomService:
    """測試房間服務"""

    @pytest.fixture
    def mock_repositories(self):
        """Mock 所有倉儲"""
        room_repo = AsyncMock()
        user_repo = AsyncMock()
        message_repo = AsyncMock()
        return room_repo, user_repo, message_repo

    @pytest.fixture
    def mock_connection_manager(self):
        """Mock ConnectionManager — 補齊真實 ConnectionManager.__init__ 的 dict/set 屬���"""
        cm = AsyncMock()
        cm.user_info = {}
        cm.active_connections = {}
        cm.room_users = {}
        cm.global_online_users = set()
        return cm

    @pytest.fixture
    def room_service(self, mock_repositories, mock_connection_manager):
        """創建房間服務實例"""
        room_repo, user_repo, message_repo = mock_repositories
        return RoomService(
            room_repo,
            user_repo,
            message_repo,
            connection_manager=mock_connection_manager,
        )

    @pytest.fixture
    def sample_room(self):
        """創建測試用房間"""
        return RoomInDB(
            id=str(ObjectId()),
            name="Test Room",
            description="Test Description",
            is_public=True,
            room_type=RoomType.PUBLIC,
            join_policy=JoinPolicy.DIRECT,
            max_members=100,
            owner_id=str(ObjectId()),
            owner_name="testowner",
            members=[str(ObjectId())],
            member_roles={},
            password_hash=None,
            invite_code=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @pytest.mark.asyncio
    async def test_convert_to_response(self, room_service, sample_room):
        """測試轉換房間為響應格式"""
        # 測試正常轉換
        response = await room_service._convert_to_response(sample_room)

        assert isinstance(response, RoomResponse)
        assert response.id == sample_room.id
        assert response.name == sample_room.name
        assert response.member_count == len(sample_room.members)
        assert response.has_password is False

        # 測試有密碼的房間
        sample_room.password_hash = "hashed_password"
        response = await room_service._convert_to_response(sample_room)
        assert response.has_password is True

    @pytest.mark.asyncio
    async def test_create_room_user_not_found(self, room_service, mock_repositories):
        """測試用戶不存在時創建房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 用戶不存在
        user_repo.get_by_id.return_value = None

        # 執行並驗證拋出異常
        with pytest.raises(NotFoundError) as exc_info:
            await room_service.create_room("invalid_user", RoomCreate(name="Test"))

        assert "用戶不存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_room_duplicate_name(self, room_service, mock_repositories):
        """測試房間名稱重複"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 設置
        user_id = str(ObjectId())
        user_repo.get_by_id.return_value = Mock(id=user_id, username="testuser")
        room_repo.get_by_name.return_value = Mock()  # 房間已存在

        # 執行並驗證拋出異常
        with pytest.raises(ConflictError) as exc_info:
            await room_service.create_room(user_id, RoomCreate(name="Existing"))

        assert "房間名稱已存在" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_room_by_id(self, room_service, mock_repositories, sample_room):
        """測試根據 ID 獲取房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 返回房間
        room_repo.get_by_id.return_value = sample_room

        # 執行
        result = await room_service.get_room_by_id(sample_room.id)

        # 驗證
        assert result is not None
        assert result.id == sample_room.id
        assert result.member_count == len(sample_room.members)

    @pytest.mark.asyncio
    async def test_get_room_by_id_not_found(self, room_service, mock_repositories):
        """測試獲取不存在的房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 房間不存在
        room_repo.get_by_id.return_value = None

        # 執行並驗證拋出異常
        with pytest.raises(NotFoundError):
            await room_service.get_room_by_id("invalid_id")

    @pytest.mark.asyncio
    async def test_get_rooms_public(self, room_service, mock_repositories, sample_room):
        """測試獲取公開房間列表"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 房間列表
        mock_rooms = [sample_room]
        room_repo.get_public_rooms.return_value = mock_rooms

        # 執行
        result = await room_service.get_rooms(skip=0, limit=10)

        # 驗證
        assert len(result) == 1
        room_repo.get_public_rooms.assert_called_once_with(0, 10)

    @pytest.mark.asyncio
    async def test_get_rooms_with_search(
        self, room_service, mock_repositories, sample_room
    ):
        """測試搜尋房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 搜尋結果
        sample_room.name = "Search Result"
        mock_rooms = [sample_room]
        room_repo.search_rooms.return_value = mock_rooms

        # 執行
        result = await room_service.get_rooms(search="test")

        # 驗證
        assert len(result) == 1
        room_repo.search_rooms.assert_called_once_with(
            "test", 0, 20, True, exclude_user_id=None
        )

    @pytest.mark.asyncio
    async def test_get_rooms_with_user_id(
        self, room_service, mock_repositories, sample_room
    ):
        """測試帶 user_id 獲取房間列表（走 get_rooms_for_user 路徑）"""
        room_repo, user_repo, message_repo = mock_repositories

        mock_rooms = [sample_room]
        room_repo.get_rooms_for_user.return_value = mock_rooms

        user_id = str(ObjectId())
        result = await room_service.get_rooms(skip=0, limit=10, user_id=user_id)

        # 驗證走了正確的 repository 路徑
        room_repo.get_rooms_for_user.assert_called_once_with(user_id, 0, 10)
        room_repo.get_public_rooms.assert_not_called()
        room_repo.search_rooms.assert_not_called()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_rooms_is_member_flag(self, room_service, mock_repositories):
        """測試 get_rooms 回傳的 is_member 標記正確"""
        room_repo, user_repo, message_repo = mock_repositories

        user_id = str(ObjectId())
        other_id = str(ObjectId())

        # Mock owner 查詢（_prepare_room_data 會補填 owner_name）
        user_repo.get_by_id.return_value = Mock(username="owner")

        # 使用者是成員的房間
        joined_room = RoomInDB(
            id=str(ObjectId()),
            name="Joined Room",
            description="",
            is_public=True,
            room_type=RoomType.PUBLIC,
            join_policy=JoinPolicy.DIRECT,
            max_members=100,
            owner_id=other_id,
            members=[other_id, user_id],
            member_roles={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 使用者不是成員的房間
        not_joined_room = RoomInDB(
            id=str(ObjectId()),
            name="Not Joined Room",
            description="",
            is_public=True,
            room_type=RoomType.PUBLIC,
            join_policy=JoinPolicy.DIRECT,
            max_members=100,
            owner_id=other_id,
            members=[other_id],
            member_roles={},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        room_repo.get_rooms_for_user.return_value = [joined_room, not_joined_room]

        result = await room_service.get_rooms(user_id=user_id)

        joined = next(r for r in result if r.name == "Joined Room")
        not_joined = next(r for r in result if r.name == "Not Joined Room")
        assert joined.is_member is True
        assert not_joined.is_member is False

    @pytest.mark.asyncio
    async def test_get_rooms_search_with_user_id(
        self, room_service, mock_repositories, sample_room
    ):
        """測試搜尋時有 user_id 仍走 search_rooms 路徑"""
        room_repo, user_repo, message_repo = mock_repositories

        room_repo.search_rooms.return_value = [sample_room]

        user_id = str(ObjectId())
        result = await room_service.get_rooms(
            search="test", user_id=user_id, skip=0, limit=10
        )

        # 有 search 時不管有沒有 user_id 都走 search_rooms（exclude_joined 預設 False）
        room_repo.search_rooms.assert_called_once_with(
            "test", 0, 10, True, exclude_user_id=None
        )
        room_repo.get_rooms_for_user.assert_not_called()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_rooms_exclude_joined(
        self, room_service, mock_repositories, sample_room
    ):
        """測試 exclude_joined=True 走 get_explore_rooms 路徑"""
        room_repo, user_repo, message_repo = mock_repositories

        room_repo.get_explore_rooms.return_value = [sample_room]

        user_id = str(ObjectId())
        result = await room_service.get_rooms(
            skip=0, limit=10, user_id=user_id, exclude_joined=True
        )

        room_repo.get_explore_rooms.assert_called_once_with(user_id, 0, 10)
        room_repo.get_rooms_for_user.assert_not_called()
        room_repo.get_public_rooms.assert_not_called()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_rooms_search_exclude_joined(
        self, room_service, mock_repositories, sample_room
    ):
        """測試搜尋 + exclude_joined=True 會傳 exclude_user_id"""
        room_repo, user_repo, message_repo = mock_repositories

        room_repo.search_rooms.return_value = [sample_room]

        user_id = str(ObjectId())
        result = await room_service.get_rooms(
            search="test", user_id=user_id, exclude_joined=True, skip=0, limit=10
        )

        room_repo.search_rooms.assert_called_once_with(
            "test", 0, 10, True, exclude_user_id=user_id
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_join_room_direct(self, room_service, mock_repositories, sample_room):
        """測試直接加入房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置房間為直接加入
        sample_room.join_policy = JoinPolicy.DIRECT
        sample_room.members = []
        room_repo.get_by_id.return_value = sample_room
        room_repo.add_member.return_value = True

        # 執行
        user_id = str(ObjectId())
        result = await room_service.join_room(sample_room.id, user_id)

        # 驗證
        assert "成功加入" in result
        room_repo.add_member.assert_called_once_with(
            sample_room.id, user_id, MemberRole.MEMBER
        )

    @pytest.mark.asyncio
    async def test_join_room_with_password(
        self, room_service, mock_repositories, sample_room
    ):
        """測試使用密碼加入房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置房間需要密碼
        sample_room.join_policy = JoinPolicy.PASSWORD
        sample_room.password_hash = bcrypt.hashpw(b"test123", bcrypt.gensalt()).decode(
            "utf-8"
        )
        sample_room.members = []
        room_repo.get_by_id.return_value = sample_room
        room_repo.add_member.return_value = True

        # 執行 - 正確密碼
        user_id = str(ObjectId())
        join_request = RoomJoinRequest(password="test123")
        result = await room_service.join_room(sample_room.id, user_id, join_request)

        # 驗證
        assert "成功加入" in result

        # 測試錯誤密碼
        join_request = RoomJoinRequest(password="wrong_password")
        with pytest.raises(AppError) as exc_info:
            await room_service.join_room(sample_room.id, user_id, join_request)
        assert "密碼錯誤" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_join_room_already_member(
        self, room_service, mock_repositories, sample_room
    ):
        """測試已是成員時加入房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置用戶已是成員
        user_id = str(ObjectId())
        sample_room.members = [user_id]
        room_repo.get_by_id.return_value = sample_room

        # 執行
        result = await room_service.join_room(sample_room.id, user_id)

        # 驗證
        assert "已經是該房間的成員" in result

    @pytest.mark.asyncio
    async def test_join_room_full(self, room_service, mock_repositories, sample_room):
        """測試房間已滿時加入"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置房間已滿
        sample_room.max_members = 1
        sample_room.members = [str(ObjectId())]
        room_repo.get_by_id.return_value = sample_room

        # 執行並驗證拋出異常
        with pytest.raises(AppError) as exc_info:
            await room_service.join_room(sample_room.id, str(ObjectId()))
        assert "房間已滿" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_leave_room_success(
        self, room_service, mock_repositories, sample_room
    ):
        """測試成功離開房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置用戶為成員（非擁有者）
        user_id = str(ObjectId())
        sample_room.members = [sample_room.owner_id, user_id]
        room_repo.get_by_id.return_value = sample_room
        room_repo.remove_member.return_value = True

        # 執行
        result = await room_service.leave_room(sample_room.id, user_id)

        # 驗證
        assert "成功離開" in result
        room_repo.remove_member.assert_called_once_with(sample_room.id, user_id)

    @pytest.mark.asyncio
    async def test_leave_room_force_disconnects_ws(
        self, room_service, mock_repositories, mock_connection_manager, sample_room
    ):
        """測試離開房間時撤銷該使用者在該房的 WS 連線（讀取權撤銷）"""
        room_repo, user_repo, message_repo = mock_repositories

        user_id = str(ObjectId())
        sample_room.members = [sample_room.owner_id, user_id]
        room_repo.get_by_id.return_value = sample_room
        room_repo.remove_member.return_value = True

        await room_service.leave_room(sample_room.id, user_id)

        # 離開後必須強制斷開 WS，否則已開分頁會繼續收到房間廣播
        mock_connection_manager.force_disconnect.assert_called_once_with(
            user_id, sample_room.id
        )

    @pytest.mark.asyncio
    async def test_leave_room_as_owner(
        self, room_service, mock_repositories, sample_room
    ):
        """測試擁有者離開房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置用戶為擁有者
        room_repo.get_by_id.return_value = sample_room

        # 執行並驗證拋出異常
        with pytest.raises(ForbiddenError) as exc_info:
            await room_service.leave_room(sample_room.id, sample_room.owner_id)
        assert "房間擁有者不能離開房間" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_room_success(
        self, room_service, mock_repositories, mock_connection_manager, sample_room
    ):
        """測試成功刪除房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 設置
        room_repo.get_by_id.return_value = sample_room
        room_repo.delete.return_value = True
        message_repo.delete_by_room_id.return_value = True

        # 設定 connection_manager mock
        mock_connection_manager.active_connections = {"user1": {}, "user2": {}}
        mock_connection_manager.send_event = AsyncMock()

        # 執行
        await room_service.delete_room(sample_room.id, sample_room.owner_id)

        # 驗證
        room_repo.delete.assert_called_once_with(sample_room.id)
        message_repo.delete_by_room_id.assert_called_once_with(sample_room.id)

        # 驗證 WebSocket 通知被發送
        assert mock_connection_manager.send_event.called

        # 驗證撤銷該房所有 WS 連線（連線不應殘留在廣播名單中）
        mock_connection_manager.force_disconnect_room.assert_called_once_with(
            sample_room.id
        )

    @pytest.mark.asyncio
    async def test_delete_room_not_owner(
        self, room_service, mock_repositories, sample_room
    ):
        """測試非擁有者刪除房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 設置
        room_repo.get_by_id.return_value = sample_room

        # 執行並驗證拋出異常
        with pytest.raises(ForbiddenError) as exc_info:
            await room_service.delete_room(sample_room.id, str(ObjectId()))
        assert "只有房間擁有者可以刪除房間" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_room_success(
        self, room_service, mock_repositories, sample_room
    ):
        """測試成功更新房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # Mock 設置
        room_repo.get_by_id.return_value = sample_room
        # Service 層名稱唯一性檢查：無衝突
        room_repo.get_by_name.return_value = None
        # 創建更新後的房間
        updated_data = sample_room.model_dump()
        updated_data["name"] = "Updated Name"
        updated_room = RoomInDB(**updated_data)
        room_repo.update.return_value = updated_room

        # 更新數據
        update_data = RoomUpdate(name="Updated Name")

        # 執行
        result = await room_service.update_room(
            sample_room.id, sample_room.owner_id, update_data
        )

        # 驗證
        assert result is not None
        assert result.name == "Updated Name"
        room_repo.update.assert_called_once_with(
            sample_room.id, update_data, password_hash=None
        )

    @pytest.mark.asyncio
    async def test_update_room_max_members_validation(
        self, room_service, mock_repositories, sample_room
    ):
        """測試更新最大成員數驗證"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置當前有 5 個成員
        sample_room.members = [str(ObjectId()) for _ in range(5)]
        room_repo.get_by_id.return_value = sample_room

        # 嘗試設置最大成員數為 3
        update_data = RoomUpdate(max_members=3)

        # 執行並驗證拋出異常
        with pytest.raises(AppError) as exc_info:
            await room_service.update_room(
                sample_room.id, sample_room.owner_id, update_data
            )
        assert "最大成員數不能小於當前成員數" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_broadcast_room_event(
        self, room_service, mock_repositories, mock_connection_manager
    ):
        """測試廣播房間事件"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設定注入的 connection_manager mock
        mock_connection_manager.active_connections = {
            "user1": {},
            "user2": {},
            "creator": {},
        }
        mock_connection_manager.send_event = AsyncMock()

        message = {"type": "room_created", "room": {"id": "room123", "name": "Test"}}

        # 執行 - 排除 creator
        await room_service._broadcast_room_event(message, exclude_user_id="creator")

        # 驗證 - 應該發送給除了 creator 之外的所有用戶
        assert mock_connection_manager.send_event.call_count == 2

    @pytest.mark.asyncio
    async def test_join_room_with_invite_code(
        self, room_service, mock_repositories, sample_room
    ):
        """測試使用邀請碼加入房間"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置房間需要邀請碼
        sample_room.join_policy = JoinPolicy.INVITE
        sample_room.invite_code = "test-invite-code"
        sample_room.members = []
        room_repo.get_by_id.return_value = sample_room
        room_repo.add_member.return_value = True

        # 正確的邀請碼
        user_id = str(ObjectId())
        join_request = RoomJoinRequest(invite_code="test-invite-code")
        result = await room_service.join_room(sample_room.id, user_id, join_request)

        # 驗證
        assert "成功加入" in result

        # 錯誤的邀請碼
        join_request = RoomJoinRequest(invite_code="wrong-code")
        with pytest.raises(AppError) as exc_info:
            await room_service.join_room(sample_room.id, user_id, join_request)
        assert "邀請碼無效" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_invite_code(
        self, room_service, mock_repositories, sample_room
    ):
        """測試驗證邀請碼回傳房間資訊"""
        room_repo, user_repo, message_repo = mock_repositories

        sample_room.join_policy = JoinPolicy.INVITE
        sample_room.invite_code = "test-invite-code"
        room_repo.get_by_invite_code.return_value = sample_room
        owner = Mock()
        owner.username = "testowner"
        user_repo.get_by_id.return_value = owner

        result = await room_service.validate_invite_code("test-invite-code")

        assert result == {
            "room_id": sample_room.id,
            "room_name": sample_room.name,
            "inviter_name": "testowner",
        }

    @pytest.mark.asyncio
    async def test_validate_invite_code_not_found(
        self, room_service, mock_repositories
    ):
        """測試無效邀請碼拋出 NotFoundError"""
        room_repo, user_repo, message_repo = mock_repositories
        room_repo.get_by_invite_code.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            await room_service.validate_invite_code("bad-code")
        assert "邀請碼無效" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_invite_code_expired(
        self, room_service, mock_repositories, sample_room
    ):
        """測試過期邀請碼拋出 AppError"""
        room_repo, user_repo, message_repo = mock_repositories

        sample_room.join_policy = JoinPolicy.INVITE
        sample_room.invite_code = "test-invite-code"
        sample_room.invite_code_expires_at = datetime.now(UTC) - timedelta(hours=1)
        room_repo.get_by_invite_code.return_value = sample_room

        with pytest.raises(AppError) as exc_info:
            await room_service.validate_invite_code("test-invite-code")
        assert "已過期" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("offset", "expired"),
        [(timedelta(hours=-1), True), (timedelta(hours=1), False)],
    )
    def test_invite_code_expiry_with_naive_datetime(self, sample_room, offset, expired):
        """MongoDB 讀回的時間不帶時區，比較時不可拋 TypeError"""
        naive_utc_now = datetime.now(UTC).replace(tzinfo=None)
        sample_room.invite_code_expires_at = naive_utc_now + offset

        assert RoomService._invite_code_expired(sample_room) is expired

    def test_invite_code_without_expiry_never_expires(self, sample_room):
        sample_room.invite_code_expires_at = None

        assert RoomService._invite_code_expired(sample_room) is False

    @pytest.mark.asyncio
    async def test_delete_room_with_websocket_notification(
        self, room_service, mock_repositories, mock_connection_manager, sample_room
    ):
        """測試刪除房間時發送 WebSocket 通知"""
        room_repo, user_repo, message_repo = mock_repositories

        # 設置房間有多個成員
        member1_id = str(ObjectId())
        member2_id = str(ObjectId())
        sample_room.members = [sample_room.owner_id, member1_id, member2_id]

        # Mock 設置
        room_repo.get_by_id.return_value = sample_room
        room_repo.delete.return_value = True
        message_repo.delete_by_room_id.return_value = True

        # 設定注入的 connection_manager mock
        other_user1 = str(ObjectId())
        other_user2 = str(ObjectId())
        mock_connection_manager.active_connections = {
            sample_room.owner_id: {},
            member1_id: {},
            member2_id: {},
            other_user1: {},
            other_user2: {},
        }
        mock_connection_manager.send_event = AsyncMock()

        # 執行
        await room_service.delete_room(sample_room.id, sample_room.owner_id)

        # 驗證通知被發送給所有在線用戶（5 個）
        assert mock_connection_manager.send_event.call_count == 5

        expected_message = {
            "type": "room_deleted",
            "room_id": sample_room.id,
            "deleted_by": sample_room.owner_id,
        }

        notified_users = set()
        for call in mock_connection_manager.send_event.call_args_list:
            user_id, message = call[0]
            notified_users.add(user_id)
            assert message == expected_message

        expected_users = {
            sample_room.owner_id,
            member1_id,
            member2_id,
            other_user1,
            other_user2,
        }
        assert notified_users == expected_users

    @pytest.mark.asyncio
    async def test_owner_name_backfilled_for_legacy_room(
        self, room_service, mock_repositories, sample_room
    ):
        """缺 owner_name 的舊房間以擁有者的 username 補填；擁有者已不存在則維持 None"""
        room_repo, user_repo, message_repo = mock_repositories
        sample_room.owner_name = None
        room_repo.get_by_id.return_value = sample_room

        owner = Mock()
        owner.username = "legacy-owner"
        user_repo.get_by_id.return_value = owner
        backfilled = await room_service.get_room_by_id(sample_room.id)

        user_repo.get_by_id.return_value = None
        orphaned = await room_service.get_room_by_id(sample_room.id)

        user_repo.get_by_id.assert_awaited_with(sample_room.owner_id)
        assert backfilled.owner_name == "legacy-owner"
        assert orphaned.owner_name is None

    @pytest.mark.asyncio
    async def test_create_room_broadcasts_summary_to_others(
        self, room_service, mock_repositories, mock_connection_manager
    ):
        """公開房間的 room_created 只送給其他在線者，內容為摘要（不含邀請碼）與建立者 ID"""
        room_repo, user_repo, message_repo = mock_repositories
        owner_id, other_id = str(ObjectId()), str(ObjectId())
        creator = Mock()
        creator.username = "creator"
        user_repo.get_by_id.return_value = creator
        room_repo.get_by_name.return_value = None
        room_repo.create.side_effect = lambda room: room.model_copy(
            update={"id": str(ObjectId())}
        )
        mock_connection_manager.active_connections = {owner_id: {}, other_id: {}}
        mock_connection_manager.send_event = AsyncMock()

        response = await room_service.create_room(
            owner_id, RoomCreate(name="New Room", join_policy=JoinPolicy.INVITE)
        )

        [(recipient, event)] = [
            call.args for call in mock_connection_manager.send_event.await_args_list
        ]
        room = event.pop("room")
        assert recipient == other_id
        assert event == {"type": "room_created", "creator_id": owner_id}
        assert response.invite_code
        assert room["id"] == response.id
        assert room["name"] == "New Room"
        assert "invite_code" not in room

    @pytest.mark.asyncio
    async def test_leave_room_broadcasts_user_left(
        self, room_service, mock_repositories, mock_connection_manager, sample_room
    ):
        room_repo, user_repo, message_repo = mock_repositories
        user_id = str(ObjectId())
        sample_room.members = [sample_room.owner_id, user_id]
        room_repo.get_by_id.return_value = sample_room
        room_repo.remove_member.return_value = True
        mock_connection_manager.user_info = {
            user_id: {"id": user_id, "username": "leaver"}
        }

        await room_service.leave_room(sample_room.id, user_id)

        mock_connection_manager.broadcast_to_room.assert_awaited_once()
        room_id, event = mock_connection_manager.broadcast_to_room.await_args.args
        sent_at = datetime.fromisoformat(event.pop("timestamp"))
        assert room_id == sample_room.id
        assert event == {
            "type": "user_left",
            "user": {"id": user_id, "username": "leaver"},
            "room_id": sample_room.id,
            "removed": True,
        }
        assert abs(datetime.now(UTC) - sent_at) < timedelta(seconds=5)

    @pytest.mark.asyncio
    async def test_get_members_of_missing_room_is_empty_list(
        self, room_service, mock_repositories
    ):
        room_repo, user_repo, message_repo = mock_repositories
        room_repo.get_by_id.return_value = None

        assert await room_service.get_room_members(str(ObjectId())) == []

    @pytest.mark.asyncio
    async def test_broadcast_logs_each_failed_recipient_only(
        self, room_service, mock_connection_manager, caplog
    ):
        """成功送達不記錯誤；每位送達失敗的收件者各記一筆錯誤，其餘收件者照常送出"""
        failures = {
            "broken-1": RuntimeError("socket-1 gone"),
            "broken-2": RuntimeError("socket-2 gone"),
        }

        async def send_event(user_id, message):
            if user_id in failures:
                raise failures[user_id]

        mock_connection_manager.active_connections = {
            "ok-1": {},
            "broken-1": {},
            "ok-2": {},
            "broken-2": {},
        }
        mock_connection_manager.send_event = AsyncMock(side_effect=send_event)
        caplog.set_level(logging.ERROR, logger="app.services.room_service")

        await room_service._broadcast_room_event({"type": "room_updated"})

        errors = [
            r.getMessage()
            for r in caplog.records
            if r.name == "app.services.room_service" and r.levelno >= logging.ERROR
        ]
        assert mock_connection_manager.send_event.await_count == 4
        assert len(errors) == 2
        assert any("socket-1 gone" in e for e in errors)
        assert any("socket-2 gone" in e for e in errors)
