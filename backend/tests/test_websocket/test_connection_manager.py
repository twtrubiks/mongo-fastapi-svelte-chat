"""WebSocket ConnectionManager 的測試"""

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import WebSocket

import app.websocket.manager as manager_module
from app.services.room_service import RoomService
from app.websocket.manager import ConnectionManager
from tests.test_websocket.membership_fake import FakeMembership


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
        """創建連接管理器實例（測試用，縮短 debounce 時間）"""
        cm = ConnectionManager(membership=FakeMembership().factory())
        cm._disconnect_debounce_seconds = 0.5
        cm._room_rejoin_debounce_seconds = 0.5
        return cm

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

        # 驗證斷開（連線立即清除，room_users 延遲清除）
        assert user_id not in connection_manager.active_connections
        assert user_id in connection_manager.room_users.get(room_id, set())

        # user_info 會在 debounce 後才清除，此時應仍存在
        assert user_id in connection_manager.user_info
        assert user_id in connection_manager.global_online_users

        # 等待 debounce 完成後，所有狀態才會清除
        await asyncio.sleep(
            max(
                connection_manager._disconnect_debounce_seconds,
                connection_manager._room_rejoin_debounce_seconds,
            )
            + 0.2
        )
        assert user_id not in connection_manager.user_info
        assert user_id not in connection_manager.global_online_users
        assert user_id not in connection_manager.room_users.get(room_id, set())

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
    async def test_slow_close_of_replaced_connection_blocks_no_one_else(
        self, connection_manager
    ):
        """取代舊連線時，舊連線關閉很慢（對端不回關閉握手）：其他人的連線與撤銷不被卡住"""
        room_id = "room123"
        old_closed = asyncio.Event()

        async def slow_close(**_):
            await old_closed.wait()

        def ws():
            mock = Mock(spec=WebSocket)
            mock.accept = AsyncMock()
            mock.send_text = AsyncMock()
            mock.close = AsyncMock()
            return mock

        old, new = ws(), ws()
        old.close = AsyncMock(side_effect=slow_close)
        info = {"id": "user1", "username": "User1"}
        await connection_manager.connect(old, "user1", room_id, info)
        reconnecting = asyncio.create_task(
            connection_manager.connect(new, "user1", room_id, info)
        )
        await asyncio.sleep(0.01)  # 正在等舊連線關閉

        other = ws()
        await asyncio.wait_for(
            connection_manager.connect(
                other, "user2", room_id, {"id": "user2", "username": "User2"}
            ),
            timeout=1,
        )
        await asyncio.wait_for(
            connection_manager.force_disconnect("user2", room_id), timeout=1
        )
        other.close.assert_called_once()

        old_closed.set()
        assert await reconnecting is True
        assert connection_manager.active_connections["user1"][room_id] is new

    @pytest.mark.asyncio
    async def test_stale_disconnect_preserves_new_connection(self, connection_manager):
        """測試舊連線的 disconnect 不會誤刪已取代的新連線（競態修復）

        重現情境：同一 user 同房重複連線。connect 以新 websocket 覆寫並關閉舊連線後，
        舊連線 handler 的 finally 會呼叫 disconnect。若 disconnect 無條件清理，
        會把已是新連線的項刪掉，導致新連線收不到後續 personal message。
        傳入 websocket 比對 identity 後，stale disconnect 應被略過。
        """
        user_id = "user123"
        room_id = "room456"
        user_info = {"id": user_id, "username": "testuser", "avatar": None}

        old_ws = Mock(spec=WebSocket)
        old_ws.accept = AsyncMock()
        old_ws.close = AsyncMock()
        old_ws.send_text = AsyncMock()

        new_ws = Mock(spec=WebSocket)
        new_ws.accept = AsyncMock()
        new_ws.close = AsyncMock()
        new_ws.send_text = AsyncMock()

        # 第一條連線，接著第二條連線取代它
        await connection_manager.connect(old_ws, user_id, room_id, user_info)
        await connection_manager.connect(new_ws, user_id, room_id, user_info)
        assert connection_manager.active_connections[user_id][room_id] is new_ws

        # 模擬舊連線 handler 的 finally：用舊 websocket 呼叫 disconnect
        await connection_manager.disconnect(user_id, room_id, old_ws)

        # 新連線不應被刪除
        assert user_id in connection_manager.active_connections
        assert connection_manager.active_connections[user_id][room_id] is new_ws
        assert user_id in connection_manager.room_users[room_id]
        # 不應排程離線 / 房間離開
        assert user_id not in connection_manager._pending_offline
        assert (user_id, room_id) not in connection_manager._pending_room_leave

        # 新連線仍能收到 personal message
        new_ws.send_text.reset_mock()
        await connection_manager.send_personal_message(
            user_id, room_id, {"type": "test", "content": "still reachable"}
        )
        new_ws.send_text.assert_called_once()

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
        await connection_manager.broadcast_to_room(
            room_id, message, exclude_user=exclude_user
        )

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

        # send_personal_message 透過 asyncio.create_task 延遲清理，需讓事件迴圈執行背景任務
        await asyncio.sleep(0)

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
        # room_users 在 debounce 期間仍保留
        assert user_id in connection_manager.room_users.get(rooms[0], set())

        # 但仍在其他房間
        for room_id in rooms[1:]:
            assert room_id in connection_manager.active_connections[user_id]
            assert user_id in connection_manager.room_users[room_id]

        # 等待 room debounce 完成後，room_users 才會清除
        await asyncio.sleep(connection_manager._room_rejoin_debounce_seconds + 0.2)
        assert user_id not in connection_manager.room_users.get(rooms[0], set())

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

    @pytest.mark.asyncio
    async def test_room_rejoin_within_debounce_suppresses_user_joined(
        self, connection_manager
    ):
        """測試快速重連同一房間不廣播 user_joined"""
        room_id = "room123"

        # 連接兩個使用者
        user1_id = "user1"
        user1_info = {"id": user1_id, "username": "User1"}
        ws1 = Mock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()

        user2_id = "user2"
        user2_info = {"id": user2_id, "username": "User2"}
        ws2 = Mock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await connection_manager.connect(ws1, user1_id, room_id, user1_info)
        await connection_manager.connect(ws2, user2_id, room_id, user2_info)

        # 重置 mock 以清除連接時的調用
        ws2.send_text.reset_mock()

        # user1 斷開
        await connection_manager.disconnect(user1_id, room_id)

        # user1 在 debounce 窗口內重連
        ws1_new = Mock(spec=WebSocket)
        ws1_new.accept = AsyncMock()
        ws1_new.send_text = AsyncMock()
        await connection_manager.connect(ws1_new, user1_id, room_id, user1_info)

        # 驗證 user2 沒有收到 user_joined 訊息
        for call in ws2.send_text.call_args_list:
            msg = json.loads(call[0][0])
            assert msg.get("type") != "user_joined", "快速重連時不應廣播 user_joined"

        # 驗證 user1 仍收到 room_users 列表
        room_users_received = False
        for call in ws1_new.send_text.call_args_list:
            msg = json.loads(call[0][0])
            if msg.get("type") == "room_users":
                room_users_received = True
                break
        assert room_users_received, "重連的使用者應收到 room_users 列表"

    @pytest.mark.asyncio
    async def test_room_rejoin_after_debounce_broadcasts_user_joined(
        self, connection_manager
    ):
        """測試超過 debounce 後重連正常廣播 user_joined"""
        room_id = "room123"

        # 連接兩個使用者
        user1_id = "user1"
        user1_info = {"id": user1_id, "username": "User1"}
        ws1 = Mock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()

        user2_id = "user2"
        user2_info = {"id": user2_id, "username": "User2"}
        ws2 = Mock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()

        await connection_manager.connect(ws1, user1_id, room_id, user1_info)
        await connection_manager.connect(ws2, user2_id, room_id, user2_info)

        # user1 斷開
        await connection_manager.disconnect(user1_id, room_id)

        # 等待 debounce 過期
        await asyncio.sleep(connection_manager._room_rejoin_debounce_seconds + 0.2)

        # 重置 mock
        ws2.send_text.reset_mock()

        # user1 重連（debounce 已過期）
        ws1_new = Mock(spec=WebSocket)
        ws1_new.accept = AsyncMock()
        ws1_new.send_text = AsyncMock()
        await connection_manager.connect(ws1_new, user1_id, room_id, user1_info)

        # 驗證 user2 收到 user_joined 訊息
        user_joined_received = False
        for call in ws2.send_text.call_args_list:
            msg = json.loads(call[0][0])
            if msg.get("type") == "user_joined":
                user_joined_received = True
                break
        assert user_joined_received, "debounce 過期後應正常廣播 user_joined"

    @pytest.mark.asyncio
    async def test_different_room_always_broadcasts_user_joined(
        self, connection_manager
    ):
        """測試連線不同房間時總是廣播 user_joined"""
        room_a = "room_a"
        room_b = "room_b"

        user1_id = "user1"
        user1_info = {"id": user1_id, "username": "User1"}

        # user1 連線 room_a
        ws1 = Mock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        await connection_manager.connect(ws1, user1_id, room_a, user1_info)

        # user2 在 room_b
        user2_id = "user2"
        user2_info = {"id": user2_id, "username": "User2"}
        ws2 = Mock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()
        await connection_manager.connect(ws2, user2_id, room_b, user2_info)

        # user1 斷開 room_a
        await connection_manager.disconnect(user1_id, room_a)

        # 重置 mock
        ws2.send_text.reset_mock()

        # user1 連線 room_b（不同房間）— 應正常廣播
        ws1_new = Mock(spec=WebSocket)
        ws1_new.accept = AsyncMock()
        ws1_new.send_text = AsyncMock()
        await connection_manager.connect(ws1_new, user1_id, room_b, user1_info)

        # 驗證 user2 收到 user_joined
        user_joined_received = False
        for call in ws2.send_text.call_args_list:
            msg = json.loads(call[0][0])
            if msg.get("type") == "user_joined":
                user_joined_received = True
                break
        assert user_joined_received, "連線不同房間應正常廣播 user_joined"

    @pytest.mark.asyncio
    async def test_force_disconnect_revokes_room_broadcast(self, connection_manager):
        """測試強制斷線後不再收到房間廣播（離開房間撤銷讀取權）"""
        room_id = "room123"

        # 連接兩個使用者
        ws1 = Mock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock()
        ws1.close = AsyncMock()
        await connection_manager.connect(
            ws1, "user1", room_id, {"id": "user1", "username": "User1"}
        )

        ws2 = Mock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock()
        await connection_manager.connect(
            ws2, "user2", room_id, {"id": "user2", "username": "User2"}
        )

        # 強制斷開 user1
        await connection_manager.force_disconnect("user1", room_id)

        # 驗證 socket 以 4003 關閉（前端不重連）
        ws1.close.assert_called_once()
        assert ws1.close.call_args.kwargs["code"] == 4003

        # 驗證狀態立即清理（不走 debounce）
        assert "user1" not in connection_manager.active_connections
        assert "user1" not in connection_manager.room_users.get(room_id, set())
        assert ("user1", room_id) not in connection_manager._pending_room_leave

        # 廣播不再送達 user1，user2 正常收到
        ws1.send_text.reset_mock()
        ws2.send_text.reset_mock()
        await connection_manager.broadcast_to_room(
            room_id, {"type": "message", "content": "secret"}
        )
        ws1.send_text.assert_not_called()
        ws2.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_disconnect_keeps_other_rooms(self, connection_manager):
        """測試強制斷線只影響指定房間，其他房間連線不受影響"""
        user_id = "user1"
        user_info = {"id": user_id, "username": "User1"}

        ws_a = Mock(spec=WebSocket)
        ws_a.accept = AsyncMock()
        ws_a.send_text = AsyncMock()
        ws_a.close = AsyncMock()
        await connection_manager.connect(ws_a, user_id, "room_a", user_info)

        ws_b = Mock(spec=WebSocket)
        ws_b.accept = AsyncMock()
        ws_b.send_text = AsyncMock()
        await connection_manager.connect(ws_b, user_id, "room_b", user_info)

        # 強制斷開 room_a
        await connection_manager.force_disconnect(user_id, "room_a")

        # room_a 連線已撤銷，room_b 連線保留
        assert "room_a" not in connection_manager.active_connections[user_id]
        assert connection_manager.active_connections[user_id]["room_b"] is ws_b
        assert user_id in connection_manager.room_users["room_b"]
        # 使用者仍在線（有其他房間連線），不應排程離線
        assert user_id not in connection_manager._pending_offline

        ws_b.send_text.reset_mock()
        await connection_manager.broadcast_to_room(
            "room_b", {"type": "message", "content": "hi"}
        )
        ws_b.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_disconnect_room_closes_all_connections(
        self, connection_manager
    ):
        """測試房間層級強制斷線關閉房內所有連線（房間刪除場景）"""
        room_id = "room123"

        websockets = []
        for i in range(3):
            ws = Mock(spec=WebSocket)
            ws.accept = AsyncMock()
            ws.send_text = AsyncMock()
            ws.close = AsyncMock()
            await connection_manager.connect(
                ws, f"user{i}", room_id, {"id": f"user{i}", "username": f"User{i}"}
            )
            websockets.append(ws)

        await connection_manager.force_disconnect_room(room_id)

        # 所有連線關閉、房間狀態清空
        for ws in websockets:
            ws.close.assert_called_once()
        assert room_id not in connection_manager.room_users
        for i in range(3):
            assert f"user{i}" not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_force_disconnect_close_failure_still_cleans_state(
        self, connection_manager
    ):
        """測試 socket 關閉失敗時狀態仍被清理（廣播名單不得殘留）"""
        room_id = "room123"
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock(side_effect=Exception("already closed"))
        await connection_manager.connect(
            ws, "user1", room_id, {"id": "user1", "username": "User1"}
        )

        # close 拋錯不應外洩，狀態仍需清理
        await connection_manager.force_disconnect("user1", room_id)
        assert "user1" not in connection_manager.active_connections
        assert "user1" not in connection_manager.room_users.get(room_id, set())

    @staticmethod
    def _ws():
        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.close = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_failed_recheck_withdraws_registration(self, connection_manager):
        """登記後再確認已不是成員：撤回登記、以 4001 關閉，房內不會看到他加入"""
        room_id = "room123"
        other = self._ws()
        await connection_manager.connect(
            other, "user2", room_id, {"id": "user2", "username": "User2"}
        )
        other.send_text.reset_mock()
        ws = self._ws()

        connected = await connection_manager.connect(
            ws,
            "user1",
            room_id,
            {"id": "user1", "username": "User1"},
            still_member=AsyncMock(return_value=False),
        )

        assert connected is False
        assert ws.close.call_args.kwargs["code"] == 4001
        ws.send_text.assert_not_called()
        other.send_text.assert_not_called()
        assert "user1" not in connection_manager.active_connections
        assert connection_manager.room_users[room_id] == {"user2"}

    @pytest.mark.asyncio
    async def test_failed_recheck_leaves_newer_connection_alone(
        self, connection_manager
    ):
        """再確認期間同一使用者的新連線取代了這條：確認失敗只撤回自己，不動新連線"""
        room_id = "room123"
        user_info = {"id": "user1", "username": "User1"}
        answer = asyncio.Event()

        async def not_member_after_newer_connection():
            await answer.wait()
            return False

        older, newer = self._ws(), self._ws()
        older_connect = asyncio.create_task(
            connection_manager.connect(
                older,
                "user1",
                room_id,
                user_info,
                still_member=not_member_after_newer_connection,
            )
        )
        await asyncio.sleep(0)
        assert await connection_manager.connect(newer, "user1", room_id, user_info)
        answer.set()

        assert await older_connect is False
        newer.close.assert_not_called()
        assert connection_manager.active_connections["user1"][room_id] is newer
        assert "user1" in connection_manager.room_users[room_id]

    @pytest.mark.asyncio
    async def test_recheck_error_propagates(self, connection_manager):
        """再確認時資料庫故障：往上拋（handler 以 4000 關閉），不留下確認中的標記"""
        ws = self._ws()

        with pytest.raises(ConnectionError):
            await connection_manager.connect(
                ws,
                "user1",
                "room123",
                {"id": "user1", "username": "User1"},
                still_member=AsyncMock(side_effect=ConnectionError("db down")),
            )

        assert connection_manager._confirming == set()
        assert "user1" not in connection_manager.room_users.get("room123", set())

    @pytest.mark.asyncio
    async def test_personal_event_avoids_connection_still_confirming(
        self, connection_manager
    ):
        """個人事件不送到還在確認成員資格的連線：確認失敗時事件會跟著連線消失"""
        info = {"id": "user1", "username": "User1"}
        await connection_manager.connect(self._ws(), "user1", "room_a", info)
        in_room_b = self._ws()
        await connection_manager.connect(in_room_b, "user1", "room_b", info)
        answer = asyncio.Event()

        async def not_member():
            await answer.wait()
            return False

        # 重新連線 room_a：在連線表中排在 room_b 前面，但還在確認
        confirming = self._ws()
        reconnecting = asyncio.create_task(
            connection_manager.connect(
                confirming, "user1", "room_a", info, still_member=not_member
            )
        )
        await asyncio.sleep(0.01)
        confirming.send_text.reset_mock()
        in_room_b.send_text.reset_mock()

        await connection_manager.send_event("user1", {"type": "room_updated"})
        answer.set()

        assert await reconnecting is False
        confirming.send_text.assert_not_called()
        in_room_b.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_removed_while_recheck_waits_for_lock(self, connection_manager):
        """再確認通過、排隊等鎖時被移出：房內先看到加入再看到移出，不會移出後又加入"""
        room_id = "room123"
        received = []  # (收件者, 事件類型, 事件中的使用者)

        def recording_ws(name):
            ws = self._ws()

            async def send_text(text):
                event = json.loads(text)
                user = event.get("user") or {}
                received.append((name, event["type"], user.get("id")))

            ws.send_text = AsyncMock(side_effect=send_text)
            return ws

        def info(user_id):
            return {"id": user_id, "username": user_id.title()}

        await connection_manager.connect(
            recording_ws("owner"), "owner", room_id, info("owner")
        )
        recheck_read = asyncio.Event()

        async def still_member():
            await recheck_read.wait()
            return True  # 讀資料庫時還是成員

        member = recording_ws("member")
        connecting = asyncio.create_task(
            connection_manager.connect(
                member, "member", room_id, info("member"), still_member=still_member
            )
        )
        await asyncio.sleep(0.01)  # member 已登記，等再確認
        # 其他操作正持鎖（例如另一條連線宣告加入時，鎖內廣播遇到很慢的連線）
        await connection_manager._lock.acquire()
        recheck_read.set()
        await asyncio.sleep(0.01)  # member 再確認通過，排隊等鎖

        service = RoomService(
            AsyncMock(), AsyncMock(), AsyncMock(), connection_manager=connection_manager
        )
        service.user_repo.get_by_id = AsyncMock(return_value=Mock(username="Member"))
        service._notify_room_change = AsyncMock()
        revoking = asyncio.create_task(
            service._revoke_member_access(room_id, "member", kicked=True)
        )
        await asyncio.sleep(0.01)
        connection_manager._lock.release()
        await asyncio.gather(connecting, revoking)

        seen_by_owner = [
            kind
            for to, kind, user_id in received
            if (to, user_id) == ("owner", "member")
        ]
        assert seen_by_owner == ["user_joined", "user_left"]
        assert member.close.call_args.kwargs["code"] == 4003
        assert "member" not in connection_manager.room_users[room_id]

    @pytest.mark.asyncio
    async def test_room_deletion_reaches_connection_awaiting_recheck(
        self, connection_manager
    ):
        """刪除房間時還在確認成員資格的連線（不在房間名單）也要斷開，之後不再宣告加入"""
        room_id = "room123"
        recheck_read = asyncio.Event()

        async def still_member():
            await recheck_read.wait()
            return True  # 讀資料庫時房間還在

        ws = self._ws()
        connecting = asyncio.create_task(
            connection_manager.connect(
                ws,
                "user1",
                room_id,
                {"id": "user1", "username": "User1"},
                still_member=still_member,
            )
        )
        await asyncio.sleep(0.01)
        await connection_manager.force_disconnect_room(room_id)
        recheck_read.set()

        assert await connecting is False
        assert ws.close.call_args.kwargs["code"] == 4003
        assert "user1" not in connection_manager.active_connections
        assert room_id not in connection_manager.room_users

    @pytest.mark.asyncio
    async def test_room_leave_debounce_cleans_up_room_users(self, connection_manager):
        """測試 debounce 到期後正確清理 room_users"""
        room_id = "room123"
        user_id = "user1"
        user_info = {"id": user_id, "username": "User1"}

        ws = Mock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()

        await connection_manager.connect(ws, user_id, room_id, user_info)

        # 斷開
        await connection_manager.disconnect(user_id, room_id)

        # debounce 期間：使用者仍在 room_users 中
        assert user_id in connection_manager.room_users.get(room_id, set())
        assert (user_id, room_id) in connection_manager._pending_room_leave

        # 等待 debounce 完成
        await asyncio.sleep(connection_manager._room_rejoin_debounce_seconds + 0.2)

        # debounce 後：使用者已從 room_users 移除
        assert user_id not in connection_manager.room_users.get(room_id, set())
        assert (user_id, room_id) not in connection_manager._pending_room_leave


# ==================== debounce 時間軸與事件 payload ====================

FROZEN_NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
TS = "2026-01-02T03:04:05+00:00"

ALICE = {"id": "alice", "username": "Alice", "avatar": None}
BOB = {"id": "bob", "username": "Bob", "avatar": None}
CAROL = {"id": "carol", "username": "Carol", "avatar": None}
DAVE = {"id": "dave", "username": "Dave", "avatar": None}
ERIN = {"id": "erin", "username": "Erin", "avatar": None}


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


async def _drain():
    """讓背景 task 跑到下一個等待點"""
    for _ in range(20):
        await asyncio.sleep(0)


class VirtualClock:
    """取代 manager 模組內的 asyncio：sleep 改走虛擬時間，由 advance_to() 推進

    其餘屬性（create_task、Lock…）照常委派給真正的 asyncio。
    """

    def __init__(self):
        self.now = 0.0
        self._sleepers: list[tuple[float, asyncio.Future]] = []

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def sleep(self, seconds):
        future = asyncio.get_running_loop().create_future()
        self._sleepers.append((self.now + seconds, future))
        await future

    async def advance_to(self, t: float):
        """推進到時間 t：依到期先後逐一放行到期的 sleep"""
        await _drain()
        while due := sorted(
            (item for item in self._sleepers if item[0] <= t and not item[1].done()),
            key=lambda item: item[0],
        ):
            deadline, future = due[0]
            self.now = deadline
            future.set_result(None)
            await _drain()
        self.now = t
        await _drain()

    async def shutdown(self):
        for _, future in self._sleepers:
            if not future.done():
                future.cancel()
        await _drain()


def _ws():
    ws = Mock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _received(ws) -> list[dict]:
    """取出並清空此連線目前收到的訊息"""
    messages = [json.loads(call.args[0]) for call in ws.send_text.call_args_list]
    ws.send_text.reset_mock()
    return messages


async def _join(manager, user, room_id):
    ws = _ws()
    await manager.connect(ws, user["id"], room_id, dict(user))
    return ws


def _room_user_ids(manager, room_id) -> list[str]:
    return sorted(user["id"] for user in manager.get_room_users(room_id))


def _joined(user, room_id):
    return {"type": "user_joined", "user": user, "timestamp": TS, "room_id": room_id}


def _left(user, room_id):
    return {"type": "user_left", "user": user, "timestamp": TS, "room_id": room_id}


def _offline(user):
    return {
        "type": "user_status_changed",
        "user_id": user["id"],
        "is_online": False,
        "timestamp": TS,
    }


@pytest.fixture
async def clock(monkeypatch):
    virtual_clock = VirtualClock()
    monkeypatch.setattr(manager_module, "asyncio", virtual_clock)
    monkeypatch.setattr(manager_module, "datetime", _FrozenDatetime)
    yield virtual_clock
    await virtual_clock.shutdown()


# r1～r3：四人都是成員；r4：只有 erin（bob 等人不是成員）
MEMBERSHIP = {
    **{rid: {"alice", "bob", "carol", "dave"} for rid in ("r1", "r2", "r3")},
    "r4": {"erin"},
}


@pytest.fixture
def manager(clock):
    return ConnectionManager(membership=FakeMembership(MEMBERSHIP).factory())


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventPayloads:
    """連線事件的完整 payload 契約"""

    async def test_connect_events(self, manager):
        alice_ws = await _join(manager, ALICE, "r1")
        carol_ws = await _join(manager, CAROL, "r2")
        erin_ws = await _join(manager, ERIN, "r4")
        for ws in (alice_ws, carol_ws, erin_ws):
            _received(ws)

        bob_ws = _ws()
        await manager.connect(bob_ws, "bob", "r1", dict(BOB))

        # 同房其他人：user_joined；bob 所屬的其他房間：上線狀態只帶 id，不帶使用者資料
        assert _received(alice_ws) == [
            {"type": "user_joined", "user": BOB, "timestamp": TS, "room_id": "r1"}
        ]
        assert _received(carol_ws) == [
            {
                "type": "user_status_changed",
                "user_id": "bob",
                "is_online": True,
                "timestamp": TS,
            }
        ]
        # bob 不是 r4 的成員：r4 的人不知道 bob 上線
        assert _received(erin_ws) == []
        # 本人：房內在線列表，在線 ID 只列 r1 的成員（集合轉 list，順序不固定）
        [room_users] = _received(bob_ws)
        room_users["users"].sort(key=lambda user: user["id"])
        room_users["global_online_user_ids"].sort()
        assert room_users == {
            "type": "room_users",
            "users": [{**ALICE, "is_active": True}, {**BOB, "is_active": True}],
            "global_online_user_ids": ["alice", "bob", "carol"],
            "timestamp": TS,
            "room_id": "r1",
            "online_only": True,
        }

    async def test_offline_reaches_only_rooms_the_user_belongs_to(self, manager, clock):
        alice_ws = await _join(manager, ALICE, "r1")
        erin_ws = await _join(manager, ERIN, "r4")
        bob_ws = await _join(manager, BOB, "r2")
        for ws in (alice_ws, erin_ws):
            _received(ws)

        await manager.disconnect("bob", "r2", bob_ws)
        await clock.advance_to(5)

        # bob 是 r1 的成員（即使沒連在 r1）：r1 收到離線；r4 不是 bob 的房間
        assert _received(alice_ws) == [_offline(BOB)]
        assert _received(erin_ws) == []

    async def test_membership_lookup_failure_sends_no_status(self, clock):
        class BrokenMembership(FakeMembership):
            async def get_member_room_ids(self, user_id, room_ids):
                raise RuntimeError("db down")

        manager = ConnectionManager(membership=BrokenMembership(MEMBERSHIP).factory())
        carol_ws = await _join(manager, CAROL, "r2")
        _received(carol_ws)

        # 查不到成員資格：不退回送給所有房間，也不讓連線失敗
        assert await manager.connect(_ws(), "bob", "r1", dict(BOB)) is True
        assert _received(carol_ws) == []

    async def test_member_lookup_failure_on_connect_keeps_connection(self, clock):
        class BrokenMembership(FakeMembership):
            async def get_member_ids(self, room_id):
                raise RuntimeError("db down")

        manager = ConnectionManager(membership=BrokenMembership(MEMBERSHIP).factory())
        await _join(manager, ALICE, "r1")
        await _join(manager, CAROL, "r2")
        bob_ws = _ws()

        assert await manager.connect(bob_ws, "bob", "r1", dict(BOB)) is True
        # 查不到成員：在線列表退回本房的連線者（都已通過成員驗證），不列 r2 的 carol
        [room_users] = _received(bob_ws)
        assert sorted(room_users["global_online_user_ids"]) == ["alice", "bob"]

    async def test_switching_rooms_does_not_reannounce_online(self, manager):
        carol_ws = await _join(manager, CAROL, "r2")
        await _join(manager, BOB, "r1")
        _received(carol_ws)

        await _join(manager, BOB, "r3")

        # bob 本來就在線：其他房間不必再收到一次上線
        assert _received(carol_ws) == []

    async def test_stale_offline_is_not_sent_after_reconnect(self, clock):
        class SlowOffline(FakeMembership):
            """離線那次的成員查詢卡住，直到 release 被設定"""

            def __init__(self, rooms):
                super().__init__(rooms)
                self.release = asyncio.Event()

            async def get_member_room_ids(self, user_id, room_ids):
                if user_id not in self.online:
                    await self.release.wait()
                return await super().get_member_room_ids(user_id, room_ids)

        membership = SlowOffline(MEMBERSHIP)
        manager = ConnectionManager(membership=membership.factory())
        membership.online = manager.global_online_users
        alice_ws = await _join(manager, ALICE, "r1")
        bob_ws = await _join(manager, BOB, "r2")
        _received(alice_ws)

        await manager.disconnect("bob", "r2", bob_ws)
        await clock.advance_to(3)  # 離線處理開始，卡在成員查詢
        await _join(manager, BOB, "r2")  # 這時 bob 重新連線
        membership.release.set()
        await clock.advance_to(4)

        # 較晚完成的離線查詢不再送出：alice 看到的最後狀態是在線
        assert _received(alice_ws) == [
            {
                "type": "user_status_changed",
                "user_id": "bob",
                "is_online": True,
                "timestamp": TS,
            }
        ]

    async def test_online_member_ids_lists_only_members(self, manager):
        for user, room in ((ALICE, "r1"), (BOB, "r2"), (ERIN, "r4")):
            await _join(manager, user, room)

        assert sorted(await manager.get_online_member_ids("r1")) == ["alice", "bob"]
        assert await manager.get_online_member_ids("r4") == ["erin"]
        assert await manager.get_online_member_ids("lobby") == []

    async def test_notification(self, manager):
        bob_ws = await _join(manager, BOB, "r1")
        _received(bob_ws)
        data = {
            "id": "n1",
            "title": "新訊息",
            "message": "Alice: 嗨",
            "type": "message",
        }

        await manager.send_notification("bob", data)

        assert _received(bob_ws) == [
            {"type": "notification", "data": data, "timestamp": TS}
        ]

    async def test_personal_message_to_absent_connection_is_dropped(self, manager):
        bob_ws = await _join(manager, BOB, "r1")
        _received(bob_ws)

        await manager.send_personal_message("ghost", "r1", {"type": "pong"})
        await manager.send_personal_message("bob", "r2", {"type": "pong"})

        assert _received(bob_ws) == []


@pytest.mark.unit
@pytest.mark.asyncio
class TestDebounceTimeline:
    """離線（3 秒）與房間離開（5 秒）debounce：以虛擬時間驗證時間軸"""

    async def test_offline_announced_exactly_3s_after_last_room_closes(
        self, manager, clock
    ):
        alice_ws = await _join(manager, ALICE, "r1")
        bob_ws = await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1", bob_ws)

        await clock.advance_to(2.999)
        assert _received(alice_ws) == []
        assert sorted(list(manager.global_online_users)) == ["alice", "bob"]

        await clock.advance_to(3)
        assert _received(alice_ws) == [
            {"type": "user_left", "user": BOB, "timestamp": TS, "room_id": "r1"},
            {
                "type": "user_status_changed",
                "user_id": "bob",
                "is_online": False,
                "timestamp": TS,
            },
        ]
        assert list(manager.global_online_users) == ["alice"]
        assert manager.get_room_users("r1") == [ALICE]
        # 計時器跑完後不殘留在 pending 表
        assert manager._pending_offline == {}
        assert manager._pending_room_leave == {}

    @pytest.mark.parametrize("rejoin_at, announced", [(4.999, False), (5, True)])
    async def test_room_rejoin_window_is_5s(self, manager, clock, rejoin_at, announced):
        alice_ws = await _join(manager, ALICE, "r1")
        await _join(manager, BOB, "r2")  # bob 仍在其他房間，不會離線
        bob_r1 = await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1", bob_r1)
        await clock.advance_to(rejoin_at)
        assert _room_user_ids(manager, "r1") == (
            ["alice"] if announced else ["alice", "bob"]
        )

        await _join(manager, BOB, "r1")
        assert _received(alice_ws) == ([_joined(BOB, "r1")] if announced else [])

    async def test_reconnect_within_offline_window_restarts_debounce(
        self, manager, clock
    ):
        """斷線 → 3 秒內重連 → 再斷線：離線要從最後一次斷線起算"""
        alice_ws = await _join(manager, ALICE, "r1")
        bob_ws = await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1", bob_ws)
        await clock.advance_to(1)
        bob_ws = await _join(manager, BOB, "r1")
        await clock.advance_to(2)
        await manager.disconnect("bob", "r1", bob_ws)

        await clock.advance_to(4.999)
        assert _received(alice_ws) == []
        assert "bob" in list(manager.global_online_users)

        await clock.advance_to(5)
        assert _received(alice_ws) == [_left(BOB, "r1"), _offline(BOB)]

    async def test_room_flap_restarts_rejoin_window(self, manager, clock):
        """同房斷線 → 重連 → 再斷線：舊的房間離開計時器作廢，視窗從最後一次斷線起算"""
        alice_ws = await _join(manager, ALICE, "r1")
        await _join(manager, BOB, "r2")
        bob_r1 = await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1", bob_r1)
        await clock.advance_to(1)
        bob_r1 = await _join(manager, BOB, "r1")
        await clock.advance_to(2)
        await manager.disconnect("bob", "r1", bob_r1)

        # 距第一次斷線已超過 5 秒、距最後一次未滿
        await clock.advance_to(6)
        assert _room_user_ids(manager, "r1") == ["alice", "bob"]
        await _join(manager, BOB, "r1")
        assert _received(alice_ws) == []

    async def test_force_disconnect_from_last_room_goes_offline_after_3s(
        self, manager, clock
    ):
        """被移出唯一所在的房間時比照斷線：3 秒後全域離線並通知其他人"""
        alice_ws = await _join(manager, ALICE, "r1")
        await _join(manager, BOB, "r2")
        _received(alice_ws)

        await manager.force_disconnect("bob", "r2")

        await clock.advance_to(2.999)
        assert sorted(list(manager.global_online_users)) == ["alice", "bob"]
        await clock.advance_to(3)
        assert list(manager.global_online_users) == ["alice"]
        assert _received(alice_ws) == [_offline(BOB)]

    async def test_force_disconnect_discards_pending_rejoin_timer(self, manager, clock):
        """斷線 debounce 中被移出房間，之後重新加入：舊計時器不可再動到新連線的狀態"""
        alice_ws = await _join(manager, ALICE, "r1")
        await _join(manager, BOB, "r2")
        bob_r1 = await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1", bob_r1)
        await clock.advance_to(1)
        await manager.force_disconnect("bob", "r1")
        await clock.advance_to(2)
        bob_r1 = await _join(manager, BOB, "r1")
        assert _received(alice_ws) == [_joined(BOB, "r1")]
        await clock.advance_to(3)
        await manager.disconnect("bob", "r1", bob_r1)

        await clock.advance_to(6)
        assert _room_user_ids(manager, "r1") == ["alice", "bob"]
        await _join(manager, BOB, "r1")
        assert _received(alice_ws) == []

    async def test_going_offline_discards_pending_rejoin_timers(self, manager, clock):
        """離線後重新上線：離線前排下的房間離開計時器不可再動到新連線的狀態"""
        alice_ws = await _join(manager, ALICE, "r1")
        bob_ws = await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1", bob_ws)
        await clock.advance_to(3)
        assert _received(alice_ws) == [_left(BOB, "r1"), _offline(BOB)]

        await clock.advance_to(4)
        bob_ws = await _join(manager, BOB, "r1")
        assert _received(alice_ws) == [_joined(BOB, "r1")]
        await clock.advance_to(4.5)
        await manager.disconnect("bob", "r1", bob_ws)

        await clock.advance_to(6)
        assert _room_user_ids(manager, "r1") == ["alice", "bob"]
        await _join(manager, BOB, "r1")
        assert _received(alice_ws) == []

    async def test_room_left_earlier_is_not_reannounced_on_offline(
        self, manager, clock
    ):
        """切房（仍在線）不廣播 user_left；之後離線也不可對早已離開的房間補發 user_left"""
        alice_ws = await _join(manager, ALICE, "r1")
        bob_r2 = await _join(manager, BOB, "r2")
        bob_r1 = await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1", bob_r1)
        await clock.advance_to(5)
        assert _received(alice_ws) == []
        assert manager.get_room_users("r1") == [ALICE]

        await clock.advance_to(6)
        await manager.disconnect("bob", "r2", bob_r2)
        await clock.advance_to(9)
        assert _received(alice_ws) == [_offline(BOB)]

    async def test_room_leave_finalizes_while_offline_pending(self, manager, clock):
        """房間離開計時器到期時使用者已無任何連線（尚在離線 debounce 中），仍要移出該房"""
        await _join(manager, ALICE, "r1")
        bob_r2 = await _join(manager, BOB, "r2")
        bob_r1 = await _join(manager, BOB, "r1")

        await manager.disconnect("bob", "r1", bob_r1)
        await clock.advance_to(4)
        await manager.disconnect("bob", "r2", bob_r2)

        await clock.advance_to(5)
        assert manager.get_room_users("r1") == [ALICE]
        assert "bob" in list(manager.global_online_users)

    async def test_room_switch_race_leftover_offline_timer_is_replaced(
        self, manager, clock
    ):
        """換房競態：舊房 disconnect 與新房 connect 排在同一把鎖後，舊房排下的離線計時器
        會殘留到新連線上；之後再斷線必須取代它，離線仍從最後一次斷線起算 3 秒"""
        alice_ws = await _join(manager, ALICE, "r1")
        bob_r2 = await _join(manager, BOB, "r2")

        # 慢速 client：connect 持鎖廣播時卡在它身上，製造鎖競爭
        gate = asyncio.Event()
        gate.set()

        async def slow_send(_text):
            await gate.wait()

        slow_ws = _ws()
        slow_ws.send_text = AsyncMock(side_effect=slow_send)
        await manager.connect(slow_ws, "carol", "r3", dict(CAROL))

        gate.clear()
        holder = asyncio.create_task(_join(manager, DAVE, "r3"))
        await _drain()
        leaving = asyncio.create_task(manager.disconnect("bob", "r2", bob_r2))
        await _drain()
        bob_r1 = _ws()
        switching = asyncio.create_task(manager.connect(bob_r1, "bob", "r1", dict(BOB)))
        await _drain()
        gate.set()
        await asyncio.gather(holder, leaving, switching)
        _received(alice_ws)

        await clock.advance_to(1)
        await manager.disconnect("bob", "r1", bob_r1)

        await clock.advance_to(3.999)
        assert _received(alice_ws) == []
        assert "bob" in list(manager.global_online_users)

        await clock.advance_to(4)
        assert _received(alice_ws) == [_left(BOB, "r1"), _offline(BOB)]

    async def test_repeated_legacy_disconnect_restarts_room_timer(self, manager, clock):
        """不帶 websocket 的舊式 disconnect 重複呼叫：房間離開計時器重新起算，舊的作廢"""
        await _join(manager, ALICE, "r1")
        await _join(manager, BOB, "r2")
        await _join(manager, BOB, "r1")

        await manager.disconnect("bob", "r1")
        await clock.advance_to(1)
        await manager.disconnect("bob", "r1")

        await clock.advance_to(5.5)
        assert _room_user_ids(manager, "r1") == ["alice", "bob"]
        await clock.advance_to(6)
        assert _room_user_ids(manager, "r1") == ["alice"]

    async def test_restarted_room_timer_still_tracked(self, manager, clock):
        """舊計時器被取消時不可移除新計時器的表項：5 秒內重入房仍算快速重連"""
        alice_ws = await _join(manager, ALICE, "r1")
        await _join(manager, BOB, "r2")
        await _join(manager, BOB, "r1")
        _received(alice_ws)

        await manager.disconnect("bob", "r1")
        await clock.advance_to(1)
        await manager.disconnect("bob", "r1")
        await clock.advance_to(1.5)
        assert ("bob", "r1") in manager._pending_room_leave

        await clock.advance_to(5.5)
        await _join(manager, BOB, "r1")
        assert _received(alice_ws) == []
        assert ("bob", "r1") not in manager._pending_room_leave

    async def test_legacy_disconnect_after_force_disconnect_is_noop(
        self, manager, clock
    ):
        """被移出房間後再呼叫不帶 websocket 的 disconnect：不拋錯、不排任何計時器"""
        await _join(manager, BOB, "r9")
        await manager.force_disconnect("bob", "r9")  # 房內已無人，房間項目被移除
        await manager.disconnect("bob", "r9")

        alice_ws = await _join(manager, ALICE, "r1")
        await _join(manager, BOB, "r2")
        await _join(manager, BOB, "r1")
        await manager.force_disconnect("bob", "r1")
        await manager.disconnect("bob", "r1")
        _received(alice_ws)

        # 之後重新加入是新的加入，要照常廣播
        await clock.advance_to(1)
        await _join(manager, BOB, "r1")
        assert _received(alice_ws) == [_joined(BOB, "r1")]
