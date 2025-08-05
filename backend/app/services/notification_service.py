"""通知服務層（重構版）"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, UTC
from app.models.notification import (
    NotificationCreate, NotificationUpdate, NotificationResponse,
    NotificationListResponse, NotificationStats, NotificationBatch,
    NotificationType, NotificationStatus
)
from app.repositories.notification_repository import NotificationRepository
from app.database.improved_transaction import improved_transactional as transactional
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """通知服務類別"""
    
    def __init__(self, notification_repository: NotificationRepository):
        self.notification_repo = notification_repository
    
    async def _create_notification_business_logic(
        self,
        user_id: str,
        title: str,
        content: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None,
        sender_id: Optional[str] = None,
        room_id: Optional[str] = None
    ) -> Optional[NotificationResponse]:
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
            Optional[NotificationResponse]: 創建的通知資料
        """
        # 創建通知
        notification_create = NotificationCreate(
            user_id=user_id,
            title=title,
            content=content,
            type=notification_type,
            metadata=metadata or {},
            sender_id=sender_id,
            room_id=room_id
        )
        
        # 插入通知
        created_notification = await self.notification_repo.create(notification_create)
        
        if created_notification:
            # 轉換為響應模型
            notification_response = NotificationResponse(**created_notification.model_dump())
            
            # 發送實時通知 (失敗不影響主要業務邏輯)
            try:
                await self.send_real_time_notification(
                    user_id=user_id,
                    notification=notification_response.model_dump()
                )
            except Exception as e:
                logger.error(f"Error sending real-time notification: {e}")
            
            logger.info(f"Notification created for user {user_id}: {title}")
            return notification_response
        
        return None

    @transactional(retry_count=2, timeout=20.0)
    async def create_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None,
        sender_id: Optional[str] = None,
        room_id: Optional[str] = None
    ) -> Optional[NotificationResponse]:
        """
        創建通知（使用事務確保資料一致性）
        
        Args:
            user_id: 接收者 ID
            title: 通知標題
            content: 通知內容
            notification_type: 通知類型
            metadata: 額外元數據
            sender_id: 發送者 ID
            room_id: 相關房間 ID
            
        Returns:
            Optional[NotificationResponse]: 創建的通知資料
        """
        try:
            return await self._create_notification_business_logic(
                user_id=user_id,
                title=title,
                content=content,
                notification_type=notification_type,
                metadata=metadata,
                sender_id=sender_id,
                room_id=room_id
            )
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None
    
    async def _create_batch_notifications_business_logic(
        self,
        user_ids: List[str],
        title: str,
        content: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None,
        sender_id: Optional[str] = None,
        room_id: Optional[str] = None
    ) -> List[str]:
        """
        批量創建通知的業務邏輯（不包含事務管理）
        
        Args:
            user_ids: 接收者 ID 列表
            title: 通知標題
            content: 通知內容
            notification_type: 通知類型
            metadata: 額外元數據
            sender_id: 發送者 ID
            room_id: 相關房間 ID
            
        Returns:
            List[str]: 創建的通知 ID 列表
        """
        # 創建通知列表
        notifications = []
        for user_id in user_ids:
            notification_create = NotificationCreate(
                user_id=user_id,
                title=title,
                content=content,
                type=notification_type,
                metadata=metadata or {},
                sender_id=sender_id,
                room_id=room_id
            )
            notifications.append(notification_create)
        
        # 批量插入通知
        notification_ids = await self.notification_repo.create_batch(notifications)
        
        if notification_ids:
            # 批量發送實時通知 (失敗不影響主要業務邏輯)
            try:
                await self.send_batch_real_time_notifications(
                    user_ids=user_ids,
                    title=title,
                    content=content,
                    notification_type=notification_type,
                    metadata=metadata
                )
            except Exception as e:
                logger.error(f"Error sending batch real-time notifications: {e}")
            
            logger.info(f"Batch notifications created for {len(user_ids)} users")
            return notification_ids
        
        return []

    @transactional(retry_count=3, timeout=45.0)
    async def create_batch_notifications(
        self,
        user_ids: List[str],
        title: str,
        content: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None,
        sender_id: Optional[str] = None,
        room_id: Optional[str] = None
    ) -> List[str]:
        """
        批量創建通知（使用事務確保資料一致性）
        
        Args:
            user_ids: 接收者 ID 列表
            title: 通知標題
            content: 通知內容
            notification_type: 通知類型
            metadata: 額外元數據
            sender_id: 發送者 ID
            room_id: 相關房間 ID
            
        Returns:
            List[str]: 創建的通知 ID 列表
        """
        try:
            return await self._create_batch_notifications_business_logic(
                user_ids=user_ids,
                title=title,
                content=content,
                notification_type=notification_type,
                metadata=metadata,
                sender_id=sender_id,
                room_id=room_id
            )
        except Exception as e:
            logger.error(f"Error creating batch notifications: {e}")
            return []
    
    async def get_user_notifications(
        self,
        user_id: str,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None,
        page: int = 1,
        page_size: int = 20
    ) -> NotificationListResponse:
        """
        獲取用戶通知列表
        
        Args:
            user_id: 用戶 ID
            status: 通知狀態篩選
            notification_type: 通知類型篩選
            page: 頁碼
            page_size: 每頁大小
            
        Returns:
            NotificationListResponse: 通知列表響應
        """
        try:
            skip = (page - 1) * page_size
            
            # 獲取通知列表
            notifications = await self.notification_repo.get_by_user(
                user_id=user_id,
                status=status,
                notification_type=notification_type,
                skip=skip,
                limit=page_size
            )
            
            # 獲取總數和未讀數
            total_query = {"user_id": user_id}
            if status:
                total_query["status"] = status
            if notification_type:
                total_query["type"] = notification_type
            
            total = await self.notification_repo.count_documents(total_query)
            unread_count = await self.notification_repo.get_unread_count(user_id)
            
            # 轉換為響應模型
            notification_responses = [
                NotificationResponse(**notification.model_dump())
                for notification in notifications
            ]
            
            return NotificationListResponse(
                notifications=notification_responses,
                total=total,
                unread_count=unread_count,
                page=page,
                page_size=page_size,
                has_next=total > skip + page_size
            )
        except Exception as e:
            logger.error(f"Error getting notifications for user {user_id}: {e}")
            return NotificationListResponse(
                notifications=[],
                total=0,
                unread_count=0,
                page=page,
                page_size=page_size,
                has_next=False
            )
    
    async def count_user_notifications(
        self,
        user_id: str,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None
    ) -> int:
        """
        計算用戶通知數量
        
        Args:
            user_id: 用戶 ID
            status: 通知狀態篩選
            notification_type: 通知類型篩選
            
        Returns:
            int: 通知數量
        """
        try:
            query = {"user_id": user_id}
            if status:
                query["status"] = status
            if notification_type:
                query["type"] = notification_type
            
            return await self.notification_repo.count_documents(query)
        except Exception as e:
            logger.error(f"Error counting notifications for user {user_id}: {e}")
            return 0
    
    async def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """
        標記通知為已讀
        
        Args:
            notification_id: 通知 ID
            user_id: 用戶 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"Marking notification {notification_id} as read for user {user_id}")
            
            # 先檢查通知是否屬於該用戶
            notification = await self.notification_repo.get_by_id(notification_id)
            logger.info(f"Found notification: {notification is not None}")
            
            if not notification:
                logger.warning(f"Notification {notification_id} not found")
                return False
                
            if notification.user_id != user_id:
                logger.warning(f"User {user_id} does not own notification {notification_id} (owner: {notification.user_id})")
                return False
            
            # 更新狀態
            update_data = NotificationUpdate(status=NotificationStatus.READ, is_read=True, read_at=datetime.now(UTC))
            result = await self.notification_repo.update(notification_id, update_data)
            logger.info(f"Update result: {result is not None}")
            return result is not None
        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read: {e}")
            return False
    
    async def mark_all_as_read(self, user_id: str) -> int:
        """
        標記用戶所有通知為已讀
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            int: 更新的通知數量
        """
        try:
            query = {"user_id": user_id, "status": NotificationStatus.UNREAD}
            update_data = {
                "$set": {
                    "status": NotificationStatus.READ,
                    "is_read": True,
                    "read_at": datetime.now(UTC)
                }
            }
            count = await self.notification_repo.update_many(query, update_data)
            
            if count > 0:
                # 發送 WebSocket 實時更新通知
                try:
                    from app.websocket.manager import connection_manager
                    
                    # 獲取更新後的統計資料
                    stats = await self.get_notification_stats(user_id)
                    
                    # 發送統計更新事件
                    await connection_manager.send_notification(user_id, {
                        "type": "notification_stats_update",
                        "stats": {
                            "total": stats.total,
                            "unread": stats.unread,
                            "by_type": stats.by_type
                        },
                        "message": f"已標記 {count} 則通知為已讀"
                    })
                    
                    logger.info(f"Sent notification stats update to user {user_id}: unread={stats.unread}")
                except Exception as e:
                    logger.error(f"Error sending real-time notification stats update: {e}")
                    # 不影響核心功能，繼續執行
            
            return count
        except Exception as e:
            logger.error(f"Error marking all notifications as read for user {user_id}: {e}")
            return 0

    async def mark_room_notifications_as_read(self, user_id: str, room_id: str) -> int:
        """
        標記用戶在特定房間的所有通知為已讀
        
        Args:
            user_id: 用戶 ID
            room_id: 房間 ID
            
        Returns:
            int: 更新的通知數量
        """
        try:
            # 查詢該用戶在指定房間的未讀通知
            query = {
                "user_id": user_id, 
                "status": NotificationStatus.UNREAD,
                "$or": [
                    {"room_id": room_id},  # 直接的房間通知
                    {"metadata.room_id": room_id}  # 元數據中的房間 ID
                ]
            }
            update_data = {
                "$set": {
                    "status": NotificationStatus.READ,
                    "is_read": True,
                    "read_at": datetime.now(UTC)
                }
            }
            count = await self.notification_repo.update_many(query, update_data)
            
            if count > 0:
                # 重新計算並發送統計更新
                try:
                    stats = await self.get_notification_stats(user_id)
                    from app.websocket.manager import connection_manager
                    
                    # 發送統計更新事件
                    await connection_manager.send_notification(user_id, {
                        "type": "notification_stats_update",
                        "stats": {
                            "total": stats.total,
                            "unread": stats.unread,
                            "by_type": stats.by_type
                        },
                        "message": f"已標記房間 {room_id} 的 {count} 則通知為已讀"
                    })
                    
                    logger.info(f"Sent room notification stats update to user {user_id} for room {room_id}: unread={stats.unread}")
                except Exception as e:
                    logger.error(f"Error sending real-time room notification stats update: {e}")
                    # 不影響核心功能，繼續執行
            
            logger.info(f"[NotificationService] Query used: {query}")
            logger.info(f"[NotificationService] Update data: {update_data}")
            logger.info(f"[NotificationService] Marked {count} room notifications as read for user {user_id} in room {room_id}")
            return count
        except Exception as e:
            logger.error(f"Error marking room notifications as read for user {user_id} in room {room_id}: {e}")
            return 0
    
    async def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """
        刪除通知
        
        Args:
            notification_id: 通知 ID
            user_id: 用戶 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # 先檢查通知是否屬於該用戶
            notification = await self.notification_repo.get_by_id(notification_id)
            if not notification or notification.user_id != user_id:
                return False
            
            # 刪除通知
            return await self.notification_repo.delete_by_id(notification_id)
        except Exception as e:
            logger.error(f"Error deleting notification {notification_id}: {e}")
            return False
    
    async def clear_user_notifications(self, user_id: str) -> int:
        """
        清空用戶所有通知
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            int: 刪除的通知數量
        """
        try:
            query = {"user_id": user_id}
            return await self.notification_repo.delete_many(query)
        except Exception as e:
            logger.error(f"Error clearing notifications for user {user_id}: {e}")
            return 0

    async def mark_notification_as_read(self, notification_id: str) -> bool:
        """
        標記通知為已讀
        
        Args:
            notification_id: 通知 ID
            
        Returns:
            bool: 是否成功
        """
        try:
            success = await self.notification_repo.mark_as_read(notification_id)
            if success:
                logger.info(f"Notification marked as read: {notification_id}")
            return success
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False
    
    async def mark_all_notifications_as_read(self, user_id: str) -> int:
        """
        標記用戶所有通知為已讀
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            int: 標記的通知數量
        """
        try:
            count = await self.notification_repo.mark_all_as_read(user_id)
            logger.info(f"Marked {count} notifications as read for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return 0
    
    
    async def get_notification_stats(self, user_id: str) -> NotificationStats:
        """
        獲取用戶通知統計
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            NotificationStats: 統計資料
        """
        try:
            stats = await self.notification_repo.get_stats(user_id)
            return stats
        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return NotificationStats(
                total_count=0,
                unread_count=0,
                read_count=0,
                dismissed_count=0,
                type_counts={},
                recent_activity=[]
            )
    
    async def cleanup_old_notifications(self, days: int = 30) -> int:
        """
        清理舊通知
        
        Args:
            days: 天數閾值
            
        Returns:
            int: 清理的通知數量
        """
        try:
            count = await self.notification_repo.delete_old_notifications(days)
            logger.info(f"Cleaned up {count} old notifications")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up old notifications: {e}")
            return 0
    
    async def send_real_time_notification(
        self,
        user_id: str,
        notification: Dict[str, Any]
    ):
        """
        發送實時通知
        
        Args:
            user_id: 用戶 ID
            notification: 通知資料
        """
        try:
            # 這裡應該通過依賴注入獲取 connection_manager
            # 暫時使用直接導入，後續需要修正
            from app.websocket.manager import connection_manager
            
            # 確保通知資料結構完整
            complete_notification = {
                "id": notification.get("id", f"realtime_{datetime.now().timestamp()}_{user_id}"),
                "user_id": user_id,
                "type": notification.get("type", "SYSTEM"),
                "status": notification.get("status", "UNREAD"),
                "title": notification.get("title", "通知"),
                "message": notification.get("message", notification.get("content", "")),
                "data": notification.get("data", notification.get("metadata", {})),
                "created_at": notification.get("created_at", datetime.now(UTC).isoformat()),
                "updated_at": notification.get("updated_at", datetime.now(UTC).isoformat())
            }
            
            # 發送 WebSocket 通知
            await connection_manager.send_notification(user_id, complete_notification)
            
            logger.debug(f"Real-time notification sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error sending real-time notification: {e}")
    
    async def send_batch_real_time_notifications(
        self,
        user_ids: List[str],
        title: str,
        content: str,
        notification_type: NotificationType,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        批量發送實時通知
        
        Args:
            user_ids: 用戶 ID 列表
            title: 通知標題
            content: 通知內容
            notification_type: 通知類型
            metadata: 額外元數據
        """
        try:
            # 這裡應該通過依賴注入獲取 connection_manager
            # 暫時使用直接導入，後續需要修正
            from app.websocket.manager import connection_manager
            
            for user_id in user_ids:
                # 為每個用戶創建完整的通知資料結構
                notification_data = {
                    "id": f"realtime_{datetime.now().timestamp()}_{user_id}",
                    "user_id": user_id,
                    "type": notification_type.value if hasattr(notification_type, 'value') else str(notification_type),
                    "status": "UNREAD",
                    "title": title,
                    "message": content,  # 前端期望的是 message 而不是 content
                    "data": metadata or {},
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat()
                }
                await connection_manager.send_notification(user_id, notification_data)
            
            logger.debug(f"Batch real-time notifications sent to {len(user_ids)} users")
        except Exception as e:
            logger.error(f"Error sending batch real-time notifications: {e}")
    
    # 快捷方法
    async def send_message_notification(
        self,
        user_id: str,
        sender_name: str,
        message_preview: str,
        room_name: str,
        room_id: str,
        sender_id: str,
        message_id: Optional[str] = None
    ) -> Optional[NotificationResponse]:
        """
        發送訊息通知
        """
        metadata = {
            "sender_name": sender_name,
            "room_name": room_name,
            "message_preview": message_preview
        }
        
        # 如果有訊息 ID，加入 metadata 以便點擊通知時定位
        if message_id:
            metadata["message_id"] = message_id
            
        return await self.create_notification(
            user_id=user_id,
            title=f"來自 {sender_name} 的新訊息",
            content=f"在 {room_name} 中：{message_preview}",
            notification_type=NotificationType.MESSAGE,
            metadata=metadata,
            sender_id=sender_id,
            room_id=room_id
        )
    
    async def send_room_invite_notification(
        self,
        user_id: str,
        inviter_name: str,
        room_name: str,
        room_id: str,
        inviter_id: str
    ) -> Optional[NotificationResponse]:
        """
        發送房間邀請通知
        """
        return await self.create_notification(
            user_id=user_id,
            title="房間邀請",
            content=f"{inviter_name} 邀請您加入房間 {room_name}",
            notification_type=NotificationType.ROOM_INVITE,
            metadata={
                "inviter_name": inviter_name,
                "room_name": room_name
            },
            sender_id=inviter_id,
            room_id=room_id
        )
    
    async def send_system_notification(
        self,
        user_id: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[NotificationResponse]:
        """
        發送系統通知
        """
        return await self.create_notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=NotificationType.SYSTEM,
            metadata=metadata or {}
        )