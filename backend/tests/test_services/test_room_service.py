"""
測試房間服務層
使用 Mock 優先的方式測試所有功能
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, UTC
from bson import ObjectId
import bcrypt
import secrets

from app.services.room_service import RoomService
from app.models.room import RoomCreate, RoomInDB, RoomResponse, RoomUpdate, RoomJoinRequest
from app.models.enums import MemberRole, RoomType, JoinPolicy
from app.models.user import UserResponse


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
    def room_service(self, mock_repositories):
        """創建房間服務實例"""
        room_repo, user_repo, message_repo = mock_repositories
        return RoomService(room_repo, user_repo, message_repo)
    
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
            members=[str(ObjectId())],
            member_roles={},
            password_hash=None,
            invite_code=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
    
    def test_convert_to_response(self, room_service, sample_room):
        """測試轉換房間為響應格式"""
        # 測試正常轉換
        response = room_service._convert_to_response(sample_room)
        
        assert isinstance(response, RoomResponse)
        assert response.id == sample_room.id
        assert response.name == sample_room.name
        assert response.member_count == len(sample_room.members)
        assert response.has_password is False
        
        # 測試有密碼的房間
        sample_room.password_hash = "hashed_password"
        response = room_service._convert_to_response(sample_room)
        assert response.has_password is True
    
    
    
    @pytest.mark.asyncio
    async def test_create_room_user_not_found(self, room_service, mock_repositories):
        """測試用戶不存在時創建房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 用戶不存在
        user_repo.get_by_id.return_value = None
        
        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await room_service.create_room("invalid_user", RoomCreate(name="Test"))
        
        assert "用戶不存在" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_room_duplicate_name(self, room_service, mock_repositories):
        """測試房間名稱重複"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 設置
        user_id = str(ObjectId())
        user_repo.get_by_id.return_value = Mock(id=user_id)
        room_repo.get_by_name.return_value = Mock()  # 房間已存在
        
        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
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
        
        # 執行
        result = await room_service.get_room_by_id("invalid_id")
        
        # 驗證
        assert result is None
    
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
    async def test_get_rooms_with_search(self, room_service, mock_repositories, sample_room):
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
        room_repo.search_rooms.assert_called_once_with("test", 0, 20, True)
    
    @pytest.mark.asyncio
    async def test_join_room_direct(self, room_service, mock_repositories, sample_room):
        """測試直接加入房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # 設置房間為直接加入
        sample_room.join_policy = JoinPolicy.DIRECT
        sample_room.members = []
        room_repo.get_by_id.return_value = sample_room
        room_repo.add_member.return_value = True
        room_repo.update_member_role.return_value = True
        
        # 執行
        user_id = str(ObjectId())
        result = await room_service.join_room(sample_room.id, user_id)
        
        # 驗證
        assert result["success"] is True
        room_repo.add_member.assert_called_once_with(sample_room.id, user_id)
        room_repo.update_member_role.assert_called_once_with(sample_room.id, user_id, MemberRole.MEMBER)
    
    @pytest.mark.asyncio
    async def test_join_room_with_password(self, room_service, mock_repositories, sample_room):
        """測試使用密碼加入房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # 設置房間需要密碼
        sample_room.join_policy = JoinPolicy.PASSWORD
        sample_room.password_hash = bcrypt.hashpw(b"test123", bcrypt.gensalt()).decode('utf-8')
        sample_room.members = []
        room_repo.get_by_id.return_value = sample_room
        room_repo.add_member.return_value = True
        room_repo.update_member_role.return_value = True
        
        # 執行 - 正確密碼
        user_id = str(ObjectId())
        join_request = RoomJoinRequest(password="test123")
        result = await room_service.join_room(sample_room.id, user_id, join_request)
        
        # 驗證
        assert result["success"] is True
        
        # 測試錯誤密碼
        join_request = RoomJoinRequest(password="wrong_password")
        with pytest.raises(ValueError) as exc_info:
            await room_service.join_room(sample_room.id, user_id, join_request)
        assert "密碼錯誤" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_join_room_already_member(self, room_service, mock_repositories, sample_room):
        """測試已是成員時加入房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # 設置用戶已是成員
        user_id = str(ObjectId())
        sample_room.members = [user_id]
        room_repo.get_by_id.return_value = sample_room
        
        # 執行
        result = await room_service.join_room(sample_room.id, user_id)
        
        # 驗證
        assert result["success"] is True
        assert "已經是該房間的成員" in result["message"]
    
    @pytest.mark.asyncio
    async def test_join_room_full(self, room_service, mock_repositories, sample_room):
        """測試房間已滿時加入"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # 設置房間已滿
        sample_room.max_members = 1
        sample_room.members = [str(ObjectId())]
        room_repo.get_by_id.return_value = sample_room
        
        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await room_service.join_room(sample_room.id, str(ObjectId()))
        assert "房間已滿" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_leave_room_success(self, room_service, mock_repositories, sample_room):
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
        assert result["success"] is True
        room_repo.remove_member.assert_called_once_with(sample_room.id, user_id)
    
    @pytest.mark.asyncio
    async def test_leave_room_as_owner(self, room_service, mock_repositories, sample_room):
        """測試擁有者離開房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # 設置用戶為擁有者
        room_repo.get_by_id.return_value = sample_room
        
        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await room_service.leave_room(sample_room.id, sample_room.owner_id)
        assert "房間擁有者不能離開房間" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_room_success(self, room_service, mock_repositories, sample_room):
        """測試成功刪除房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 設置
        room_repo.get_by_id.return_value = sample_room
        room_repo.delete.return_value = True
        message_repo.delete_by_room_id.return_value = True
        
        # Mock connection_manager
        with patch('app.websocket.manager.connection_manager') as mock_conn_manager:
            mock_conn_manager.active_connections = {"user1": {}, "user2": {}}
            mock_conn_manager.send_notification = AsyncMock()
            
            # 執行
            result = await room_service.delete_room(sample_room.id, sample_room.owner_id)
            
            # 驗證
            assert result is True
            room_repo.delete.assert_called_once_with(sample_room.id)
            message_repo.delete_by_room_id.assert_called_once_with(sample_room.id)
            
            # 驗證 WebSocket 通知被發送
            # 應該發送給房間成員和其他在線用戶
            assert mock_conn_manager.send_notification.called
    
    @pytest.mark.asyncio
    async def test_delete_room_not_owner(self, room_service, mock_repositories, sample_room):
        """測試非擁有者刪除房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 設置
        room_repo.get_by_id.return_value = sample_room
        
        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await room_service.delete_room(sample_room.id, str(ObjectId()))
        assert "只有房間擁有者可以刪除房間" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_room_success(self, room_service, mock_repositories, sample_room):
        """測試成功更新房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 設置
        room_repo.get_by_id.return_value = sample_room
        # 創建更新後的房間
        updated_data = sample_room.model_dump()
        updated_data['name'] = "Updated Name"
        updated_room = RoomInDB(**updated_data)
        room_repo.update.return_value = updated_room
        
        # 更新數據
        update_data = RoomUpdate(name="Updated Name")
        
        # 執行
        result = await room_service.update_room(sample_room.id, sample_room.owner_id, update_data)
        
        # 驗證
        assert result is not None
        assert result.name == "Updated Name"
        room_repo.update.assert_called_once_with(sample_room.id, update_data)
    
    @pytest.mark.asyncio
    async def test_update_room_max_members_validation(self, room_service, mock_repositories, sample_room):
        """測試更新最大成員數驗證"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # 設置當前有 5 個成員
        sample_room.members = [str(ObjectId()) for _ in range(5)]
        room_repo.get_by_id.return_value = sample_room
        
        # 嘗試設置最大成員數為 3
        update_data = RoomUpdate(max_members=3)
        
        # 執行並驗證拋出異常
        with pytest.raises(ValueError) as exc_info:
            await room_service.update_room(sample_room.id, sample_room.owner_id, update_data)
        assert "最大成員數不能小於當前成員數" in str(exc_info.value)
    
    
    @pytest.mark.asyncio
    async def test_transfer_ownership(self, room_service, mock_repositories, sample_room):
        """測試轉移擁有權"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 設置
        new_owner_id = str(ObjectId())
        room_repo.get_by_id.return_value = sample_room
        room_repo.transfer_ownership.return_value = True
        
        # 執行
        result = await room_service.transfer_ownership(
            sample_room.id,
            sample_room.owner_id,
            new_owner_id
        )
        
        # 驗證
        assert result["success"] is True
        room_repo.transfer_ownership.assert_called_once_with(sample_room.id, new_owner_id)
    
    @pytest.mark.asyncio
    async def test_is_user_member(self, room_service, mock_repositories):
        """測試檢查用戶是否為成員"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 返回值
        room_repo.is_member.return_value = True
        
        # 執行
        result = await room_service.is_user_member("room_id", "user_id")
        
        # 驗證
        assert result is True
        room_repo.is_member.assert_called_once_with("room_id", "user_id")
    
    @pytest.mark.asyncio
    async def test_is_room_owner(self, room_service, mock_repositories):
        """測試檢查用戶是否為擁有者"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 返回值
        room_repo.is_owner.return_value = True
        
        # 執行
        result = await room_service.is_room_owner("room_id", "user_id")
        
        # 驗證
        assert result is True
        room_repo.is_owner.assert_called_once_with("room_id", "user_id")
    
    @pytest.mark.asyncio
    async def test_get_room_stats(self, room_service, mock_repositories, sample_room):
        """測試獲取房間統計"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock 設置
        room_repo.get_by_id.return_value = sample_room
        message_stats = Mock(total_messages=100, messages_today=10)
        message_repo.get_message_stats.return_value = message_stats
        
        # 執行
        result = await room_service.get_room_stats(sample_room.id)
        
        # 驗證
        assert result["room_id"] == sample_room.id
        assert result["member_count"] == len(sample_room.members)
        assert result["message_count"] == 100
        assert result["today_messages"] == 10
    
    @pytest.mark.asyncio
    async def test_broadcast_room_created(self, room_service, mock_repositories):
        """測試廣播房間創建事件"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # Mock connection manager
        mock_conn_manager = Mock()
        mock_conn_manager.active_connections = {
            "user1": {},
            "user2": {},
            "creator": {}
        }
        mock_conn_manager.send_notification = AsyncMock()
        
        # 創建房間響應
        room_response = Mock(id="room123", model_dump=lambda: {"id": "room123", "name": "Test"})
        
        # 執行
        await room_service._broadcast_room_created(mock_conn_manager, room_response, "creator")
        
        # 驗證 - 應該發送給除了創建者之外的所有用戶
        assert mock_conn_manager.send_notification.call_count == 2
        
    @pytest.mark.asyncio
    async def test_join_room_with_invite_code(self, room_service, mock_repositories, sample_room):
        """測試使用邀請碼加入房間"""
        room_repo, user_repo, message_repo = mock_repositories
        
        # 設置房間需要邀請碼
        sample_room.join_policy = JoinPolicy.INVITE
        sample_room.invite_code = "test-invite-code"
        sample_room.members = []
        room_repo.get_by_id.return_value = sample_room
        room_repo.add_member.return_value = True
        room_repo.update_member_role.return_value = True
        
        # 正確的邀請碼
        user_id = str(ObjectId())
        join_request = RoomJoinRequest(invite_code="test-invite-code")
        result = await room_service.join_room(sample_room.id, user_id, join_request)
        
        # 驗證
        assert result["success"] is True
        
        # 錯誤的邀請碼
        join_request = RoomJoinRequest(invite_code="wrong-code")
        with pytest.raises(ValueError) as exc_info:
            await room_service.join_room(sample_room.id, user_id, join_request)
        assert "邀請碼無效" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_delete_room_with_websocket_notification(self, room_service, mock_repositories, sample_room):
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
        
        # Mock connection_manager
        with patch('app.websocket.manager.connection_manager') as mock_conn_manager:
            # 模擬有其他在線用戶
            other_user1 = str(ObjectId())
            other_user2 = str(ObjectId())
            mock_conn_manager.active_connections = {
                sample_room.owner_id: {},
                member1_id: {},
                member2_id: {},
                other_user1: {},
                other_user2: {}
            }
            mock_conn_manager.send_notification = AsyncMock()
            
            # 執行
            result = await room_service.delete_room(sample_room.id, sample_room.owner_id)
            
            # 驗證刪除成功
            assert result is True
            
            # 驗證通知被發送給所有相關用戶
            # 預期的通知消息
            expected_message = {
                "type": "room_deleted",
                "room_id": sample_room.id,
                "deleted_by": sample_room.owner_id
            }
            
            # 驗證通知被發送的次數
            # 應該發送給：3個房間成員 + 2個其他在線用戶 = 5次
            assert mock_conn_manager.send_notification.call_count == 5
            
            # 驗證通知內容
            calls = mock_conn_manager.send_notification.call_args_list
            notified_users = set()
            for call in calls:
                user_id, message = call[0]
                notified_users.add(user_id)
                assert message == expected_message
            
            # 驗證所有用戶都收到通知
            expected_users = {sample_room.owner_id, member1_id, member2_id, other_user1, other_user2}
            assert notified_users == expected_users