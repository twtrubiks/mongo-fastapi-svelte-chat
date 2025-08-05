"""通知資料存取層"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from pymongo.asynchronous.database import AsyncDatabase
from app.repositories.base import BaseRepository

UTC = timezone.utc
from app.models.notification import (
    NotificationInDB, NotificationCreate, NotificationUpdate, NotificationResponse,
    NotificationListResponse, NotificationStats, NotificationBatch,
    NotificationType, NotificationStatus
)
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class NotificationRepository(BaseRepository[NotificationInDB]):
    """通知資料存取層"""
    
    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "notifications")
    
    async def get_by_id(self, notification_id: str) -> Optional[NotificationInDB]:
        """
        根據 ID 獲取通知
        
        Args:
            notification_id: 通知 ID
            
        Returns:
            Optional[NotificationInDB]: 通知物件，如果不存在則返回 None
        """
        try:
            logger.info(f"Getting notification by ID: {notification_id}")
            document = await self.find_by_id(notification_id)
            if document:
                logger.info(f"Found notification document: {document.get('_id')}")
                return NotificationInDB(**document)
            logger.warning(f"No document found for notification ID: {notification_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting notification by ID {notification_id}: {e}")
            return None
    
    async def delete(self, notification_id: str) -> bool:
        """
        刪除通知
        
        Args:
            notification_id: 通知 ID
            
        Returns:
            bool: 是否刪除成功
        """
        return await self.delete_by_id(notification_id)
    
    async def create(self, notification: NotificationInDB) -> Optional[NotificationInDB]:
        """
        創建通知
        
        Args:
            notification: 通知創建資料
            
        Returns:
            Optional[NotificationInDB]: 創建的通知，如果失敗則返回 None
        """
        try:
            notification_dict = notification.model_dump()
            
            # 插入文檔
            notification_id = await self.insert_one(notification_dict)
            
            if notification_id:
                # 獲取創建的通知
                created_notification = await self.get_by_id(notification_id)
                return created_notification
            
            return None
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None
    
    async def create_from_data(self, notification: NotificationCreate) -> Optional[NotificationInDB]:
        """
        從 NotificationCreate 創建通知
        
        Args:
            notification: 通知創建資料
            
        Returns:
            Optional[NotificationInDB]: 創建的通知，如果失敗則返回 None
        """
        try:
            notification_dict = notification.model_dump()
            notification_dict["created_at"] = datetime.now(UTC)
            notification_dict["updated_at"] = datetime.now(UTC)
            
            # 插入文檔
            notification_id = await self.insert_one(notification_dict)
            
            if notification_id:
                # 獲取創建的通知
                created_notification = await self.get_by_id(notification_id)
                return created_notification
            
            return None
        except Exception as e:
            logger.error(f"Error creating notification from data: {e}")
            return None
    
    async def create_batch(self, notifications: List[NotificationCreate]) -> List[str]:
        """
        批量創建通知
        
        Args:
            notifications: 通知列表
            
        Returns:
            List[str]: 創建的通知 ID 列表
        """
        try:
            notification_docs = []
            for notification in notifications:
                notification_dict = notification.model_dump()
                notification_dict["created_at"] = datetime.now(UTC)
                notification_dict["updated_at"] = datetime.now(UTC)
                notification_docs.append(notification_dict)
            
            inserted_ids = await self.insert_many(notification_docs)
            
            if inserted_ids:
                logger.info(f"Created {len(inserted_ids)} notifications")
                return inserted_ids
            
            return []
        except Exception as e:
            logger.error(f"Error creating batch notifications: {e}")
            return []
    
    async def update(self, notification_id: str, notification_update: NotificationUpdate) -> Optional[NotificationInDB]:
        """
        更新通知
        
        Args:
            notification_id: 通知 ID
            notification_update: 更新資料
            
        Returns:
            Optional[NotificationInDB]: 更新後的通知，如果失敗則返回 None
        """
        try:
            # 準備更新資料
            update_data = {}
            if notification_update.title is not None:
                update_data["title"] = notification_update.title
            if notification_update.content is not None:
                update_data["content"] = notification_update.content
            if notification_update.status is not None:
                update_data["status"] = notification_update.status
            if notification_update.is_read is not None:
                update_data["is_read"] = notification_update.is_read
            if notification_update.read_at is not None:
                update_data["read_at"] = notification_update.read_at
            if notification_update.metadata is not None:
                update_data["metadata"] = notification_update.metadata
            
            if not update_data:
                # 沒有需要更新的資料
                return await self.get_by_id(notification_id)
            
            # 執行更新
            success = await self.update_one(
                {"_id": ObjectId(notification_id)},
                {"$set": update_data}
            )
            
            if success:
                updated_notification = await self.get_by_id(notification_id)
                return updated_notification
            
            return None
        except Exception as e:
            logger.error(f"Error updating notification {notification_id}: {e}")
            return None
    
    async def get_by_user(
        self,
        user_id: str,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[NotificationInDB]:
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
        try:
            query = {"user_id": user_id}
            
            if status:
                query["status"] = status
            if notification_type:
                query["type"] = notification_type
            
            # 按創建時間倒序排列
            sort = [("created_at", -1)]
            
            notifications = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            return [NotificationInDB(**notification) for notification in notifications]
        except Exception as e:
            logger.error(f"Error getting notifications for user {user_id}: {e}")
            return []
    
    async def get_unread_count(self, user_id: str) -> int:
        """
        獲取用戶未讀通知數量
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            int: 未讀通知數量
        """
        try:
            count = await self.count_documents({
                "user_id": user_id,
                "is_read": False
            })
            return count
        except Exception as e:
            logger.error(f"Error getting unread count for user {user_id}: {e}")
            return 0
    
    async def mark_as_read(self, notification_id: str) -> bool:
        """
        標記通知為已讀
        
        Args:
            notification_id: 通知 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            success = await self.update_one(
                {"_id": ObjectId(notification_id)},
                {
                    "$set": {
                        "is_read": True,
                        "read_at": datetime.now(UTC),
                        "status": NotificationStatus.READ
                    }
                }
            )
            return success
        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read: {e}")
            return False
    
    async def mark_all_as_read(self, user_id: str) -> int:
        """
        標記用戶所有通知為已讀
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            int: 標記的通知數量
        """
        try:
            modified_count = await self.update_many(
                {
                    "user_id": user_id,
                    "is_read": False
                },
                {
                    "$set": {
                        "is_read": True,
                        "read_at": datetime.now(UTC),
                        "status": NotificationStatus.READ
                    }
                }
            )
            return modified_count
        except Exception as e:
            logger.error(f"Error marking all notifications as read for user {user_id}: {e}")
            return 0
    
    async def delete_by_id(self, notification_id: str) -> bool:
        """
        刪除通知
        
        Args:
            notification_id: 通知 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            success = await self.delete_one({"_id": ObjectId(notification_id)})
            return success
        except Exception as e:
            logger.error(f"Error deleting notification {notification_id}: {e}")
            return False
    
    async def delete_old_notifications(self, days: int = 30) -> int:
        """
        刪除舊通知
        
        Args:
            days: 天數閾值
            
        Returns:
            int: 刪除的通知數量
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)
            deleted_count = await self.delete_many({
                "created_at": {"$lt": cutoff_date},
                "is_read": True
            })
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting old notifications: {e}")
            return 0
    
    async def get_stats(self, user_id: str) -> NotificationStats:
        """
        獲取用戶通知統計
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            NotificationStats: 統計資料
        """
        try:
            # 總數
            total_count = await self.count_documents({"user_id": user_id})
            
            # 未讀數
            unread_count = await self.count_documents({
                "user_id": user_id,
                "is_read": False
            })
            
            # 已讀數
            read_count = await self.count_documents({
                "user_id": user_id,
                "is_read": True
            })
            
            # 已忽略數
            dismissed_count = await self.count_documents({
                "user_id": user_id,
                "status": NotificationStatus.DISMISSED
            })
            
            # 類型統計
            type_counts = {}
            for notification_type in NotificationType:
                count = await self.count_documents({
                    "user_id": user_id,
                    "type": notification_type
                })
                type_counts[notification_type] = count
            
            # 最近活動
            recent_notifications = await self.find_many(
                {"user_id": user_id},
                skip=0,
                limit=5,
                sort=[("created_at", -1)]
            )
            
            recent_activity = [
                {
                    "type": notification["type"],
                    "title": notification["title"],
                    "created_at": notification["created_at"]
                }
                for notification in recent_notifications
            ]
            
            return NotificationStats(
                total_count=total_count,
                unread_count=unread_count,
                read_count=read_count,
                dismissed_count=dismissed_count,
                type_counts=type_counts,
                recent_activity=recent_activity
            )
        except Exception as e:
            logger.error(f"Error getting notification stats for user {user_id}: {e}")
            return NotificationStats(
                total_count=0,
                unread_count=0,
                read_count=0,
                dismissed_count=0,
                type_counts={},
                recent_activity=[]
            )