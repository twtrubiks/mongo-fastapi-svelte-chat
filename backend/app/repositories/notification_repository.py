"""通知資料存取層"""

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.notification import (
    NotificationInDB,
    NotificationStats,
    NotificationStatus,
    NotificationType,
    NotificationUpdate,
)
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[NotificationInDB]):
    """通知資料存取層"""

    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "notifications")

    def _to_model(self, document: dict) -> NotificationInDB:
        return NotificationInDB(**document)

    async def update(
        self, notification_id: str, notification_update: NotificationUpdate
    ) -> NotificationInDB | None:
        """
        更新通知

        Args:
            notification_id: 通知 ID
            notification_update: 更新資料

        Returns:
            Optional[NotificationInDB]: 更新後的通知，如果失敗則返回 None
        """
        # 準備更新資料
        update_data = {}
        if notification_update.title is not None:
            update_data["title"] = notification_update.title
        if notification_update.content is not None:
            update_data["content"] = notification_update.content
        if notification_update.status is not None:
            update_data["status"] = notification_update.status
        if notification_update.read_at is not None:
            update_data["read_at"] = notification_update.read_at
        if notification_update.metadata is not None:
            update_data["metadata"] = notification_update.metadata

        if not update_data:
            # 沒有需要更新的資料
            return await self.get_by_id(notification_id)

        # 執行更新
        success = await self.update_one(
            {"_id": ObjectId(notification_id)}, {"$set": update_data}
        )

        if success:
            return await self.get_by_id(notification_id)

        return None

    async def get_by_user(
        self,
        user_id: str,
        status: NotificationStatus | None = None,
        notification_type: NotificationType | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[NotificationInDB]:
        """
        獲取用戶的通知列表

        Args:
            user_id: 用戶 ID
            status: 通知狀態篩選
            notification_type: 通知類型篩選
            skip: 跳過的數量
            limit: 限制數量

        Returns:
            List[NotificationInDB]: 通知列表
        """
        query = {"user_id": user_id}

        if status:
            query["status"] = status
        if notification_type:
            query["type"] = notification_type

        # 按創建時間倒序排列
        sort = [("created_at", -1)]

        notifications = await self.find_many(query, skip=skip, limit=limit, sort=sort)

        return [self._to_model(notification) for notification in notifications]

    async def get_unread_count(self, user_id: str) -> int:
        """
        獲取用戶未讀通知數量

        Args:
            user_id: 用戶 ID

        Returns:
            int: 未讀通知數量
        """
        return await self.count_documents(
            {"user_id": user_id, "status": NotificationStatus.UNREAD}
        )

    async def delete_by_id(self, notification_id: str) -> bool:
        return await self.delete_one({"_id": ObjectId(notification_id)})

    async def get_stats(self, user_id: str) -> NotificationStats:
        """
        獲取用戶通知統計（單次 aggregation 取代多次 count）

        Args:
            user_id: 用戶 ID

        Returns:
            NotificationStats: 統計資料
        """
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$facet": {
                    # 按狀態分組：同時算出 total / unread / read
                    "by_status": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
                    # 按類型分組
                    "by_type": [{"$group": {"_id": "$type", "count": {"$sum": 1}}}],
                    # 最近 5 筆活動
                    "recent": [
                        {"$sort": {"created_at": -1}},
                        {"$limit": 5},
                        {
                            "$project": {
                                "_id": 0,
                                "type": 1,
                                "title": 1,
                                "created_at": 1,
                            }
                        },
                    ],
                }
            },
        ]

        cursor = await self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        facet = results[0] if results else {}

        # 解析狀態計數
        status_map = {item["_id"]: item["count"] for item in facet.get("by_status", [])}
        unread_count = status_map.get(NotificationStatus.UNREAD, 0)
        read_count = status_map.get(NotificationStatus.READ, 0)
        total_count = unread_count + read_count

        # 解析類型計數
        type_counts = {item["_id"]: item["count"] for item in facet.get("by_type", [])}

        # 最近活動
        recent_activity = facet.get("recent", [])

        return NotificationStats(
            total_count=total_count,
            unread_count=unread_count,
            read_count=read_count,
            type_counts=type_counts,
            recent_activity=recent_activity,
        )
