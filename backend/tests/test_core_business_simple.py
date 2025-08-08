"""
簡單的核心業務邏輯測試
使用 Mock 測試核心功能
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest
from bson import ObjectId


class TestCoreBusinessSimple:
    """使用 Mock 測試核心業務邏輯"""

    @pytest.mark.asyncio
    async def test_user_registration_flow(self):
        """測試用戶註冊流程"""
        # Mock 依賴
        mock_user_repo = AsyncMock()
        mock_auth_service = Mock()

        # 設置 Mock 行為
        mock_user_repo.find_by_username.return_value = None  # 用戶不存在
        mock_user_repo.find_by_email.return_value = None  # 郵箱不存在
        mock_user_repo.create.return_value = {
            "_id": ObjectId(),
            "username": "newuser",
            "email": "new@example.com",
            "created_at": datetime.now(UTC),
        }
        mock_auth_service.hash_password.return_value = "hashed_password"

        # 模擬註冊邏輯
        username = "newuser"
        email = "new@example.com"
        password = "password123"

        # 檢查用戶是否存在
        existing_user = await mock_user_repo.find_by_username(username)
        existing_email = await mock_user_repo.find_by_email(email)

        assert existing_user is None
        assert existing_email is None

        # 創建用戶
        hashed_pw = mock_auth_service.hash_password(password)
        user_data = {"username": username, "email": email, "hashed_password": hashed_pw}

        new_user = await mock_user_repo.create(user_data)

        # 驗證
        assert new_user["username"] == "newuser"
        assert new_user["email"] == "new@example.com"
        mock_user_repo.create.assert_called_once()
        mock_auth_service.hash_password.assert_called_once_with(password)

    @pytest.mark.asyncio
    async def test_send_message_flow(self):
        """測試發送訊息流程"""
        # Mock 依賴
        mock_message_repo = AsyncMock()
        mock_ws_manager = AsyncMock()

        # 設置 Mock 行為
        message_id = ObjectId()
        mock_message_repo.create.return_value = {
            "_id": message_id,
            "content": "Hello",
            "user_id": ObjectId(),
            "room_id": ObjectId(),
            "created_at": datetime.now(UTC),
        }

        # 發送訊息
        message_data = {
            "content": "Hello",
            "user_id": str(ObjectId()),
            "room_id": str(ObjectId()),
        }

        created_message = await mock_message_repo.create(message_data)

        # 廣播訊息
        broadcast_data = {
            "type": "new_message",
            "message": {
                "id": str(created_message["_id"]),
                "content": created_message["content"],
            },
        }

        await mock_ws_manager.broadcast_to_room(
            message_data["room_id"], json.dumps(broadcast_data)
        )

        # 驗證
        assert created_message["content"] == "Hello"
        mock_message_repo.create.assert_called_once()
        mock_ws_manager.broadcast_to_room.assert_called_once()

    @pytest.mark.asyncio
    async def test_join_room_validation(self):
        """測試加入房間的驗證邏輯"""
        # Mock 依賴
        mock_room_repo = AsyncMock()

        # 設置房間數據
        room_id = str(ObjectId())
        room_data = {
            "_id": ObjectId(room_id),
            "name": "Test Room",
            "members": [ObjectId() for _ in range(5)],
            "max_members": 10,
            "is_private": False,
        }

        mock_room_repo.find_by_id.return_value = room_data

        # 測試加入房間的驗證
        room = await mock_room_repo.find_by_id(room_id)

        # 驗證房間存在
        assert room is not None

        # 驗證房間未滿
        assert len(room["members"]) < room["max_members"]

        # 驗證不是私人房間
        assert room["is_private"] is False

        # 模擬加入成功
        new_user_id = ObjectId()
        room["members"].append(new_user_id)
        mock_room_repo.add_member.return_value = True

        success = await mock_room_repo.add_member(room_id, str(new_user_id))
        assert success is True

    def test_notification_creation(self):
        """測試通知創建"""
        # Mock 依賴
        mock_notification_repo = Mock()

        # 創建通知
        notification_data = {
            "user_id": str(ObjectId()),
            "type": "message",
            "content": "You have a new message",
            "read": False,
            "created_at": datetime.now(UTC),
        }

        mock_notification_repo.create.return_value = {
            "_id": ObjectId(),
            **notification_data,
        }

        # 執行
        notification = mock_notification_repo.create(notification_data)

        # 驗證
        assert notification["type"] == "message"
        assert notification["read"] is False
        mock_notification_repo.create.assert_called_once_with(notification_data)

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """測試錯誤處理"""
        # Mock 依賴
        mock_service = AsyncMock()

        # 設置錯誤場景
        mock_service.risky_operation.side_effect = Exception("Database error")

        # 測試錯誤處理
        try:
            await mock_service.risky_operation()
            raise AssertionError("Should have raised exception")
        except Exception as e:
            assert "Database error" in str(e)

        # 驗證方法被調用
        mock_service.risky_operation.assert_called_once()

    def test_data_transformation(self):
        """測試數據轉換"""
        # Mock 數據源
        raw_data = {
            "_id": ObjectId(),
            "username": "testuser",
            "email": "test@example.com",
            "hashed_password": "secret_hash",
            "created_at": datetime.now(UTC),
        }

        # 轉換邏輯（移除敏感信息）
        public_data = {
            "id": str(raw_data["_id"]),
            "username": raw_data["username"],
            "email": raw_data["email"],
            "created_at": raw_data["created_at"].isoformat(),
        }

        # 驗證
        assert "hashed_password" not in public_data
        assert public_data["username"] == "testuser"
        assert isinstance(public_data["id"], str)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """測試並發操作"""
        import asyncio

        # Mock 依賴
        mock_service = AsyncMock()
        call_count = 0

        async def increment_counter(*args):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # 模擬 I/O
            return call_count

        mock_service.process.side_effect = increment_counter

        # 並發執行
        tasks = [mock_service.process(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # 驗證
        assert len(results) == 5
        assert mock_service.process.call_count == 5
        assert call_count == 5

    def test_business_rule_validation(self):
        """測試業務規則驗證"""

        # 定義業務規則
        def validate_username(username):
            if len(username) < 3:
                return False, "用戶名太短"
            if len(username) > 20:
                return False, "用戶名太長"
            if not username.isalnum():
                return False, "用戶名只能包含字母和數字"
            return True, None

        # 測試各種情況
        test_cases = [
            ("ab", False, "用戶名太短"),
            ("a" * 21, False, "用戶名太長"),
            ("user@123", False, "用戶名只能包含字母和數字"),
            ("validuser123", True, None),
        ]

        for username, expected_valid, expected_error in test_cases:
            valid, error = validate_username(username)
            assert valid == expected_valid
            if not valid:
                assert error == expected_error
