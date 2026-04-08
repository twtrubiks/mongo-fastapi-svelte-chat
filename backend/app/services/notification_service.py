"""通知服務層（重構版）"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.notification import (
    NotificationCreate,
    NotificationListResponse,
    NotificationResponse,
    NotificationStats,
    NotificationStatus,
    NotificationType,
    NotificationUpdate,
)
from app.repositories.notification_repository import NotificationRepository

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服務類別"""

    def __init__(
        self, notification_repository: NotificationRepository, connection_manager=None
    ):
        self.notification_repo = notification_repository
        self._connection_manager = connection_manager

    async def _create_notification_business_logic(
        self,
        user_id: str,
        title: str,
        content: str,
        notification_type: NotificationType,
        metadata: dict[str, Any] | None = None,
        sender_id: str | None = None,
        room_id: str | None = None,
    ) -> NotificationResponse:
        """
        創建通知的業務邏輯（不包含事務管理）

        Args:
            user_id: 接收者 ID
            title: 通知標題
            content: 通知內容
            notification_type: 通知類型
            metadata: 額外元數據
            sender_id: 發送者 ID
            room_id: 相關房間 ID

        Returns:
            NotificationResponse: 創建的通知資料
        """
        # 創建通知
        notification_create = NotificationCreate(
            user_id=user_id,
            title=title,
            content=content,
            type=notification_type,
            metadata=metadata or {},
            sender_id=sender_id,
            room_id=room_id,
        )

        # 插入通知
        created_notification = await self.notification_repo.create(notification_create)

        # 轉換為響應模型
        notification_response = NotificationResponse(
            **created_notification.model_dump()
        )

        try:
            await self.send_real_time_notification(
                user_id=user_id, notification=notification_response.model_dump()
            )
        except Exception as e:  # intentional fail-open: 實時推播失敗不影響通知建立
            logger.error(f"Error sending real-time notification: {e}")

        logger.info(f"Notification created for user {user_id}: {title}")
        return notification_response

    async def create_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        notification_type: NotificationType,
        metadata: dict[str, Any] | None = None,
        sender_id: str | None = None,
        room_id: str | None = None,
    ) -> NotificationResponse:
        """
        創建通知

        Args:
            user_id: 接收者 ID
            title: 通知標題
            content: 通知內容
            notification_type: 通知類型
            metadata: 額外元數據
            sender_id: 發送者 ID
            room_id: 相關房間 ID

        Returns:
            NotificationResponse: 創建的通知資料
        """
        return await self._create_notification_business_logic(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            metadata=metadata,
            sender_id=sender_id,
            room_id=room_id,
        )

    async def get_user_notifications(
        self,
        user_id: str,
        status: NotificationStatus | None = None,
        notification_type: NotificationType | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> NotificationListResponse:
        """
        獲取用戶通知列表

        Args:
            user_id: 用戶 ID
            status: 通知狀態篩選
            notification_type: 通知類型篩選
            skip: 跳過筆數
            limit: 每頁大小

        Returns:
            NotificationListResponse: 通知列表響應
        """
        # 獲取通知列表與未讀數（兩個獨立查詢，並行執行）
        notifications, unread_count = await asyncio.gather(
            self.notification_repo.get_by_user(
                user_id=user_id,
                status=status,
                notification_type=notification_type,
                skip=skip,
                limit=limit,
            ),
            self.notification_repo.get_unread_count(user_id),
        )

        # 轉換為響應模型
        notification_responses = [
            NotificationResponse(**notification.model_dump())
            for notification in notifications
        ]

        return NotificationListResponse(
            notifications=notification_responses,
            unread_count=unread_count,
        )

    async def mark_as_read(self, notification_id: str, user_id: str) -> None:
        """
        標記通知為已讀

        Args:
            notification_id: 通知 ID
            user_id: 用戶 ID

        Raises:
            NotFoundError: 通知不存在時
            ForbiddenError: 無權限時
        """
        # 先檢查通知是否屬於該用戶
        notification = await self.notification_repo.get_by_id(notification_id)
        if not notification:
            raise NotFoundError("通知不存在")

        if notification.user_id != user_id:
            raise ForbiddenError("無權操作此通知")

        # 更新狀態
        update_data = NotificationUpdate(
            status=NotificationStatus.READ, read_at=datetime.now(UTC)
        )
        await self.notification_repo.update(notification_id, update_data)

    async def mark_all_as_read(self, user_id: str) -> int:
        """
        標記用戶所有通知為已讀

        Args:
            user_id: 用戶 ID

        Returns:
            int: 更新的通知數量
        """
        query = {"user_id": user_id, "status": NotificationStatus.UNREAD}
        update_data = {
            "$set": {
                "status": NotificationStatus.READ,
                "read_at": datetime.now(UTC),
            }
        }
        count = await self.notification_repo.update_many(query, update_data)

        if count > 0:
            await self._broadcast_stats_update(user_id, f"已標記 {count} 則通知為已讀")

        return count

    async def mark_room_notifications_as_read(self, user_id: str, room_id: str) -> int:
        """
        標記用戶在特定房間的所有通知為已讀

        Args:
            user_id: 用戶 ID
            room_id: 房間 ID

        Returns:
            int: 更新的通知數量
        """
        # 查詢該用戶在指定房間的未讀通知
        query = {
            "user_id": user_id,
            "status": NotificationStatus.UNREAD,
            "$or": [
                {"room_id": room_id},  # 直接的房間通知
                {"metadata.room_id": room_id},  # 元數據中的房間 ID
            ],
        }
        update_data = {
            "$set": {
                "status": NotificationStatus.READ,
                "read_at": datetime.now(UTC),
            }
        }
        count = await self.notification_repo.update_many(query, update_data)

        if count > 0:
            await self._broadcast_stats_update(
                user_id, f"已標記房間 {room_id} 的 {count} 則通知為已讀"
            )

        return count

    async def delete_notification(self, notification_id: str, user_id: str) -> None:
        """
        刪除通知

        Args:
            notification_id: 通知 ID
            user_id: 用戶 ID

        Raises:
            NotFoundError: 通知不存在時
            ForbiddenError: 無權限時
        """
        # 先檢查通知是否屬於該用戶
        notification = await self.notification_repo.get_by_id(notification_id)
        if not notification:
            raise NotFoundError("通知不存在")

        if notification.user_id != user_id:
            raise ForbiddenError("無權操作此通知")

        # 刪除通知
        await self.notification_repo.delete_by_id(notification_id)

    async def clear_user_notifications(self, user_id: str) -> int:
        """
        清空用戶所有通知

        Args:
            user_id: 用戶 ID

        Returns:
            int: 刪除的通知數量
        """
        query = {"user_id": user_id}
        return await self.notification_repo.delete_many(query)

    async def _broadcast_stats_update(self, user_id: str, message: str) -> None:
        """透過 WebSocket 廣播通知統計更新（不影響核心功能）"""
        try:
            stats = await self.get_notification_stats(user_id)
            if not self._connection_manager:
                return
            await self._connection_manager.send_event(
                user_id,
                {
                    "type": "notification_stats_update",
                    "stats": {
                        "total": stats.total_count,
                        "unread": stats.unread_count,
                        "by_type": stats.type_counts,
                    },
                    "message": message,
                },
            )
            logger.info(
                f"Sent notification stats update to user {user_id}: unread={stats.unread_count}"
            )
        except Exception as e:  # intentional fail-open: 統計廣播失敗不中斷主流程
            logger.error(f"Error sending real-time notification stats update: {e}")

    async def get_notification_stats(self, user_id: str) -> NotificationStats:
        """
        獲取用戶通知統計

        Args:
            user_id: 用戶 ID

        Returns:
            NotificationStats: 統計資料
        """
        return await self.notification_repo.get_stats(user_id)

    async def send_real_time_notification(
        self, user_id: str, notification: dict[str, Any]
    ):
        """
        發送實時通知

        Args:
            user_id: 用戶 ID
            notification: 通知資料
        """
        try:
            # 確保通知資料結構完整
            complete_notification = {
                "id": notification.get(
                    "id", f"realtime_{datetime.now().timestamp()}_{user_id}"
                ),
                "user_id": user_id,
                "type": notification.get("type", NotificationType.SYSTEM),
                "status": notification.get("status", NotificationStatus.UNREAD),
                "title": notification.get("title", "通知"),
                "message": notification.get(
                    "content", notification.get("message", "")
                ),  # 優先使用 content
                "content": notification.get(
                    "content", notification.get("message", "")
                ),  # 同時保留 content 欄位
                "data": notification.get(
                    "metadata", notification.get("data", {})
                ),  # 優先使用 metadata
                "metadata": notification.get(
                    "metadata", notification.get("data", {})
                ),  # 同時保留 metadata 欄位
                "room_id": notification.get("room_id"),
                "sender_id": notification.get("sender_id"),
                "created_at": notification.get(
                    "created_at", datetime.now(UTC).isoformat()
                ),
                "updated_at": notification.get(
                    "updated_at", datetime.now(UTC).isoformat()
                ),
            }

            # 確保必要欄位存在
            if (
                not complete_notification["title"]
                or not complete_notification["message"]
            ):
                logger.warning(
                    f"Notification missing title or message: {complete_notification}"
                )
                return

            # 發送 WebSocket 通知
            if not self._connection_manager:
                return
            await self._connection_manager.send_notification(
                user_id, complete_notification
            )

            logger.debug(f"Real-time notification sent to user {user_id}")
        except Exception as e:  # intentional fail-open: 實時推播失敗不中斷呼叫端
            logger.error(f"Error sending real-time notification: {e}")

    # 快捷方法
    async def send_message_notification(
        self,
        user_id: str,
        sender_name: str,
        message_preview: str,
        room_name: str,
        room_id: str,
        sender_id: str,
        message_id: str | None = None,
    ) -> NotificationResponse:
        """
        發送訊息通知
        """
        metadata = {
            "sender_name": sender_name,
            "room_name": room_name,
            "message_preview": message_preview,
        }

        # 如果有訊息 ID，加入 metadata 以便點擊通知時定位
        if message_id:
            metadata["message_id"] = message_id

        # 確保 metadata 包含所有必要資訊
        metadata["room_id"] = room_id
        metadata["sender_id"] = sender_id

        return await self.create_notification(
            user_id=user_id,
            title=f"來自 {sender_name} 的新訊息",
            content=f"在 {room_name} 中：{message_preview}",
            notification_type=NotificationType.MESSAGE,
            metadata=metadata,
            sender_id=sender_id,
            room_id=room_id,
        )
