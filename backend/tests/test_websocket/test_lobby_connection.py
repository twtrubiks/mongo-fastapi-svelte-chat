"""測試 lobby 連接功能"""

import pytest
from bson import ObjectId

from app.websocket.auth import verify_room_membership


class TestLobbyConnection:
    """測試 lobby 特殊房間的連接功能"""

    @pytest.mark.asyncio
    async def test_lobby_allows_any_authenticated_user(self):
        """測試任何已認證用戶都可以連接到 lobby"""
        # 準備測試數據
        user_id = str(ObjectId())
        room_id = "lobby"

        # 執行測試 - 不需要 mock，因為 lobby 會直接返回 True
        result = await verify_room_membership(user_id, room_id)

        # 驗證結果
        assert result is True

    @pytest.mark.asyncio
    async def test_lobby_case_sensitive(self):
        """測試 lobby 名稱是否區分大小寫"""
        user_id = str(ObjectId())

        # 測試不同大小寫
        assert await verify_room_membership(user_id, "lobby") is True
        assert await verify_room_membership(user_id, "Lobby") is False  # 區分大小寫
        assert await verify_room_membership(user_id, "LOBBY") is False
