"""WebSocket 認證相關測試"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId

from app.core.exceptions import NotFoundError
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
    async def test_verify_room_membership_public_room_non_member(self):
        """測試公開房間非成員 — WS 不自動加入，回傳 False"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        mock_room_service = AsyncMock()

        with patch(
            "app.websocket.auth.create_room_service",
            return_value=mock_room_service,
        ):
            mock_room = Mock()
            mock_room.members = []
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is False
            # 確認不會調用 join_room（WS 不做自動加入）
            mock_room_service.join_room.assert_not_called()

    @pytest.mark.asyncio
    async def test_verify_room_membership_member(self):
        """測試房間成員驗證 — 是成員"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        mock_room_service = AsyncMock()

        with patch(
            "app.websocket.auth.create_room_service",
            return_value=mock_room_service,
        ):
            mock_room = Mock()
            mock_room.members = [user_id, str(ObjectId())]
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_room_membership_non_member(self):
        """測試房間成員驗證 — 非成員"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        mock_room_service = AsyncMock()

        with patch(
            "app.websocket.auth.create_room_service",
            return_value=mock_room_service,
        ):
            mock_room = Mock()
            mock_room.members = [str(ObjectId()), str(ObjectId())]
            mock_room_service.get_room_by_id.return_value = mock_room

            result = await verify_room_membership(user_id, room_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_room_membership_room_not_found(self):
        """測試房間不存在的情況"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())

        mock_room_service = AsyncMock()

        with patch(
            "app.websocket.auth.create_room_service",
            return_value=mock_room_service,
        ):
            mock_room_service.get_room_by_id.side_effect = NotFoundError("房間不存在")

            result = await verify_room_membership(user_id, room_id)

            assert result is False
