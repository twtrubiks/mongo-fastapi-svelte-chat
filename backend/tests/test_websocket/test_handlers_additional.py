"""額外的 WebSocket handlers 測試
用於提升覆蓋率到 60%+
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
from datetime import datetime, timezone

from app.websocket.handlers import (
    handle_websocket_connection, 
    handle_message, 
    handle_chat_message,
    handle_typing_indicator,
    handle_get_users,
    handle_notification_read,
    send_recent_messages
)
from app.models.message import MessageType, MessageStatus, MessageCreate
from fastapi import WebSocketDisconnect

UTC = timezone.utc


class TestWebSocketHandlersAdditional:
    """額外的 WebSocket handlers 測試"""
    
    @pytest.fixture
    def mock_websocket(self):
        """Mock WebSocket"""
        websocket = Mock()
        websocket.close = AsyncMock()
        websocket.receive_text = AsyncMock()
        websocket.send_text = AsyncMock()
        return websocket
    
    @pytest.fixture
    def mock_user_info(self):
        """Mock 用戶資訊"""
        return {
            "id": "user123",
            "username": "testuser",
            "email": "test@example.com"
        }
    
    @pytest.fixture
    def mock_message_service(self):
        """Mock MessageService"""
        service = Mock()
        service.create_message = AsyncMock()
        service.get_room_messages = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_room_service(self):
        """Mock RoomService"""
        service = Mock()
        service.get_room_members = AsyncMock()
        service.get_room_by_id = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_notification_service(self):
        """Mock NotificationService"""
        service = Mock()
        service.send_message_notification = AsyncMock()
        service.mark_as_read = AsyncMock()
        service.mark_room_notifications_as_read = AsyncMock()
        service.mark_all_as_read = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_container(self, mock_message_service, mock_room_service, mock_notification_service):
        """Mock Container"""
        container = Mock()
        container.get = AsyncMock()
        
        # 設置服務映射
        service_map = {
            'MessageService': mock_message_service,
            'RoomService': mock_room_service,
            'NotificationService': mock_notification_service
        }
        
        def get_side_effect(service_type, scope_id=None):
            service_name = service_type.__name__ if hasattr(service_type, '__name__') else str(service_type)
            return service_map.get(service_name, Mock())
        
        container.get.side_effect = get_side_effect
        
        # 正確設置 async context manager
        scope_context = AsyncMock()
        scope_context.__aenter__ = AsyncMock(return_value="test-scope")
        scope_context.__aexit__ = AsyncMock(return_value=None)
        container.scope = Mock(return_value=scope_context)
        
        return container
    
    @pytest.mark.asyncio
    async def test_handle_websocket_connection_auth_failed(self, mock_websocket):
        """測試 WebSocket 連線認證失敗"""
        with patch('app.websocket.handlers.websocket_auth_middleware') as mock_auth:
            mock_auth.return_value = None  # 認證失敗
            
            await handle_websocket_connection(mock_websocket, "room123")
            
            mock_websocket.close.assert_called_once_with(code=4001, reason="Authentication failed")
    
    @pytest.mark.asyncio
    async def test_handle_websocket_connection_success(self, mock_websocket, mock_user_info, mock_container):
        """測試 WebSocket 連線成功建立"""
        with patch('app.websocket.handlers.websocket_auth_middleware') as mock_auth, \
             patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.send_recent_messages') as mock_send_recent, \
             patch('app.websocket.handlers.get_container', return_value=mock_container):
            
            mock_auth.return_value = mock_user_info
            mock_cm.connect = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            mock_cm.disconnect = AsyncMock()
            mock_send_recent.return_value = AsyncMock()
            
            # 模擬 WebSocket 斷開連接
            mock_websocket.receive_text.side_effect = WebSocketDisconnect()
            
            await handle_websocket_connection(mock_websocket, "room123")
            
            # 驗證連線建立
            mock_cm.connect.assert_called_once_with(
                mock_websocket, "user123", "room123", mock_user_info
            )
            # 驗證歡迎訊息
            assert mock_cm.send_personal_message.call_count >= 1
            # 驗證清理連線
            mock_cm.disconnect.assert_called_once_with("user123", "room123")
    
    @pytest.mark.asyncio
    async def test_handle_websocket_connection_websocket_disconnect_exception(self, mock_websocket, mock_user_info, mock_container):
        """測試 WebSocket 連線過程中斷開連接的異常處理"""
        with patch('app.websocket.handlers.websocket_auth_middleware') as mock_auth, \
             patch('app.websocket.handlers.connection_manager') as mock_cm:
            
            mock_auth.return_value = mock_user_info
            mock_cm.connect = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            mock_cm.disconnect = AsyncMock()
            
            # 模擬在認證後的連接過程中立即斷開
            mock_websocket.receive_text.side_effect = WebSocketDisconnect()
            
            await handle_websocket_connection(mock_websocket, "room123")
            
            # 驗證清理連線
            mock_cm.disconnect.assert_called_once_with("user123", "room123")
    
    @pytest.mark.asyncio
    async def test_handle_websocket_connection_setup_exception(self, mock_websocket):
        """測試 WebSocket 連線建立過程中的異常"""
        with patch('app.websocket.handlers.websocket_auth_middleware') as mock_auth:
            # 認證過程中拋出異常
            mock_auth.side_effect = Exception("Auth service error")
            
            await handle_websocket_connection(mock_websocket, "room123")
            
            # 由於認證失敗，用戶 ID 為 None，不會調用 disconnect
            # 只是驗證函數能正常處理異常而不崩潰
    
    @pytest.mark.asyncio
    async def test_handle_message_chat_message(self, mock_user_info):
        """測試處理聊天訊息"""
        message_data = {
            "type": "chat_message",
            "content": "Hello world"
        }
        
        with patch('app.websocket.handlers.handle_chat_message') as mock_handle:
            mock_handle.return_value = AsyncMock()
            
            await handle_message("user123", "room123", message_data, mock_user_info, "scope123")
            
            mock_handle.assert_called_once_with("user123", "room123", message_data, mock_user_info, "scope123")
    
    @pytest.mark.asyncio
    async def test_handle_message_ping(self, mock_user_info):
        """測試處理 ping 訊息"""
        message_data = {"type": "ping"}
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm:
            mock_cm.handle_ping = AsyncMock()
            
            await handle_message("user123", "room123", message_data, mock_user_info)
            
            mock_cm.handle_ping.assert_called_once_with("user123", "room123")
    
    @pytest.mark.asyncio
    async def test_handle_message_typing(self, mock_user_info):
        """測試處理打字指示器"""
        message_data = {
            "type": "typing",
            "is_typing": True
        }
        
        with patch('app.websocket.handlers.handle_typing_indicator') as mock_handle:
            mock_handle.return_value = AsyncMock()
            
            await handle_message("user123", "room123", message_data, mock_user_info)
            
            mock_handle.assert_called_once_with("user123", "room123", message_data, mock_user_info)
    
    @pytest.mark.asyncio
    async def test_handle_message_get_users(self, mock_user_info):
        """測試處理獲取用戶列表"""
        message_data = {"type": "get_users"}
        
        with patch('app.websocket.handlers.handle_get_users') as mock_handle:
            mock_handle.return_value = AsyncMock()
            
            await handle_message("user123", "room123", message_data, mock_user_info)
            
            mock_handle.assert_called_once_with("user123", "room123")
    
    @pytest.mark.asyncio
    async def test_handle_message_notification_read(self, mock_user_info):
        """測試處理通知已讀"""
        message_data = {
            "type": "notification_read",
            "notification_id": "notif123"
        }
        
        with patch('app.websocket.handlers.handle_notification_read') as mock_handle:
            mock_handle.return_value = AsyncMock()
            
            await handle_message("user123", "room123", message_data, mock_user_info, "scope123")
            
            mock_handle.assert_called_once_with("user123", "room123", message_data, mock_user_info, "scope123")
    
    @pytest.mark.asyncio
    async def test_handle_message_unknown_type(self, mock_user_info):
        """測試處理未知訊息類型"""
        message_data = {"type": "unknown_type"}
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm:
            mock_cm.send_personal_message = AsyncMock()
            
            await handle_message("user123", "room123", message_data, mock_user_info)
            
            mock_cm.send_personal_message.assert_called_once()
            call_args = mock_cm.send_personal_message.call_args[0]
            assert call_args[2]["type"] == "error"
            assert "Unknown message type: unknown_type" in call_args[2]["message"]
    
    @pytest.mark.asyncio
    async def test_handle_chat_message_empty_content(self, mock_user_info):
        """測試處理空內容聊天訊息"""
        message_data = {
            "content": "",
            "temp_id": "temp123"
        }
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm:
            mock_cm.send_personal_message = AsyncMock()
            
            await handle_chat_message("user123", "room123", message_data, mock_user_info)
            
            mock_cm.send_personal_message.assert_called_once()
            call_args = mock_cm.send_personal_message.call_args[0]
            assert call_args[2]["type"] == "error"
            assert "訊息內容不能為空" in call_args[2]["message"]
            assert call_args[2]["temp_id"] == "temp123"
    
    @pytest.mark.asyncio
    async def test_handle_chat_message_content_too_long(self, mock_user_info):
        """測試處理內容過長的聊天訊息"""
        long_content = "x" * 1001  # 超過 1000 字符限制
        message_data = {
            "content": long_content,
            "message_type": "text",
            "temp_id": "temp123"
        }
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm:
            mock_cm.send_personal_message = AsyncMock()
            
            await handle_chat_message("user123", "room123", message_data, mock_user_info)
            
            mock_cm.send_personal_message.assert_called_once()
            call_args = mock_cm.send_personal_message.call_args[0]
            assert call_args[2]["type"] == "error"
            assert "訊息內容太長" in call_args[2]["message"]
            assert call_args[2]["temp_id"] == "temp123"
    
    @pytest.mark.asyncio
    async def test_handle_chat_message_image_type_long_content(self, mock_user_info):
        """測試處理圖片類型長內容（應該允許）"""
        long_content = "x" * 1500  # 1500 字符，對圖片類型應該允許
        message_data = {
            "content": long_content,
            "message_type": "image",
            "temp_id": "temp123"
        }
        
        mock_created_message = Mock()
        mock_created_message.id = "msg123"
        mock_created_message.room_id = "room123"
        mock_created_message.user_id = "user123"
        mock_created_message.content = long_content
        mock_created_message.message_type = MessageType.IMAGE
        mock_created_message.status = MessageStatus.SENT
        mock_created_message.created_at = datetime.now(UTC).isoformat()
        mock_created_message.metadata = None
        mock_created_message.username = "testuser"
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            mock_cm.broadcast_message = AsyncMock()
            
            mock_container = Mock()
            mock_message_service = Mock()
            mock_message_service.create_message = AsyncMock(return_value=mock_created_message)
            mock_container.get = AsyncMock(return_value=mock_message_service)
            mock_get_container.return_value = mock_container
            
            await handle_chat_message("user123", "room123", message_data, mock_user_info, "scope123")
            
            # 驗證訊息被創建和廣播，而不是發送錯誤
            mock_message_service.create_message.assert_called_once()
            mock_cm.broadcast_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_chat_message_success_with_notifications(self, mock_user_info, mock_container):
        """測試成功處理聊天訊息並發送通知"""
        message_data = {
            "content": "Hello world",
            "message_type": "text",
            "temp_id": "temp123",
            "metadata": {"key": "value"}
        }
        
        # Mock 創建的訊息
        mock_created_message = Mock()
        mock_created_message.id = "msg123"
        mock_created_message.room_id = "room123"
        mock_created_message.user_id = "user123"
        mock_created_message.content = "Hello world"
        mock_created_message.message_type = MessageType.TEXT
        mock_created_message.status = MessageStatus.SENT
        mock_created_message.created_at = datetime.now(UTC).isoformat()
        mock_created_message.metadata = {"key": "value"}
        mock_created_message.username = "testuser"
        
        # Mock 房間成員
        mock_member1 = Mock()
        mock_member1.id = "user456"
        mock_member2 = Mock()
        mock_member2.id = "user123"  # 發送者自己
        mock_members = [mock_member1, mock_member2]
        
        # Mock 房間資訊
        mock_room = Mock()
        mock_room.name = "Test Room"
        
        # 設置服務
        mock_message_service = Mock()
        mock_message_service.create_message = AsyncMock(return_value=mock_created_message)
        mock_room_service = Mock()
        mock_room_service.get_room_members = AsyncMock(return_value=mock_members)
        mock_room_service.get_room_by_id = AsyncMock(return_value=mock_room)
        mock_notification_service = Mock()
        mock_notification_service.send_message_notification = AsyncMock()
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            mock_cm.broadcast_message = AsyncMock()
            
            # 設置容器返回對應的服務
            mock_container = Mock()
            service_map = {
                'MessageService': mock_message_service,
                'RoomService': mock_room_service,
                'NotificationService': mock_notification_service
            }
            
            def get_side_effect(service_type, scope_id=None):
                service_name = service_type.__name__ if hasattr(service_type, '__name__') else str(service_type)
                return service_map.get(service_name, Mock())
            
            mock_container.get = AsyncMock(side_effect=get_side_effect)
            mock_get_container.return_value = mock_container
            
            await handle_chat_message("user123", "room123", message_data, mock_user_info, "scope123")
            
            # 驗證訊息創建
            mock_message_service.create_message.assert_called_once()
            create_call = mock_message_service.create_message.call_args[0]
            assert create_call[1].content == "Hello world"
            assert create_call[1].message_type == MessageType.TEXT
            
            # 驗證訊息廣播
            mock_cm.broadcast_message.assert_called_once()
            broadcast_call = mock_cm.broadcast_message.call_args[0]
            assert broadcast_call[0] == "room123"
            assert broadcast_call[1]["temp_id"] == "temp123"
            
            # 驗證通知發送（只給其他成員，不給自己）
            mock_notification_service.send_message_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_chat_message_service_error(self, mock_user_info):
        """測試聊天訊息服務錯誤"""
        message_data = {
            "content": "Hello world",
            "temp_id": "temp123"
        }
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            
            mock_container = Mock()
            mock_message_service = Mock()
            mock_message_service.create_message = AsyncMock(side_effect=Exception("Service error"))
            mock_container.get = AsyncMock(return_value=mock_message_service)
            mock_get_container.return_value = mock_container
            
            await handle_chat_message("user123", "room123", message_data, mock_user_info, "scope123")
            
            # 驗證發送錯誤訊息
            mock_cm.send_personal_message.assert_called_once()
            call_args = mock_cm.send_personal_message.call_args[0]
            assert call_args[2]["type"] == "error"
            assert "訊息發送失敗" in call_args[2]["message"]
            assert call_args[2]["temp_id"] == "temp123"
    
    @pytest.mark.asyncio
    async def test_handle_typing_indicator(self, mock_user_info):
        """測試處理打字指示器"""
        message_data = {"is_typing": True}
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm:
            mock_cm.broadcast_to_room = AsyncMock()
            
            await handle_typing_indicator("user123", "room123", message_data, mock_user_info)
            
            mock_cm.broadcast_to_room.assert_called_once()
            call_args = mock_cm.broadcast_to_room.call_args
            assert call_args[0][0] == "room123"
            assert call_args[0][1]["type"] == "typing"
            assert call_args[0][1]["is_typing"] is True
            assert call_args[1]["exclude_user"] == "user123"
    
    @pytest.mark.asyncio
    async def test_handle_get_users(self):
        """測試處理獲取用戶列表"""
        mock_users = [{"id": "user1", "username": "user1"}, {"id": "user2", "username": "user2"}]
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm:
            mock_cm.get_room_users.return_value = mock_users
            mock_cm.send_personal_message = AsyncMock()
            
            await handle_get_users("user123", "room123")
            
            mock_cm.get_room_users.assert_called_once_with("room123")
            mock_cm.send_personal_message.assert_called_once()
            call_args = mock_cm.send_personal_message.call_args[0]
            assert call_args[2]["type"] == "room_users"
            assert call_args[2]["users"] == mock_users
    
    @pytest.mark.asyncio
    async def test_handle_notification_read_single_notification(self, mock_user_info, mock_container):
        """測試處理單個通知已讀"""
        message_data = {
            "notification_id": "notif123",
            "read_type": "notification"
        }
        
        mock_notification_service = Mock()
        mock_notification_service.mark_as_read = AsyncMock(return_value=True)
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            mock_cm.send_notification = AsyncMock()
            
            mock_container = Mock()
            mock_container.get = AsyncMock(return_value=mock_notification_service)
            mock_get_container.return_value = mock_container
            
            await handle_notification_read("user123", "room123", message_data, mock_user_info, "scope123")
            
            # 驗證標記已讀
            mock_notification_service.mark_as_read.assert_called_once_with("notif123", "user123")
            
            # 驗證響應
            response_calls = [call for call in mock_cm.send_personal_message.call_args_list 
                            if call[0][2].get("type") == "read_status_response"]
            assert len(response_calls) == 1
            assert response_calls[0][0][2]["success"] is True
            
            # 驗證狀態廣播
            mock_cm.send_notification.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_notification_read_room_notifications(self, mock_user_info, mock_container):
        """測試處理房間通知已讀"""
        message_data = {
            "read_type": "room",
            "target_room_id": "room456"
        }
        
        mock_notification_service = Mock()
        mock_notification_service.mark_room_notifications_as_read = AsyncMock(return_value=5)
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            mock_cm.send_notification = AsyncMock()
            
            mock_container = Mock()
            mock_container.get = AsyncMock(return_value=mock_notification_service)
            mock_get_container.return_value = mock_container
            
            await handle_notification_read("user123", "room123", message_data, mock_user_info, "scope123")
            
            # 驗證標記房間通知已讀
            mock_notification_service.mark_room_notifications_as_read.assert_called_once_with("user123", "room456")
            
            # 驗證響應
            response_calls = [call for call in mock_cm.send_personal_message.call_args_list 
                            if call[0][2].get("type") == "read_status_response"]
            assert len(response_calls) == 1
            assert response_calls[0][0][2]["success"] is True
    
    @pytest.mark.asyncio
    async def test_handle_notification_read_all_notifications(self, mock_user_info, mock_container):
        """測試處理所有通知已讀"""
        message_data = {"read_type": "all"}
        
        mock_notification_service = Mock()
        mock_notification_service.mark_all_as_read = AsyncMock(return_value=10)
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            mock_cm.send_notification = AsyncMock()
            
            mock_container = Mock()
            mock_container.get = AsyncMock(return_value=mock_notification_service)
            mock_get_container.return_value = mock_container
            
            await handle_notification_read("user123", "room123", message_data, mock_user_info, "scope123")
            
            # 驗證標記所有通知已讀
            mock_notification_service.mark_all_as_read.assert_called_once_with("user123")
            
            # 驗證響應
            response_calls = [call for call in mock_cm.send_personal_message.call_args_list 
                            if call[0][2].get("type") == "read_status_response"]
            assert len(response_calls) == 1
            assert response_calls[0][0][2]["success"] is True
    
    @pytest.mark.asyncio
    async def test_handle_notification_read_service_error(self, mock_user_info, mock_container):
        """測試處理通知已讀服務錯誤"""
        message_data = {
            "notification_id": "notif123",
            "read_type": "notification"
        }
        
        mock_notification_service = Mock()
        mock_notification_service.mark_as_read = AsyncMock(side_effect=Exception("Service error"))
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            
            mock_container = Mock()
            mock_container.get = AsyncMock(return_value=mock_notification_service)
            mock_get_container.return_value = mock_container
            
            await handle_notification_read("user123", "room123", message_data, mock_user_info, "scope123")
            
            # 驗證發送錯誤響應
            error_calls = [call for call in mock_cm.send_personal_message.call_args_list 
                          if call[0][2].get("type") == "read_status_response" and not call[0][2].get("success")]
            assert len(error_calls) == 1
            assert error_calls[0][0][2]["error"] == "系統錯誤"
    
    @pytest.mark.asyncio
    async def test_send_recent_messages_success(self):
        """測試成功發送最近訊息"""
        # Mock 訊息
        mock_message = Mock()
        mock_message.id = "msg123"
        mock_message.content = "Hello"
        mock_message.message_type = MessageType.TEXT
        mock_message.status = MessageStatus.SENT
        mock_message.created_at = datetime.now(UTC).isoformat()
        mock_message.user_id = "user456"
        mock_message.username = "sender"
        
        mock_messages = [mock_message]
        
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            
            mock_container = Mock()
            mock_message_service = Mock()
            mock_message_service.get_room_messages = AsyncMock(return_value=mock_messages)
            mock_container.get = AsyncMock(return_value=mock_message_service)
            mock_get_container.return_value = mock_container
            
            await send_recent_messages("user123", "room123", 50)
            
            # 驗證獲取訊息
            mock_message_service.get_room_messages.assert_called_once_with(
                room_id="room123", skip=0, limit=50
            )
            
            # 驗證發送歷史訊息
            mock_cm.send_personal_message.assert_called_once()
            call_args = mock_cm.send_personal_message.call_args[0]
            assert call_args[2]["type"] == "message_history"
            assert len(call_args[2]["messages"]) == 1
            assert call_args[2]["messages"][0]["id"] == "msg123"
    
    @pytest.mark.asyncio
    async def test_send_recent_messages_service_error(self):
        """測試發送最近訊息服務錯誤"""
        with patch('app.websocket.handlers.connection_manager') as mock_cm, \
             patch('app.websocket.handlers.get_container') as mock_get_container:
            
            mock_cm.send_personal_message = AsyncMock()
            
            mock_container = Mock()
            mock_message_service = Mock()
            mock_message_service.get_room_messages = AsyncMock(side_effect=Exception("Service error"))
            mock_container.get = AsyncMock(return_value=mock_message_service)
            mock_get_container.return_value = mock_container
            
            await send_recent_messages("user123", "room123", 50)
            
            # 驗證發送錯誤訊息
            mock_cm.send_personal_message.assert_called_once()
            call_args = mock_cm.send_personal_message.call_args[0]
            assert call_args[2]["type"] == "error"
            assert "無法載入歷史訊息" in call_args[2]["message"]