"""RoomService 和 MessageService 整合測試"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.models.message import MessageCreate, MessageInDB, MessageType
from app.models.room import RoomCreate, RoomInDB
from app.models.user import UserInDB
from app.services.message_service import MessageService
from app.services.room_service import RoomService


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.unit
class TestRoomMessageIntegration:
    """RoomService 和 MessageService 整合測試類別"""

    @pytest.fixture
    def room_service_with_mocks(
        self, mock_room_repository, mock_user_repository, mock_message_repository
    ):
        """配置 RoomService 和相關依賴"""
        return RoomService(
            room_repository=mock_room_repository,
            user_repository=mock_user_repository,
            message_repository=mock_message_repository,
        )

    @pytest.fixture
    def message_service_with_mocks(self, mock_message_repository, mock_room_repository):
        """配置 MessageService 和相關依賴"""
        return MessageService(
            message_repository=mock_message_repository,
            room_repository=mock_room_repository,
        )

    @pytest.fixture
    def integration_services(self, room_service_with_mocks, message_service_with_mocks):
        """整合測試的服務組合"""
        return {
            "room_service": room_service_with_mocks,
            "message_service": message_service_with_mocks,
        }

    @pytest.mark.asyncio
    async def test_create_room_and_send_welcome_message(
        self,
        integration_services,
        mock_room_repository,
        mock_user_repository,
        mock_message_repository,
    ):
        """測試創建房間後發送歡迎消息的整合流程"""
        room_service = integration_services["room_service"]
        message_service = integration_services["message_service"]

        # 準備測試數據
        owner_id = str(ObjectId())
        room_id = str(ObjectId())

        # 配置用戶 mock
        owner_user = UserInDB(
            id=owner_id,
            username="room_owner",
            email="owner@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置房間創建 mock
        room_create = RoomCreate(
            name="測試房間", description="這是一個測試房間", is_public=True
        )

        created_room = RoomInDB(
            id=room_id,
            name="測試房間",
            description="這是一個測試房間",
            is_public=True,
            owner_id=owner_id,
            members=[owner_id],
            member_roles={owner_id: "owner"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置歡迎消息 mock
        welcome_message = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=owner_id,
            username="room_owner",
            content="歡迎來到房間！",
            message_type=MessageType.SYSTEM,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置 mocks
        mock_user_repository.get_by_id.return_value = owner_user
        mock_room_repository.get_by_name.return_value = None  # 房間名稱不存在
        mock_room_repository.create.return_value = created_room
        mock_room_repository.get_by_id.return_value = created_room
        mock_room_repository.is_member.return_value = True
        mock_message_repository.create.return_value = welcome_message

        # 執行整合流程
        # 1. 創建房間
        with patch("app.websocket.manager.connection_manager") as mock_conn_mgr:
            mock_conn_mgr.active_connections = {}
            mock_conn_mgr.send_notification = AsyncMock()
            result_room = await room_service.create_room(owner_id, room_create)
        assert result_room is not None
        assert result_room.name == "測試房間"
        assert result_room.owner_id == owner_id

        # 2. 發送歡迎消息
        message_create = MessageCreate(
            room_id=room_id, content="歡迎來到房間！", message_type=MessageType.SYSTEM
        )

        # Mock UserRepository 用於 MessageService
        with patch(
            "app.repositories.user_repository.UserRepository"
        ) as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=owner_user)

            welcome_result = await message_service.create_message(
                user_id=owner_id, message_data=message_create
            )

        # 驗證整合結果
        assert welcome_result is not None
        assert welcome_result.content == "歡迎來到房間！"
        assert welcome_result.room_id == room_id
        assert welcome_result.user_id == owner_id

        # 驗證服務調用
        mock_room_repository.create.assert_called_once()
        mock_message_repository.create.assert_called_once()
        mock_room_repository.is_member.assert_called_once_with(room_id, owner_id)

    @pytest.mark.asyncio
    async def test_join_room_and_send_join_message(
        self,
        integration_services,
        mock_room_repository,
        mock_user_repository,
        mock_message_repository,
    ):
        """測試加入房間後發送加入消息的整合流程"""
        room_service = integration_services["room_service"]
        message_service = integration_services["message_service"]

        # 準備測試數據
        room_id = str(ObjectId())
        owner_id = str(ObjectId())
        new_user_id = str(ObjectId())

        # 配置用戶 mock
        new_user = UserInDB(
            id=new_user_id,
            username="new_member",
            email="new@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置房間 mock
        room_before_join = RoomInDB(
            id=room_id,
            name="測試房間",
            description="這是一個測試房間",
            is_public=True,
            owner_id=owner_id,
            members=[owner_id],
            member_roles={owner_id: "owner"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        room_after_join = RoomInDB(
            id=room_id,
            name="測試房間",
            description="這是一個測試房間",
            is_public=True,
            owner_id=owner_id,
            members=[owner_id, new_user_id],
            member_roles={owner_id: "owner", new_user_id: "member"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置加入消息 mock
        join_message = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=new_user_id,
            username="new_member",
            content="new_member 加入了房間",
            message_type=MessageType.SYSTEM,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置 mocks
        mock_user_repository.get_by_id.return_value = new_user
        mock_room_repository.get_by_id.return_value = room_before_join
        mock_room_repository.add_member.return_value = room_after_join
        mock_room_repository.is_member.return_value = True
        mock_message_repository.create.return_value = join_message

        # 執行整合流程
        # 1. 加入房間
        result = await room_service.join_room(room_id, new_user_id)
        assert result is not None
        assert result["success"] is True

        # 2. 發送加入消息
        message_create = MessageCreate(
            room_id=room_id,
            content="new_member 加入了房間",
            message_type=MessageType.SYSTEM,
        )

        # Mock UserRepository 用於 MessageService
        with patch(
            "app.repositories.user_repository.UserRepository"
        ) as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=new_user)

            join_result = await message_service.create_message(
                user_id=new_user_id, message_data=message_create
            )

        # 驗證整合結果
        assert join_result is not None
        assert join_result.content == "new_member 加入了房間"
        assert join_result.room_id == room_id
        assert join_result.user_id == new_user_id

        # 驗證服務調用
        mock_room_repository.add_member.assert_called_once_with(room_id, new_user_id)
        mock_message_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_room_with_message_cleanup(
        self,
        integration_services,
        mock_room_repository,
        mock_user_repository,
        mock_message_repository,
    ):
        """測試刪除房間時清理消息的整合流程"""
        room_service = integration_services["room_service"]
        _message_service = integration_services["message_service"]  # 預留供未來整合測試

        # 準備測試數據
        room_id = str(ObjectId())
        owner_id = str(ObjectId())

        # 配置房間 mock
        room_to_delete = RoomInDB(
            id=room_id,
            name="待刪除房間",
            description="這個房間將被刪除",
            is_public=True,
            owner_id=owner_id,
            members=[owner_id],
            member_roles={owner_id: "owner"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置 mocks
        mock_room_repository.get_by_id.return_value = room_to_delete
        mock_room_repository.delete.return_value = True

        # 添加缺少的 mock 方法（RoomService 實際調用的是 delete_by_room_id）
        mock_message_repository.delete_by_room_id = AsyncMock(
            return_value=15
        )  # 刪除了15條消息

        # 執行整合流程
        # 1. 刪除房間
        delete_result = await room_service.delete_room(room_id, owner_id)
        assert delete_result is True

        # 2. 驗證消息清理（RoomService 內部已調用）
        mock_message_repository.delete_by_room_id.assert_called_once_with(room_id)

        # 驗證服務調用
        mock_room_repository.delete.assert_called_once_with(room_id)

    @pytest.mark.asyncio
    async def test_send_message_with_room_validation(
        self,
        integration_services,
        mock_room_repository,
        mock_user_repository,
        mock_message_repository,
    ):
        """測試發送消息時的房間驗證整合流程"""
        room_service = integration_services["room_service"]
        message_service = integration_services["message_service"]

        # 準備測試數據
        room_id = str(ObjectId())
        owner_id = str(ObjectId())
        user_id = str(ObjectId())

        # 配置房間 mock
        room = RoomInDB(
            id=room_id,
            name="測試房間",
            description="這是一個測試房間",
            is_public=True,
            owner_id=owner_id,
            members=[owner_id, user_id],
            member_roles={owner_id: "owner", user_id: "member"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置用戶 mock
        user = UserInDB(
            id=user_id,
            username="test_user",
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置消息 mock
        message = MessageInDB(
            id=str(ObjectId()),
            room_id=room_id,
            user_id=user_id,
            username="test_user",
            content="Hello, world!",
            message_type=MessageType.TEXT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置 mocks
        mock_room_repository.get_by_id.return_value = room
        mock_room_repository.is_member.return_value = True
        mock_user_repository.get_by_id.return_value = user
        mock_message_repository.create.return_value = message

        # 執行整合流程
        # 1. 驗證房間存在（MessageService 內部驗證）
        room_result = await room_service.get_room_by_id(room_id)
        assert room_result is not None
        assert room_result.id == room_id

        # 2. 發送消息
        message_create = MessageCreate(
            room_id=room_id, content="Hello, world!", message_type=MessageType.TEXT
        )

        # Mock UserRepository 用於 MessageService
        with patch(
            "app.repositories.user_repository.UserRepository"
        ) as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=user)

            message_result = await message_service.create_message(
                user_id=user_id, message_data=message_create
            )

        # 驗證整合結果
        assert message_result is not None
        assert message_result.content == "Hello, world!"
        assert message_result.room_id == room_id
        assert message_result.user_id == user_id

        # 驗證服務調用
        mock_room_repository.get_by_id.assert_called()
        mock_room_repository.is_member.assert_called_once_with(room_id, user_id)
        mock_message_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_room_member_validation_for_message_sending(
        self,
        integration_services,
        mock_room_repository,
        mock_user_repository,
        mock_message_repository,
    ):
        """測試非成員發送消息時的驗證流程"""
        room_service = integration_services["room_service"]
        message_service = integration_services["message_service"]

        # 準備測試數據
        room_id = str(ObjectId())
        owner_id = str(ObjectId())
        non_member_id = str(ObjectId())

        # 配置房間 mock
        room = RoomInDB(
            id=room_id,
            name="私人房間",
            description="這是一個私人房間",
            is_public=False,
            owner_id=owner_id,
            members=[owner_id],  # 不包含 non_member_id
            member_roles={owner_id: "owner"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置用戶 mock
        non_member = UserInDB(
            id=non_member_id,
            username="non_member",
            email="non@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置 mocks
        mock_room_repository.get_by_id.return_value = room
        mock_room_repository.is_member.return_value = False  # 非成員
        mock_user_repository.get_by_id.return_value = non_member

        # 執行整合流程
        # 1. 驗證房間存在
        room_result = await room_service.get_room_by_id(room_id)
        assert room_result is not None
        assert non_member_id not in room_result.members

        # 2. 嘗試發送消息（應該失敗）
        message_create = MessageCreate(
            room_id=room_id, content="我不是成員", message_type=MessageType.TEXT
        )

        # Mock UserRepository 用於 MessageService
        with patch(
            "app.repositories.user_repository.UserRepository"
        ) as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=non_member)

            # 嘗試發送消息應該拋出異常
            message_result = None
            try:
                message_result = await message_service.create_message(
                    user_id=non_member_id, message_data=message_create
                )
            except ValueError as e:
                # 預期的錯誤
                assert "使用者不是該房間的成員" in str(e)

        # 驗證整合結果
        assert message_result is None  # 消息創建失敗

        # 驗證服務調用
        mock_room_repository.is_member.assert_called_once_with(room_id, non_member_id)
        mock_message_repository.create.assert_not_called()  # 未調用創建消息

    @pytest.mark.asyncio
    async def test_get_room_messages_integration(
        self, integration_services, mock_room_repository, mock_message_repository
    ):
        """測試獲取房間消息的整合流程"""
        room_service = integration_services["room_service"]
        message_service = integration_services["message_service"]

        # 準備測試數據
        room_id = str(ObjectId())
        owner_id = str(ObjectId())

        # 配置房間 mock
        room = RoomInDB(
            id=room_id,
            name="消息房間",
            description="包含多條消息的房間",
            is_public=True,
            owner_id=owner_id,
            members=[owner_id],
            member_roles={owner_id: "owner"},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 配置消息列表 mock
        messages = [
            MessageInDB(
                id=str(ObjectId()),
                room_id=room_id,
                user_id=owner_id,
                username="room_owner",
                content=f"消息 {i}",
                message_type=MessageType.TEXT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            for i in range(5)
        ]

        # 配置 mocks
        mock_room_repository.get_by_id.return_value = room
        mock_message_repository.get_room_messages.return_value = messages

        # 執行整合流程
        # 1. 驗證房間存在
        room_result = await room_service.get_room_by_id(room_id)
        assert room_result is not None
        assert room_result.id == room_id

        # 2. 獲取房間消息
        messages_result = await message_service.get_room_messages(room_id)

        # 驗證整合結果
        assert messages_result is not None
        assert len(messages_result) == 5
        for i, message in enumerate(messages_result):
            assert message.content == f"消息 {i}"
            assert message.room_id == room_id

        # 驗證服務調用
        mock_room_repository.get_by_id.assert_called_once_with(room_id)
        mock_message_repository.get_room_messages.assert_called_once_with(
            room_id=room_id, skip=0, limit=20, message_type=None, user_id=None
        )

    @pytest.mark.asyncio
    async def test_error_handling_in_room_message_integration(
        self, integration_services, mock_room_repository, mock_message_repository
    ):
        """測試房間消息整合中的錯誤處理"""
        room_service = integration_services["room_service"]
        message_service = integration_services["message_service"]

        # 準備測試數據
        room_id = str(ObjectId())
        user_id = str(ObjectId())

        # 配置 mocks - 房間不存在
        mock_room_repository.get_by_id.return_value = None

        # 執行整合流程
        # 1. 嘗試獲取不存在的房間
        room_result = await room_service.get_room_by_id(room_id)
        assert room_result is None

        # 2. 嘗試在不存在的房間發送消息
        message_create = MessageCreate(
            room_id=room_id, content="這條消息不會發送", message_type=MessageType.TEXT
        )

        # 創建一個假的用戶用於測試
        fake_user = UserInDB(
            id=user_id,
            username="test_user",
            email="test@example.com",
            hashed_password="hashed_password",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock UserRepository 用於 MessageService
        with patch(
            "app.repositories.user_repository.UserRepository"
        ) as mock_user_repo_class:
            mock_user_repo = mock_user_repo_class.return_value
            mock_user_repo.get_by_id = AsyncMock(return_value=fake_user)

            # 嘗試發送消息應該拋出異常
            message_result = None
            try:
                message_result = await message_service.create_message(
                    user_id=user_id, message_data=message_create
                )
            except ValueError as e:
                # 預期的錯誤
                assert "房間不存在" in str(e)

        # 驗證錯誤處理
        assert message_result is None  # 消息創建失敗

        # 驗證服務調用
        mock_room_repository.get_by_id.assert_called()
        mock_message_repository.create.assert_not_called()  # 未調用創建消息
