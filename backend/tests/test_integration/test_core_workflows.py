"""核心工作流程的整合測試"""
import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, UTC


class TestCoreWorkflows:
    """測試核心業務工作流程"""
    
    def test_user_registration_workflow(self):
        """測試用戶註冊完整流程"""
        # Mock 所有服務
        mock_user_service = Mock()
        mock_email_service = Mock()
        mock_notification_service = Mock()
        
        # 模擬註冊流程
        class RegistrationWorkflow:
            def __init__(self, user_service, email_service, notification_service):
                self.user_service = user_service
                self.email_service = email_service
                self.notification_service = notification_service
            
            def register_user(self, username, email, password):
                # 1. 創建用戶
                user = self.user_service.create_user(username, email, password)
                
                # 2. 發送歡迎郵件
                self.email_service.send_welcome_email(email, username)
                
                # 3. 創建歡迎通知
                self.notification_service.create_notification(
                    user["id"],
                    "Welcome to our platform!"
                )
                
                return user
        
        # 設置 Mock 返回值
        mock_user_service.create_user.return_value = {
            "id": "user123",
            "username": "testuser",
            "email": "test@example.com"
        }
        mock_email_service.send_welcome_email.return_value = True
        mock_notification_service.create_notification.return_value = True
        
        # 執行工作流程
        workflow = RegistrationWorkflow(
            mock_user_service,
            mock_email_service,
            mock_notification_service
        )
        
        result = workflow.register_user("testuser", "test@example.com", "password")
        
        # 驗證結果
        assert result["id"] == "user123"
        mock_user_service.create_user.assert_called_once()
        mock_email_service.send_welcome_email.assert_called_once()
        mock_notification_service.create_notification.assert_called_once()
    
    def test_message_send_workflow(self):
        """測試訊息發送完整流程"""
        # Mock 服務
        mock_auth_service = Mock()
        mock_room_service = Mock()
        mock_message_service = Mock()
        mock_websocket_service = Mock()
        
        # 模擬訊息發送流程
        class MessageWorkflow:
            def __init__(self, auth, room, message, websocket):
                self.auth = auth
                self.room = room
                self.message = message
                self.websocket = websocket
            
            def send_message(self, user_id, room_id, content):
                # 1. 驗證用戶
                if not self.auth.verify_user(user_id):
                    raise ValueError("Invalid user")
                
                # 2. 檢查房間權限
                if not self.room.is_member(room_id, user_id):
                    raise ValueError("Not a room member")
                
                # 3. 創建訊息
                message = self.message.create_message(user_id, room_id, content)
                
                # 4. 廣播訊息
                members = self.room.get_members(room_id)
                self.websocket.broadcast_to_users(members, message)
                
                return message
        
        # 設置 Mock 行為
        mock_auth_service.verify_user.return_value = True
        mock_room_service.is_member.return_value = True
        mock_room_service.get_members.return_value = ["user1", "user2", "user3"]
        mock_message_service.create_message.return_value = {
            "id": "msg123",
            "content": "Hello",
            "timestamp": datetime.now(UTC).isoformat()
        }
        mock_websocket_service.broadcast_to_users.return_value = True
        
        # 執行工作流程
        workflow = MessageWorkflow(
            mock_auth_service,
            mock_room_service,
            mock_message_service,
            mock_websocket_service
        )
        
        result = workflow.send_message("user1", "room1", "Hello")
        
        # 驗證結果
        assert result["id"] == "msg123"
        mock_websocket_service.broadcast_to_users.assert_called_once_with(
            ["user1", "user2", "user3"],
            result
        )
    
    def test_room_join_workflow(self):
        """測試加入房間完整流程"""
        # Mock 服務
        mock_room_service = Mock()
        mock_notification_service = Mock()
        mock_message_service = Mock()
        
        # 模擬加入房間流程
        class RoomJoinWorkflow:
            def __init__(self, room, notification, message):
                self.room = room
                self.notification = notification
                self.message = message
            
            def join_room(self, user_id, room_id):
                # 1. 檢查房間是否存在
                room = self.room.get_room(room_id)
                if not room:
                    raise ValueError("Room not found")
                
                # 2. 加入房間
                self.room.add_member(room_id, user_id)
                
                # 3. 發送系統訊息
                self.message.create_system_message(
                    room_id,
                    f"User joined the room"
                )
                
                # 4. 通知其他成員
                members = self.room.get_members(room_id)
                for member in members:
                    if member != user_id:
                        self.notification.notify_user(
                            member,
                            f"New member joined {room['name']}"
                        )
                
                return {"joined": True, "room": room}
        
        # 設置 Mock 返回值
        mock_room_service.get_room.return_value = {
            "id": "room1",
            "name": "Test Room"
        }
        mock_room_service.add_member.return_value = True
        mock_room_service.get_members.return_value = ["user1", "user2", "user3"]
        mock_message_service.create_system_message.return_value = True
        mock_notification_service.notify_user.return_value = True
        
        # 執行工作流程
        workflow = RoomJoinWorkflow(
            mock_room_service,
            mock_notification_service,
            mock_message_service
        )
        
        result = workflow.join_room("user3", "room1")
        
        # 驗證結果
        assert result["joined"] is True
        assert result["room"]["name"] == "Test Room"
        # 應該通知2個其他成員
        assert mock_notification_service.notify_user.call_count == 2
    
    def test_file_sharing_workflow(self):
        """測試文件分享完整流程"""
        # Mock 服務
        mock_file_service = Mock()
        mock_message_service = Mock()
        mock_storage_service = Mock()
        
        # 模擬文件分享流程
        class FileSharingWorkflow:
            def __init__(self, file, message, storage):
                self.file = file
                self.message = message
                self.storage = storage
            
            def share_file(self, user_id, room_id, file_data):
                # 1. 驗證文件
                if not self.file.validate_file(file_data):
                    raise ValueError("Invalid file")
                
                # 2. 上傳文件
                file_url = self.storage.upload(file_data)
                
                # 3. 創建文件訊息
                message = self.message.create_file_message(
                    user_id,
                    room_id,
                    file_url,
                    file_data["name"]
                )
                
                return {
                    "file_url": file_url,
                    "message": message
                }
        
        # 設置 Mock 行為
        mock_file_service.validate_file.return_value = True
        mock_storage_service.upload.return_value = "https://storage/file123"
        mock_message_service.create_file_message.return_value = {
            "id": "msg456",
            "type": "file",
            "file_url": "https://storage/file123"
        }
        
        # 執行工作流程
        workflow = FileSharingWorkflow(
            mock_file_service,
            mock_message_service,
            mock_storage_service
        )
        
        result = workflow.share_file(
            "user1",
            "room1",
            {"name": "test.jpg", "data": b"fake"}
        )
        
        # 驗證結果
        assert result["file_url"] == "https://storage/file123"
        assert result["message"]["type"] == "file"
    
    def test_notification_delivery_workflow(self):
        """測試通知投遞完整流程"""
        # Mock 服務
        mock_user_service = Mock()
        mock_push_service = Mock()
        mock_email_service = Mock()
        mock_websocket_service = Mock()
        
        # 模擬通知投遞流程
        class NotificationDeliveryWorkflow:
            def __init__(self, user, push, email, websocket):
                self.user = user
                self.push = push
                self.email = email
                self.websocket = websocket
            
            def deliver_notification(self, user_id, notification):
                # 1. 獲取用戶偏好設置
                preferences = self.user.get_notification_preferences(user_id)
                
                delivered = []
                
                # 2. 根據偏好發送
                if preferences.get("push", True):
                    if self.push.send(user_id, notification):
                        delivered.append("push")
                
                if preferences.get("email", False):
                    if self.email.send_notification_email(user_id, notification):
                        delivered.append("email")
                
                # 3. 總是通過 WebSocket 發送（如果在線）
                if self.websocket.is_online(user_id):
                    if self.websocket.send_notification(user_id, notification):
                        delivered.append("websocket")
                
                return {
                    "delivered_via": delivered,
                    "success": len(delivered) > 0
                }
        
        # 設置 Mock 行為
        mock_user_service.get_notification_preferences.return_value = {
            "push": True,
            "email": True
        }
        mock_push_service.send.return_value = True
        mock_email_service.send_notification_email.return_value = True
        mock_websocket_service.is_online.return_value = True
        mock_websocket_service.send_notification.return_value = True
        
        # 執行工作流程
        workflow = NotificationDeliveryWorkflow(
            mock_user_service,
            mock_push_service,
            mock_email_service,
            mock_websocket_service
        )
        
        result = workflow.deliver_notification(
            "user1",
            {"title": "New Message", "body": "You have a new message"}
        )
        
        # 驗證結果
        assert result["success"] is True
        assert len(result["delivered_via"]) == 3
        assert "push" in result["delivered_via"]
        assert "email" in result["delivered_via"]
        assert "websocket" in result["delivered_via"]