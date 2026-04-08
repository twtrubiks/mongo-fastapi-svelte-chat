"""MongoDB 索引建立測試"""

from unittest.mock import AsyncMock, Mock

import pytest

from app.database.indexes import ensure_indexes


@pytest.mark.asyncio
@pytest.mark.unit
class TestEnsureIndexes:
    """測試 ensure_indexes 函數"""

    async def test_creates_all_indexes(self):
        """測試建立所有 collection 的索引"""
        # 準備 mock collections
        mock_users = Mock()
        mock_users.create_index = AsyncMock()

        mock_messages = Mock()
        mock_messages.create_index = AsyncMock()

        mock_rooms = Mock()
        mock_rooms.create_index = AsyncMock()

        mock_notifications = Mock()
        mock_notifications.create_index = AsyncMock()

        mock_invitations = Mock()
        mock_invitations.create_index = AsyncMock()

        mock_db = Mock()
        mock_db.__getitem__ = Mock(
            side_effect=lambda name: {
                "users": mock_users,
                "messages": mock_messages,
                "rooms": mock_rooms,
                "notifications": mock_notifications,
                "room_invitations": mock_invitations,
            }[name]
        )

        await ensure_indexes(mock_db)

        # users：username unique + email unique
        assert mock_users.create_index.call_count == 2
        # messages：room_id + created_at 複合索引
        assert mock_messages.create_index.call_count == 1
        # rooms：members 索引 + is_public+created_at 複合索引
        assert mock_rooms.create_index.call_count == 2
        # notifications：user_id + created_at 複合索引
        assert mock_notifications.create_index.call_count == 1
        # room_invitations：invite_code unique
        assert mock_invitations.create_index.call_count == 1

    async def test_users_unique_indexes(self):
        """測試 users collection 的唯一索引"""
        mock_users = Mock()
        mock_users.create_index = AsyncMock()
        mock_other = Mock()
        mock_other.create_index = AsyncMock()

        mock_db = Mock()
        mock_db.__getitem__ = Mock(
            side_effect=lambda name: mock_users if name == "users" else mock_other
        )

        await ensure_indexes(mock_db)

        # 檢查 users 的兩個索引都有 unique=True
        assert mock_users.create_index.call_count == 2
        for call in mock_users.create_index.call_args_list:
            assert call.kwargs.get("unique") is True

    async def test_invitations_unique_index(self):
        """測試 room_invitations collection 的唯一索引"""
        mock_collection = Mock()
        mock_collection.create_index = AsyncMock()

        mock_db = Mock()
        mock_db.__getitem__ = Mock(return_value=mock_collection)

        await ensure_indexes(mock_db)

        # 找到 room_invitations 的呼叫（invite_code）
        invitations_calls = [
            c
            for c in mock_collection.create_index.call_args_list
            if any("invite_code" in str(arg) for arg in c.args)
        ]
        assert len(invitations_calls) == 1
        assert invitations_calls[0].kwargs.get("unique") is True
