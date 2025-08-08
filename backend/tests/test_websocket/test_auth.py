"""WebSocket 認證相關測試"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId

from app.websocket.auth import verify_room_membership


class TestWebSocketAuth:
    """測試 WebSocket 認證功能"""

    @pytest.mark.asyncio
    async def test_verify_room_membership_lobby(self):
        """測試 lobby 房間的特殊處理"""
        # 任何登入用戶都應該可以連接到 lobby
        user_id = str(ObjectId())
        room_id = "lobby"

        # 不需要 mock room_service，因為 lobby 會直接返回 True
        result = await verify_room_membership(user_id, room_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_room_membership_invalid_room_id(self):
        """測試無效房間 ID 格式"""
        user_id = str(ObjectId())
        room_id = "invalid-room-id"  # 不是 ObjectId 格式，也不是 lobby

        result = await verify_room_membership(user_id, room_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_verify_room_membership_normal_room(self):
        """測試正常房間的成員驗證"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        # Mock room_service
        with patch("app.websocket.auth.get_container") as mock_get_container:
            mock_container = AsyncMock()
            mock_room_service = AsyncMock()

            # 設置 mock 返回值
            mock_get_container.return_value = mock_container
            mock_container.get.return_value = mock_room_service

            # 測試公開房間
            mock_room = Mock()
            mock_room.is_public = True
            mock_room.members = []
            mock_room.max_members = 100
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is True
            # 確認調用了 join_room
            mock_room_service.join_room.assert_called_once_with(room_id, user_id)

    @pytest.mark.asyncio
    async def test_verify_room_membership_private_room_member(self):
        """測試私人房間的成員驗證 - 是成員"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        with patch("app.websocket.auth.get_container") as mock_get_container:
            mock_container = AsyncMock()
            mock_room_service = AsyncMock()

            mock_get_container.return_value = mock_container
            mock_container.get.return_value = mock_room_service

            # 設置私人房間，用戶是成員
            mock_room = Mock()
            mock_room.is_public = False
            mock_room.members = [user_id, str(ObjectId())]  # 包含該用戶
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_room_membership_private_room_non_member(self):
        """測試私人房間的成員驗證 - 非成員"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        with patch("app.websocket.auth.get_container") as mock_get_container:
            mock_container = AsyncMock()
            mock_room_service = AsyncMock()

            mock_get_container.return_value = mock_container
            mock_container.get.return_value = mock_room_service

            # 設置私人房間，用戶不是成員
            mock_room = Mock()
            mock_room.is_public = False
            mock_room.members = [str(ObjectId()), str(ObjectId())]  # 不包含該用戶
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_room_membership_public_room_already_member(self):
        """測試公開房間 - 用戶已經是成員，不應重複加入"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        with patch("app.websocket.auth.get_container") as mock_get_container:
            mock_container = AsyncMock()
            mock_room_service = AsyncMock()

            mock_get_container.return_value = mock_container
            mock_container.get.return_value = mock_room_service

            # 設置公開房間，用戶已經是成員
            mock_room = Mock()
            mock_room.is_public = True
            mock_room.members = [user_id, str(ObjectId())]  # 用戶已在成員列表中
            mock_room.max_members = 100
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is True
            # 重要：確認沒有調用 join_room，因為用戶已經是成員
            mock_room_service.join_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_room_membership_full_room(self):
        """測試房間已滿的情況"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        with patch("app.websocket.auth.get_container") as mock_get_container:
            mock_container = AsyncMock()
            mock_room_service = AsyncMock()

            mock_get_container.return_value = mock_container
            mock_container.get.return_value = mock_room_service

            # 設置公開房間，已達到最大成員數
            mock_room = Mock()
            mock_room.is_public = True
            mock_room.members = [str(ObjectId()) for _ in range(5)]  # 5個成員
            mock_room.max_members = 5  # 最大5個成員
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is False
            # 不應調用 join_room
            mock_room_service.join_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_room_membership_join_room_failure(self):
        """測試 join_room 失敗的情況"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        with patch("app.websocket.auth.get_container") as mock_get_container:
            mock_container = AsyncMock()
            mock_room_service = AsyncMock()

            mock_get_container.return_value = mock_container
            mock_container.get.return_value = mock_room_service

            # 設置公開房間
            mock_room = Mock()
            mock_room.is_public = True
            mock_room.members = []
            mock_room.max_members = 100
            mock_room_service.get_room_by_id.return_value = mock_room

            # 模擬 join_room 拋出異常
            mock_room_service.join_room.side_effect = Exception("Database error")

            result = await verify_room_membership(user_id, room_id)

            assert result is False  # 應該返回 False
            mock_room_service.join_room.assert_called_once_with(room_id, user_id)
