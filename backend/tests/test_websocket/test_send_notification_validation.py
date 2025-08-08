"""WebSocket 通知驗證測試"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import WebSocket

from app.websocket.manager import ConnectionManager


class TestNotificationValidation:
    """測試通知驗證功能"""

    @pytest.fixture
    def connection_manager(self):
        """創建連接管理器實例"""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """創建 Mock WebSocket"""
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_send_notification_with_valid_data(
        self, connection_manager, mock_websocket
    ):
        """測試發送有效通知資料"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser"}

        # 連接用戶
        await connection_manager.connect(mock_websocket, user_id, room_id, user_info)

        # 有效的通知資料
        notification_data = {
            "id": "notif123",
            "user_id": user_id,
            "type": "MESSAGE",
            "status": "UNREAD",
            "title": "來自 John 的新訊息",
            "message": "在 測試房間 中：Hello world",
            "content": "在 測試房間 中：Hello world",
            "data": {"room_id": room_id, "sender_id": "john123"},
            "metadata": {"room_id": room_id, "sender_id": "john123"},
            "room_id": room_id,
            "sender_id": "john123",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }

        # 發送通知
        await connection_manager.send_notification(user_id, notification_data)

        # 驗證 WebSocket 被調用（connect 會發送 room_users，notification 會發送通知）
        assert mock_websocket.send_text.call_count == 2

        # 獲取通知的資料（第二次調用）
        call_args = mock_websocket.send_text.call_args_list[1][0][0]
        import json

        sent_data = json.loads(call_args)

        # 驗證發送的資料結構
        assert sent_data["type"] == "notification"
        assert sent_data["data"]["title"] == "來自 John 的新訊息"
        assert sent_data["data"]["message"] == "在 測試房間 中：Hello world"

    @pytest.mark.asyncio
    async def test_send_notification_with_empty_data(
        self, connection_manager, mock_websocket
    ):
        """測試發送空通知資料"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser"}

        # 連接用戶
        await connection_manager.connect(mock_websocket, user_id, room_id, user_info)

        # 空的通知資料
        notification_data = None

        # 發送通知
        await connection_manager.send_notification(user_id, notification_data)

        # 驗證只有 connect 時的 room_users 訊息被發送，沒有通知訊息
        assert mock_websocket.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_send_notification_missing_title(
        self, connection_manager, mock_websocket
    ):
        """測試發送缺少標題的通知"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser"}

        # 連接用戶
        await connection_manager.connect(mock_websocket, user_id, room_id, user_info)

        # 缺少標題的通知資料
        notification_data = {
            "id": "notif123",
            "user_id": user_id,
            "type": "MESSAGE",
            "status": "UNREAD",
            # "title": "來自 John 的新訊息",  # 缺少標題
            "message": "在 測試房間 中：Hello world",
            "data": {"room_id": room_id},
        }

        # 發送通知
        await connection_manager.send_notification(user_id, notification_data)

        # 驗證只有 connect 時的 room_users 訊息被發送，沒有通知訊息
        assert mock_websocket.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_send_notification_missing_message(
        self, connection_manager, mock_websocket
    ):
        """測試發送缺少訊息內容的通知"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser"}

        # 連接用戶
        await connection_manager.connect(mock_websocket, user_id, room_id, user_info)

        # 缺少訊息內容的通知資料
        notification_data = {
            "id": "notif123",
            "user_id": user_id,
            "type": "MESSAGE",
            "status": "UNREAD",
            "title": "來自 John 的新訊息",
            # "message": "在 測試房間 中：Hello world",  # 缺少訊息
            "data": {"room_id": room_id},
        }

        # 發送通知
        await connection_manager.send_notification(user_id, notification_data)

        # 驗證只有 connect 時的 room_users 訊息被發送，沒有通知訊息
        assert mock_websocket.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_send_notification_empty_title(
        self, connection_manager, mock_websocket
    ):
        """測試發送空標題的通知"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser"}

        # 連接用戶
        await connection_manager.connect(mock_websocket, user_id, room_id, user_info)

        # 空標題的通知資料
        notification_data = {
            "id": "notif123",
            "user_id": user_id,
            "type": "MESSAGE",
            "status": "UNREAD",
            "title": "",  # 空標題
            "message": "在 測試房間 中：Hello world",
            "data": {"room_id": room_id},
        }

        # 發送通知
        await connection_manager.send_notification(user_id, notification_data)

        # 驗證只有 connect 時的 room_users 訊息被發送，沒有通知訊息
        assert mock_websocket.send_text.call_count == 1

    @pytest.mark.asyncio
    async def test_send_notification_user_not_connected(self, connection_manager):
        """測試向未連接用戶發送通知"""
        user_id = "user123"

        # 有效的通知資料
        notification_data = {
            "id": "notif123",
            "user_id": user_id,
            "type": "MESSAGE",
            "status": "UNREAD",
            "title": "來自 John 的新訊息",
            "message": "在 測試房間 中：Hello world",
            "data": {"room_id": "room456"},
        }

        # 發送通知給未連接的用戶
        await connection_manager.send_notification(user_id, notification_data)

        # 驗證不會拋出異常，靜默處理
        # 這個測試主要確保函數不會崩潰
