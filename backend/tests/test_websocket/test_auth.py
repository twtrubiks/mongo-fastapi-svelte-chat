"""WebSocket 認證相關測試"""

from unittest.mock import AsyncMock, patch

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
    @pytest.mark.parametrize("is_member", [True, False])
    async def test_verify_room_membership_checks_membership_only(self, is_member):
        """只查成員資格，不讀整份房間；非成員不自動加入（加入必須走 HTTP API）"""
        user_id = str(ObjectId())
        room_id = str(ObjectId())
        mock_room_service = AsyncMock()
        mock_room_service.is_member.return_value = is_member

        with patch(
            "app.websocket.auth.create_room_service",
            return_value=mock_room_service,
        ):
            result = await verify_room_membership(user_id, room_id)

        assert result is is_member
        mock_room_service.is_member.assert_awaited_once_with(room_id, user_id)
        mock_room_service.get_room_by_id.assert_not_called()
        mock_room_service.join_room.assert_not_called()
