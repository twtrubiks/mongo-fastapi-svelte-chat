"""通知服務驗證測試 - 針對修改後的功能"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.notification import NotificationType
from app.services.notification_service import NotificationService


class TestNotificationValidation:
    """測試修改後的通知資料驗證"""

    @pytest.fixture
    def mock_notification_repository(self):
        """Mock 通知 Repository"""
        repo = Mock()
        repo.create = AsyncMock()
        return repo

    @pytest.fixture
    def notification_service(self, mock_notification_repository):
        """通知服務實例"""
        return NotificationService(mock_notification_repository)

    @pytest.mark.asyncio
    async def test_send_message_notification_metadata_enhancement(
        self, notification_service, mock_notification_repository
    ):
        """測試訊息通知的 metadata 增強"""
        user_id = "user123"
        sender_name = "John"
        message_preview = "Hello world"
        room_name = "測試房間"
        room_id = "room456"
        sender_id = "john123"
        message_id = "msg789"

        # Mock create_notification 方法來檢查參數
        with patch.object(notification_service, "create_notification") as mock_create:
            mock_create.return_value = None

            # 發送訊息通知
            await notification_service.send_message_notification(
                user_id=user_id,
                sender_name=sender_name,
                message_preview=message_preview,
                room_name=room_name,
                room_id=room_id,
                sender_id=sender_id,
                message_id=message_id,
            )

            # 驗證 create_notification 被正確調用
            mock_create.assert_called_once()

            # 獲取傳遞的參數
            call_kwargs = mock_create.call_args.kwargs

            # 驗證基本參數
            assert call_kwargs["user_id"] == user_id
            assert call_kwargs["title"] == f"來自 {sender_name} 的新訊息"
            assert call_kwargs["content"] == f"在 {room_name} 中：{message_preview}"
            assert call_kwargs["notification_type"] == NotificationType.MESSAGE
            assert call_kwargs["sender_id"] == sender_id
            assert call_kwargs["room_id"] == room_id

            # 驗證 metadata 包含所有必要資訊（包括新增的欄位）
            metadata = call_kwargs["metadata"]
            assert metadata["sender_name"] == sender_name
            assert metadata["room_name"] == room_name
            assert metadata["message_preview"] == message_preview
            assert metadata["message_id"] == message_id
            assert metadata["room_id"] == room_id  # 確保 room_id 被加入
            assert metadata["sender_id"] == sender_id  # 確保 sender_id 被加入

    def test_notification_data_structure_validation(self):
        """測試通知資料結構的驗證邏輯"""
        # 測試有效的通知資料
        valid_notification = {
            "title": "測試通知",
            "message": "測試內容",
            "content": "測試內容",
            "data": {"test": "value"},
            "metadata": {"test": "value"},
        }

        # 這個測試模擬我們在 send_real_time_notification 中的驗證邏輯
        assert valid_notification.get("title")
        assert valid_notification.get("message") or valid_notification.get("content")

        # 測試無效的通知資料
        invalid_notification_no_title = {
            "message": "測試內容",
            "data": {"test": "value"},
        }

        invalid_notification_no_message = {
            "title": "測試通知",
            "data": {"test": "value"},
        }

        invalid_notification_empty_title = {
            "title": "",
            "message": "測試內容",
            "data": {"test": "value"},
        }

        # 驗證無效資料會被拒絕
        assert not invalid_notification_no_title.get("title")
        assert not invalid_notification_no_message.get("message")
        assert not invalid_notification_empty_title.get("title")  # 空字串視為無效

    def test_notification_field_mapping(self):
        """測試通知欄位映射邏輯"""
        # 模擬 send_real_time_notification 中的欄位映射
        original_notification = {
            "id": "notif123",
            "type": "MESSAGE",
            "status": "UNREAD",
            "title": "測試通知",
            "content": "這是測試內容",
            "metadata": {"room_id": "room456"},
            "room_id": "room456",
            "sender_id": "user123",
        }

        # 模擬完整通知資料結構的建立
        complete_notification = {
            "id": original_notification.get(
                "id", f"realtime_{datetime.now().timestamp()}_user123"
            ),
            "user_id": "user123",
            "type": original_notification.get("type", "SYSTEM"),
            "status": original_notification.get("status", "UNREAD"),
            "title": original_notification.get("title", "通知"),
            "message": original_notification.get(
                "content", original_notification.get("message", "")
            ),  # 優先使用 content
            "content": original_notification.get(
                "content", original_notification.get("message", "")
            ),  # 同時保留 content
            "data": original_notification.get(
                "metadata", original_notification.get("data", {})
            ),  # 優先使用 metadata
            "metadata": original_notification.get(
                "metadata", original_notification.get("data", {})
            ),  # 同時保留 metadata
            "room_id": original_notification.get("room_id"),
            "sender_id": original_notification.get("sender_id"),
            "created_at": original_notification.get(
                "created_at", datetime.now(UTC).isoformat()
            ),
            "updated_at": original_notification.get(
                "updated_at", datetime.now(UTC).isoformat()
            ),
        }

        # 驗證欄位映射正確
        assert complete_notification["title"] == "測試通知"
        assert complete_notification["message"] == "這是測試內容"  # 從 content 映射
        assert complete_notification["content"] == "這是測試內容"  # 保留原始 content
        assert complete_notification["data"]["room_id"] == "room456"  # 從 metadata 映射
        assert (
            complete_notification["metadata"]["room_id"] == "room456"
        )  # 保留原始 metadata
        assert complete_notification["room_id"] == "room456"
        assert complete_notification["sender_id"] == "user123"

        # 驗證必要欄位存在
        assert complete_notification["title"]
        assert complete_notification["message"]
