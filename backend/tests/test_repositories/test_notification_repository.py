"""通知 Repository 測試"""

from unittest.mock import patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.models.notification import (
    NotificationCreate,
    NotificationInDB,
    NotificationStatus,
    NotificationType,
    NotificationUpdate,
)
from app.repositories.notification_repository import NotificationRepository


async def _create_notification(repo, notification_data):
    """輔助函式：透過 create 建立單筆通知並返回 NotificationInDB"""
    notification_in_db = NotificationInDB(**notification_data.model_dump())
    return await repo.create(notification_in_db)


@pytest.mark.unit
class TestNotificationRepository:
    """通知 Repository 整合測試類別"""

    @pytest.mark.asyncio
    async def test_create_notification(self, db_manager):
        """測試創建通知"""
        repo = NotificationRepository(db_manager.database)

        # 創建通知資料
        notification_data = NotificationCreate(
            user_id=str(ObjectId()),
            title="測試通知",
            content="這是一個測試通知",
            type=NotificationType.MESSAGE,
            sender_id=str(ObjectId()),
            room_id=str(ObjectId()),
        )

        # 執行創建
        result = await _create_notification(repo, notification_data)

        # 驗證結果
        assert result is not None
        assert result.id is not None
        assert result.user_id == notification_data.user_id
        assert result.title == "測試通知"
        assert result.content == "這是一個測試通知"
        assert result.type == NotificationType.MESSAGE
        assert result.status == NotificationStatus.UNREAD
        assert result.read_at is None

    @pytest.mark.asyncio
    async def test_get_by_user(self, db_manager):
        """測試根據用戶獲取通知"""
        repo = NotificationRepository(db_manager.database)
        user_id = str(ObjectId())

        # 創建多個通知
        notifications = [
            NotificationCreate(
                user_id=user_id,
                title=f"通知 {i}",
                content=f"內容 {i}",
                type=(
                    NotificationType.MESSAGE if i % 2 == 0 else NotificationType.SYSTEM
                ),
            )
            for i in range(5)
        ]

        for notification in notifications:
            await _create_notification(repo, notification)

        # 獲取用戶的所有通知
        user_notifications = await repo.get_by_user(user_id)

        # 驗證結果
        assert len(user_notifications) >= 5
        assert all(notif.user_id == user_id for notif in user_notifications)

        # 測試按類型篩選
        message_notifications = await repo.get_by_user(
            user_id, notification_type=NotificationType.MESSAGE
        )
        assert len(message_notifications) >= 3  # 應該有 3 個 MESSAGE 類型
        assert all(
            notif.type == NotificationType.MESSAGE for notif in message_notifications
        )

    @pytest.mark.asyncio
    async def test_get_by_user_with_status_filter(self, db_manager):
        """測試根據狀態篩選用戶通知"""
        repo = NotificationRepository(db_manager.database)
        user_id = str(ObjectId())

        # 創建不同狀態的通知
        notification1 = NotificationCreate(
            user_id=user_id,
            title="未讀通知",
            content="未讀內容",
            type=NotificationType.MESSAGE,
        )

        notification2 = NotificationCreate(
            user_id=user_id,
            title="已讀通知",
            content="已讀內容",
            type=NotificationType.MESSAGE,
            status=NotificationStatus.READ,
        )

        await _create_notification(repo, notification1)
        await _create_notification(repo, notification2)

        # 測試獲取未讀通知
        unread_notifications = await repo.get_by_user(
            user_id, status=NotificationStatus.UNREAD
        )
        assert len(unread_notifications) >= 1
        assert all(
            notif.status == NotificationStatus.UNREAD for notif in unread_notifications
        )

        # 測試獲取已讀通知
        read_notifications = await repo.get_by_user(
            user_id, status=NotificationStatus.READ
        )
        assert len(read_notifications) >= 1
        assert all(
            notif.status == NotificationStatus.READ for notif in read_notifications
        )

    @pytest.mark.asyncio
    async def test_get_unread_count(self, db_manager):
        """測試獲取未讀通知數量"""
        repo = NotificationRepository(db_manager.database)
        user_id = str(ObjectId())

        # 初始未讀數應該為 0
        initial_count = await repo.get_unread_count(user_id)
        assert initial_count == 0

        # 創建 3 個未讀通知
        for i in range(3):
            notification = NotificationCreate(
                user_id=user_id,
                title=f"未讀通知 {i}",
                content=f"內容 {i}",
                type=NotificationType.MESSAGE,
            )
            await _create_notification(repo, notification)

        # 驗證未讀數量
        unread_count = await repo.get_unread_count(user_id)
        assert unread_count >= 3

        # 創建 1 個已讀通知
        read_notification = NotificationCreate(
            user_id=user_id,
            title="已讀通知",
            content="已讀內容",
            type=NotificationType.MESSAGE,
            status=NotificationStatus.READ,
        )
        await _create_notification(repo, read_notification)

        # 未讀數量應該保持不變
        unread_count_after = await repo.get_unread_count(user_id)
        assert unread_count_after >= 3

    @pytest.mark.asyncio
    async def test_update_notification(self, db_manager):
        """測試更新通知"""
        repo = NotificationRepository(db_manager.database)

        # 創建通知
        notification = NotificationCreate(
            user_id=str(ObjectId()),
            title="原始標題",
            content="原始內容",
            type=NotificationType.MESSAGE,
        )

        created_notification = await _create_notification(repo, notification)
        assert created_notification is not None

        # 更新通知
        update_data = NotificationUpdate(
            title="更新後標題", content="更新後內容", status=NotificationStatus.READ
        )

        updated_notification = await repo.update(created_notification.id, update_data)

        # 驗證結果
        assert updated_notification is not None
        assert updated_notification.id == created_notification.id
        assert updated_notification.title == "更新後標題"
        assert updated_notification.content == "更新後內容"
        assert updated_notification.status == NotificationStatus.READ
        assert updated_notification.updated_at >= created_notification.updated_at

    @pytest.mark.asyncio
    async def test_update_nonexistent_notification(self, db_manager):
        """測試更新不存在的通知"""
        repo = NotificationRepository(db_manager.database)

        # 嘗試更新不存在的通知
        non_existent_id = str(ObjectId())
        update_data = NotificationUpdate(title="新標題")
        result = await repo.update(non_existent_id, update_data)

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_notification(self, db_manager):
        """測試刪除通知"""
        repo = NotificationRepository(db_manager.database)

        # 創建通知
        notification = NotificationCreate(
            user_id=str(ObjectId()),
            title="待刪除通知",
            content="待刪除內容",
            type=NotificationType.MESSAGE,
        )

        created_notification = await _create_notification(repo, notification)
        assert created_notification is not None

        # 刪除通知
        success = await repo.delete_by_id(created_notification.id)
        assert success is True

        # 驗證通知已被刪除
        deleted_notification = await repo.get_by_id(created_notification.id)
        assert deleted_notification is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_notification(self, db_manager):
        """測試刪除不存在的通知"""
        repo = NotificationRepository(db_manager.database)

        # 嘗試刪除不存在的通知
        non_existent_id = str(ObjectId())
        result = await repo.delete_by_id(non_existent_id)

        # 驗證結果
        assert result is False

    @pytest.mark.asyncio
    async def test_get_stats(self, db_manager):
        """測試獲取通知統計"""
        repo = NotificationRepository(db_manager.database)
        user_id = str(ObjectId())

        # 創建不同類型和狀態的通知
        notifications = [
            NotificationCreate(
                user_id=user_id,
                title="MESSAGE 未讀",
                content="內容",
                type=NotificationType.MESSAGE,
            ),
            NotificationCreate(
                user_id=user_id,
                title="MESSAGE 已讀",
                content="內容",
                type=NotificationType.MESSAGE,
                status=NotificationStatus.READ,
            ),
            NotificationCreate(
                user_id=user_id,
                title="SYSTEM 通知",
                content="內容",
                type=NotificationType.SYSTEM,
            ),
        ]

        for notification in notifications:
            await _create_notification(repo, notification)

        # 獲取統計
        stats = await repo.get_stats(user_id)

        # 驗證統計結果
        assert stats.total_count >= 3
        assert stats.unread_count >= 1  # 1 個未讀
        assert stats.read_count >= 1  # 1 個已讀

        # 驗證類型統計
        assert NotificationType.MESSAGE in stats.type_counts
        assert NotificationType.SYSTEM in stats.type_counts
        assert stats.type_counts[NotificationType.MESSAGE] >= 2
        assert stats.type_counts[NotificationType.SYSTEM] >= 1

        # 驗證最近活動
        assert len(stats.recent_activity) <= 5
        assert all("type" in activity for activity in stats.recent_activity)
        assert all("title" in activity for activity in stats.recent_activity)
        assert all("created_at" in activity for activity in stats.recent_activity)

    @pytest.mark.asyncio
    async def test_pagination(self, db_manager):
        """測試分頁功能"""
        repo = NotificationRepository(db_manager.database)
        user_id = str(ObjectId())

        # 創建 9 個通知（剛好 3 頁）
        created_notifications = []
        for i in range(9):
            notification = NotificationCreate(
                user_id=user_id,
                title=f"通知 {i:02d}",
                content=f"內容 {i}",
                type=NotificationType.MESSAGE,
            )
            created_notif = await _create_notification(repo, notification)
            created_notifications.append(created_notif)

        # 測試分頁
        page1 = await repo.get_by_user(user_id, skip=0, limit=3)
        page2 = await repo.get_by_user(user_id, skip=3, limit=3)
        page3 = await repo.get_by_user(user_id, skip=6, limit=3)

        # 驗證分頁結果
        assert len(page1) == 3
        assert len(page2) == 3
        assert len(page3) == 3

        # 驗證沒有重複
        all_ids = set()
        for page in [page1, page2, page3]:
            for notif in page:
                assert notif.id not in all_ids, f"Duplicate notification ID: {notif.id}"
                all_ids.add(notif.id)

        # 驗證總數正確
        assert len(all_ids) == 9

    @pytest.mark.asyncio
    async def test_error_handling(self, db_manager):
        """測試錯誤處理"""
        repo = NotificationRepository(db_manager.database)

        # 測試無效的 ObjectId
        result = await repo.get_by_id("invalid_id")
        assert result is None

        # 測試空字串 ID
        result = await repo.get_by_id("")
        assert result is None

        # 測試 None ID
        result = await repo.get_by_id(None)
        assert result is None

        # 測試無效用戶 ID 的統計
        stats = await repo.get_stats("invalid_user_id")
        assert stats.total_count == 0
        assert stats.unread_count == 0


@pytest.mark.unit
class TestNotificationRepositoryErrorPropagation:
    """驗證 DB 異常正確傳播而非被吞掉"""

    @pytest.mark.asyncio
    async def test_find_propagates_db_error(self, db_manager):
        """測試查詢時 DB 異常正確傳播"""
        repo = NotificationRepository(db_manager.database)
        with patch.object(
            repo.collection, "find_one", side_effect=PyMongoError("connection lost")
        ):
            with pytest.raises(PyMongoError):
                await repo.get_by_id(str(ObjectId()))

    @pytest.mark.asyncio
    async def test_count_propagates_db_error(self, db_manager):
        """測試 count 時 DB 異常正確傳播（之前會回傳 0 假裝沒資料）"""
        repo = NotificationRepository(db_manager.database)
        with patch.object(
            repo.collection,
            "count_documents",
            side_effect=PyMongoError("timeout"),
        ):
            with pytest.raises(PyMongoError):
                await repo.get_unread_count("some_user_id")

    @pytest.mark.asyncio
    async def test_aggregate_propagates_db_error(self, db_manager):
        """測試 aggregation 時 DB 異常正確傳播（之前會回傳空統計）"""
        repo = NotificationRepository(db_manager.database)
        with patch.object(
            repo.collection,
            "aggregate",
            side_effect=PyMongoError("aggregation failed"),
        ):
            with pytest.raises(PyMongoError):
                await repo.get_stats("some_user_id")
