"""WebSocket ConnectionManager 的測試"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket
import json
from datetime import datetime, UTC
from app.websocket.manager import ConnectionManager


class TestConnectionManager:
    """測試 WebSocket 連接管理器"""
    
    @pytest.fixture
    def mock_websocket(self):
        """創建 Mock WebSocket"""
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock()
        ws.receive_json = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.fixture
    def connection_manager(self):
        """創建連接管理器實例"""
        return ConnectionManager()
    
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, connection_manager, mock_websocket):
        """測試連接和斷開"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser", "avatar": None}
        
        # 連接
        await connection_manager.connect(mock_websocket, user_id, room_id, user_info)
        
        # 驗證連接
        assert user_id in connection_manager.active_connections
        assert room_id in connection_manager.active_connections[user_id]
        assert user_id in connection_manager.room_users[room_id]
        assert connection_manager.user_info[user_id] == user_info
        
        # 驗證 accept 被調用
        mock_websocket.accept.assert_called_once()
        
        # 斷開連接
        await connection_manager.disconnect(user_id, room_id)
        
        # 驗證斷開
        assert user_id not in connection_manager.active_connections
        assert user_id not in connection_manager.room_users.get(room_id, set())
        assert user_id not in connection_manager.user_info
    
    @pytest.mark.asyncio
    async def test_duplicate_connection_handling(self, connection_manager):
        """測試重複連線處理 - 同一用戶連接到同一房間"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser", "avatar": None}
        
        # 創建兩個不同的 WebSocket 實例
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws1.close = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.accept = AsyncMock()
        mock_ws2.close = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        
        # 第一次連接
        await connection_manager.connect(mock_ws1, user_id, room_id, user_info)
        
        # 驗證第一個連接
        assert connection_manager.active_connections[user_id][room_id] == mock_ws1
        
        # 第二次連接（同一用戶，同一房間）
        await connection_manager.connect(mock_ws2, user_id, room_id, user_info)
        
        # 驗證舊連接被關閉
        mock_ws1.close.assert_called_once()
        
        # 驗證新連接取代了舊連接
        assert connection_manager.active_connections[user_id][room_id] == mock_ws2
        
        # 驗證用戶仍然只在房間中出現一次
        assert len(connection_manager.room_users[room_id]) == 1
        assert user_id in connection_manager.room_users[room_id]
    
    @pytest.mark.asyncio
    async def test_duplicate_connection_close_failure(self, connection_manager):
        """測試重複連線時關閉舊連接失敗的情況"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser", "avatar": None}
        
        # 創建兩個 WebSocket 實例
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws1.close = AsyncMock(side_effect=Exception("Close failed"))
        mock_ws1.send_text = AsyncMock()
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        
        # 第一次連接
        await connection_manager.connect(mock_ws1, user_id, room_id, user_info)
        
        # 第二次連接，關閉舊連接會失敗
        await connection_manager.connect(mock_ws2, user_id, room_id, user_info)
        
        # 即使關閉失敗，新連接仍應該成功建立
        assert connection_manager.active_connections[user_id][room_id] == mock_ws2
        
        # 驗證嘗試關閉舊連接
        mock_ws1.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_multiple_rooms_same_user(self, connection_manager):
        """測試同一用戶連接到多個房間"""
        user_id = "user123"
        room_id1 = "room456"
        room_id2 = "room789"
        user_info = {"id": user_id, "username": "testuser", "avatar": None}
        
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_text = AsyncMock()
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_text = AsyncMock()
        
        # 連接到第一個房間
        await connection_manager.connect(mock_ws1, user_id, room_id1, user_info)
        
        # 連接到第二個房間
        await connection_manager.connect(mock_ws2, user_id, room_id2, user_info)
        
        # 驗證用戶在兩個房間都有連接
        assert len(connection_manager.active_connections[user_id]) == 2
        assert connection_manager.active_connections[user_id][room_id1] == mock_ws1
        assert connection_manager.active_connections[user_id][room_id2] == mock_ws2
        
        # 驗證用戶在兩個房間的成員列表中
        assert user_id in connection_manager.room_users[room_id1]
        assert user_id in connection_manager.room_users[room_id2]
    
    @pytest.mark.asyncio
    async def test_broadcast_to_room(self, connection_manager):
        """測試房間廣播"""
        room_id = "room123"
        
        # 創建多個用戶連接
        users = []
        for i in range(3):
            user_id = f"user{i}"
            user_info = {"id": user_id, "username": f"User{i}"}
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            
            await connection_manager.connect(ws, user_id, room_id, user_info)
            users.append((user_id, ws))
        
        # 廣播訊息
        message = {"type": "chat", "content": "Hello everyone!"}
        await connection_manager.broadcast_to_room(room_id, message)
        
        # 驗證所有用戶都收到訊息
        for _, ws in users:
            ws.send_text.assert_called()
            # 獲取發送的內容
            call_args = ws.send_text.call_args[0][0]
            sent_message = json.loads(call_args)
            assert sent_message["type"] == "chat"
            assert sent_message["content"] == "Hello everyone!"
    
    @pytest.mark.asyncio
    async def test_broadcast_with_exclusion(self, connection_manager):
        """測試排除特定用戶的廣播"""
        room_id = "room123"
        exclude_user = "user1"
        
        # 創建用戶連接
        users = []
        for i in range(3):
            user_id = f"user{i}"
            user_info = {"id": user_id, "username": f"User{i}"}
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            
            await connection_manager.connect(ws, user_id, room_id, user_info)
            users.append((user_id, ws))
        
        # 廣播訊息，排除 user1
        message = {"type": "notification", "content": "Broadcast message"}
        await connection_manager.broadcast_to_room(room_id, message, exclude_user=exclude_user)
        
        # 驗證
        for user_id, ws in users:
            if user_id == exclude_user:
                # user1 的 send_text 不應該被調用（除了連接時的消息）
                # 連接時會收到 2 條消息：user_joined 和 room_users
                assert ws.send_text.call_count == 2  # 只有連接時的消息
            else:
                # 其他用戶應該收到額外的廣播消息
                assert ws.send_text.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_send_personal_message(self, connection_manager, mock_websocket):
        """測試發送個人訊息"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser"}
        
        # 連接用戶
        await connection_manager.connect(mock_websocket, user_id, room_id, user_info)
        
        # 重置 mock 以清除連接時的調用
        mock_websocket.send_text.reset_mock()
        
        # 發送個人訊息
        message = {"type": "private", "content": "Private message for you"}
        await connection_manager.send_personal_message(user_id, room_id, message)
        
        # 驗證訊息已發送
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        sent_message = json.loads(sent_data)
        assert sent_message["type"] == "private"
        assert sent_message["content"] == "Private message for you"
    
    @pytest.mark.asyncio
    async def test_get_room_users(self, connection_manager):
        """測試獲取房間用戶列表"""
        room_id = "room123"
        
        # 添加多個用戶
        user_ids = []
        for i in range(3):
            user_id = f"user{i}"
            user_info = {"id": user_id, "username": f"User{i}"}
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            
            await connection_manager.connect(ws, user_id, room_id, user_info)
            user_ids.append(user_id)
        
        # 獲取房間用戶
        room_users = connection_manager.get_room_users(room_id)
        
        # 驗證
        assert len(room_users) == 3
        for user_info in room_users:
            assert user_info["id"] in user_ids
    
    @pytest.mark.asyncio
    async def test_connection_error_handling(self, connection_manager):
        """測試連接錯誤處理"""
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser"}
        
        # 創建正常的 WebSocket 先連接
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        
        # 連接
        await connection_manager.connect(ws, user_id, room_id, user_info)
        
        # 現在讓 send_text 拋出錯誤
        ws.send_text = AsyncMock(side_effect=Exception("Connection lost"))
        
        # 嘗試發送訊息（應該處理錯誤並斷開連接）
        message = {"type": "test", "content": "Test message"}
        await connection_manager.send_personal_message(user_id, room_id, message)
        
        # 驗證連接已被清理
        assert user_id not in connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_multi_room_support(self, connection_manager):
        """測試多房間支持"""
        user_id = "user123"
        rooms = ["room1", "room2", "room3"]
        user_info = {"id": user_id, "username": "MultiRoomUser"}
        
        # 為每個房間創建連接
        websockets = {}
        for room_id in rooms:
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            websockets[room_id] = ws
            
            await connection_manager.connect(ws, user_id, room_id, user_info)
        
        # 驗證用戶在所有房間中
        assert len(connection_manager.active_connections[user_id]) == 3
        for room_id in rooms:
            assert room_id in connection_manager.active_connections[user_id]
            assert user_id in connection_manager.room_users[room_id]
        
        # 從一個房間斷開
        await connection_manager.disconnect(user_id, rooms[0])
        
        # 驗證用戶仍在其他房間
        assert len(connection_manager.active_connections[user_id]) == 2
        assert rooms[0] not in connection_manager.active_connections[user_id]
        assert user_id not in connection_manager.room_users.get(rooms[0], set())
        
        # 但仍在其他房間
        for room_id in rooms[1:]:
            assert room_id in connection_manager.active_connections[user_id]
            assert user_id in connection_manager.room_users[room_id]
    
    @pytest.mark.asyncio
    async def test_room_user_list_on_connect(self, connection_manager):
        """測試連接時發送房間用戶列表"""
        room_id = "room123"
        
        # 先連接一個用戶
        user1_id = "user1"
        user1_info = {"id": user1_id, "username": "User1"}
        ws1 = Mock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        
        await connection_manager.connect(ws1, user1_id, room_id, user1_info)
        
        # 連接第二個用戶
        user2_id = "user2"
        user2_info = {"id": user2_id, "username": "User2"}
        ws2 = Mock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()
        
        await connection_manager.connect(ws2, user2_id, room_id, user2_info)
        
        # 驗證第二個用戶收到房間用戶列表
        # 查找 room_users 類型的消息
        calls = ws2.send_text.call_args_list
        room_users_msg = None
        for call in calls:
            msg = json.loads(call[0][0])
            if msg.get("type") == "room_users":
                room_users_msg = msg
                break
        
        assert room_users_msg is not None
        assert len(room_users_msg["users"]) == 2
        user_ids = [u["id"] for u in room_users_msg["users"]]
        assert user1_id in user_ids
        assert user2_id in user_ids