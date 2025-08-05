"""訊息資料存取層"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from pymongo.asynchronous.database import AsyncDatabase
from app.repositories.base import BaseRepository

UTC = timezone.utc
from app.models.message import (
    MessageInDB, MessageCreate, MessageUpdate, MessageResponse,
    MessageListResponse, MessageSearchQuery, MessageStats,
    MessageWithReply, ReplyToMessage, MessageType, MessageStatus,
    MessageReaction, MessageWithReactions
)
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository[MessageInDB]):
    """訊息資料存取類別"""
    
    def __init__(self, database: AsyncDatabase):
        """
        初始化訊息 Repository
        
        Args:
            database: MongoDB 資料庫連線
        """
        super().__init__(database, "messages")
    
    async def get_by_id(self, message_id: str) -> Optional[MessageInDB]:
        """
        根據 ID 獲取訊息
        
        Args:
            message_id: 訊息 ID
            
        Returns:
            Optional[MessageInDB]: 訊息物件，如果不存在則返回 None
        """
        try:
            document = await self.find_by_id(message_id)
            if document:
                return MessageInDB(**document)
            return None
        except Exception as e:
            logger.error(f"Error getting message by ID {message_id}: {e}")
            return None
    
    async def get_with_reply(self, message_id: str) -> Optional[MessageWithReply]:
        """
        根據 ID 獲取訊息（包含回覆資訊）
        
        Args:
            message_id: 訊息 ID
            
        Returns:
            Optional[MessageWithReply]: 包含回覆資訊的訊息物件，如果不存在則返回 None
        """
        try:
            message = await self.get_by_id(message_id)
            if not message:
                return None
            
            # 轉換為 MessageResponse
            message_response = MessageResponse(**message.model_dump())
            
            # 獲取回覆訊息資訊
            reply_to_message = None
            if message.reply_to:
                reply_msg = await self.get_by_id(message.reply_to)
                if reply_msg:
                    reply_to_message = ReplyToMessage(
                        id=str(reply_msg.id),
                        content=reply_msg.content,
                        username=reply_msg.username,
                        created_at=reply_msg.created_at
                    )
            
            return MessageWithReply(
                **message_response.model_dump(),
                reply_to_message=reply_to_message
            )
        except Exception as e:
            logger.error(f"Error getting message with reply {message_id}: {e}")
            return None
    
    async def create(self, message: MessageInDB) -> Optional[MessageInDB]:
        """
        創建新訊息
        
        Args:
            message: 訊息物件
            
        Returns:
            Optional[MessageInDB]: 創建後的訊息物件，如果失敗則返回 None
        """
        try:
            # 驗證回覆訊息（如果有）
            if message.reply_to:
                reply_message = await self.get_by_id(message.reply_to)
                if not reply_message or reply_message.room_id != message.room_id:
                    logger.warning(f"Invalid reply_to message: {message.reply_to}")
                    return None
            
            # 準備文檔
            message_dict = message.model_dump(exclude={"id"})
            message_dict["created_at"] = datetime.now(UTC)
            message_dict["updated_at"] = datetime.now(UTC)
            message_dict["status"] = MessageStatus.SENT
            
            # 插入文檔
            message_id = await self.insert_one(message_dict)
            if message_id:
                return await self.get_by_id(message_id)
            
            return None
        except Exception as e:
            logger.error(f"Error creating message: {e}")
            return None
    
    async def update(self, message_id: str, message_update: MessageUpdate) -> Optional[MessageInDB]:
        """
        更新訊息
        
        Args:
            message_id: 訊息 ID
            message_update: 更新資料
            
        Returns:
            Optional[MessageInDB]: 更新後的訊息物件，如果失敗則返回 None
        """
        try:
            # 準備更新資料
            update_data = {}
            if message_update.content is not None:
                update_data["content"] = message_update.content
                update_data["edited"] = True
                update_data["edited_at"] = datetime.now(UTC)
            
            if message_update.status is not None:
                update_data["status"] = message_update.status
            
            if message_update.metadata is not None:
                update_data["metadata"] = message_update.metadata
            
            if not update_data:
                # 沒有需要更新的資料
                return await self.get_by_id(message_id)
            
            # 執行更新
            success = await self.update_one(
                {"_id": ObjectId(message_id)},
                {"$set": update_data}
            )
            
            if success:
                return await self.get_by_id(message_id)
            
            return None
        except Exception as e:
            logger.error(f"Error updating message {message_id}: {e}")
            return None
    
    async def delete(self, message_id: str) -> bool:
        """
        刪除訊息（軟刪除）
        
        Args:
            message_id: 訊息 ID
            
        Returns:
            bool: 是否刪除成功
        """
        try:
            # 軟刪除：更新狀態和內容
            success = await self.update_one(
                {"_id": ObjectId(message_id)},
                {
                    "$set": {
                        "status": MessageStatus.DELETED,
                        "content": "此訊息已被刪除",
                        "edited": True,
                        "edited_at": datetime.now(UTC)
                    }
                }
            )
            
            if success:
                logger.info(f"Message {message_id} soft deleted")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
            return False
    
    async def get_room_messages(
        self,
        room_id: str,
        skip: int = 0,
        limit: int = 20,
        message_type: Optional[MessageType] = None,
        user_id: Optional[str] = None,
        include_deleted: bool = False
    ) -> List[MessageInDB]:
        """
        獲取房間訊息列表
        
        Args:
            room_id: 房間 ID
            skip: 跳過的訊息數
            limit: 返回的訊息數限制
            message_type: 訊息類型篩選
            user_id: 使用者 ID 篩選
            include_deleted: 是否包含已刪除的訊息
            
        Returns:
            List[MessageInDB]: 訊息列表
        """
        try:
            # 構建查詢條件
            query = {"room_id": room_id}
            if not include_deleted:
                query["status"] = {"$ne": MessageStatus.DELETED}
            if message_type:
                query["message_type"] = message_type
            if user_id:
                query["user_id"] = user_id
            
            # 查詢
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            # 轉換為 MessageInDB 物件
            messages = []
            for doc in documents:
                messages.append(MessageInDB(**doc))
            
            # 反轉順序（最舊的在前面）
            messages.reverse()
            
            return messages
        except Exception as e:
            logger.error(f"Error getting room messages: {e}")
            return []
    
    async def get_recent_messages(self, room_id: str, limit: int = 50) -> List[MessageResponse]:
        """
        獲取房間最近的訊息
        
        Args:
            room_id: 房間 ID
            limit: 訊息數量限制
            
        Returns:
            List[MessageResponse]: 最近的訊息列表
        """
        try:
            query = {
                "room_id": room_id,
                "status": {"$ne": MessageStatus.DELETED}
            }
            
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=0, limit=limit, sort=sort)
            
            # 反轉順序（最舊的在前面）
            documents.reverse()
            
            # 格式化訊息
            formatted_messages = []
            for doc in documents:
                # 將 _id 轉換為 id 字段
                if "_id" in doc:
                    doc["id"] = doc.pop("_id")
                formatted_messages.append(MessageResponse(**doc))
            
            return formatted_messages
        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []
    
    async def search_messages(
        self,
        room_id: str,
        search_query: MessageSearchQuery
    ) -> MessageListResponse:
        """
        搜尋房間訊息
        
        Args:
            room_id: 房間 ID
            search_query: 搜尋查詢
            
        Returns:
            MessageListResponse: 搜尋結果
        """
        try:
            # 構建搜尋查詢
            query = {
                "room_id": room_id,
                "status": {"$ne": MessageStatus.DELETED}
            }
            
            if search_query.keyword:
                query["content"] = {"$regex": search_query.keyword, "$options": "i"}
            
            if search_query.message_type:
                query["message_type"] = search_query.message_type
            
            if search_query.user_id:
                query["user_id"] = search_query.user_id
            
            if search_query.start_date or search_query.end_date:
                date_query = {}
                if search_query.start_date:
                    date_query["$gte"] = search_query.start_date
                if search_query.end_date:
                    date_query["$lte"] = search_query.end_date
                query["created_at"] = date_query
            
            # 計算總數
            total = await self.count_documents(query)
            
            # 分頁查詢
            skip = (search_query.page - 1) * search_query.page_size
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=search_query.page_size, sort=sort)
            
            # 格式化結果
            formatted_messages = []
            for doc in documents:
                # 將 _id 轉換為 id 字段
                if "_id" in doc:
                    doc["id"] = doc.pop("_id")
                formatted_messages.append(MessageResponse(**doc))
            
            return MessageListResponse(
                messages=formatted_messages,
                total=total,
                page=search_query.page,
                page_size=search_query.page_size,
                has_next=skip + search_query.page_size < total,
                has_prev=search_query.page > 1
            )
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return MessageListResponse(
                messages=[],
                total=0,
                page=search_query.page,
                page_size=search_query.page_size,
                has_next=False,
                has_prev=False
            )
    
    async def get_message_stats(self, room_id: str) -> MessageStats:
        """
        獲取房間訊息統計
        
        Args:
            room_id: 房間 ID
            
        Returns:
            MessageStats: 訊息統計資料
        """
        try:
            # 基本查詢條件
            base_query = {"room_id": room_id, "status": {"$ne": MessageStatus.DELETED}}
            
            # 總訊息數
            total_messages = await self.count_documents(base_query)
            
            # 今日訊息數
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            messages_today = await self.count_documents({
                **base_query,
                "created_at": {"$gte": today_start}
            })
            
            # 本週訊息數
            week_start = today_start - timedelta(days=today_start.weekday())
            messages_this_week = await self.count_documents({
                **base_query,
                "created_at": {"$gte": week_start}
            })
            
            # 本月訊息數
            month_start = today_start.replace(day=1)
            messages_this_month = await self.count_documents({
                **base_query,
                "created_at": {"$gte": month_start}
            })
            
            # 訊息類型統計
            message_types_pipeline = [
                {"$match": base_query},
                {"$group": {"_id": "$message_type", "count": {"$sum": 1}}}
            ]
            message_types_result = await self.aggregate(message_types_pipeline)
            message_types = {item["_id"]: item["count"] for item in message_types_result}
            
            # 最活躍用戶統計
            top_users_pipeline = [
                {"$match": base_query},
                {"$group": {"_id": "$user_id", "username": {"$first": "$username"}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 10}
            ]
            top_users_result = await self.aggregate(top_users_pipeline)
            top_users = [
                {"user_id": item["_id"], "username": item["username"], "message_count": item["count"]}
                for item in top_users_result
            ]
            
            return MessageStats(
                total_messages=total_messages,
                messages_today=messages_today,
                messages_this_week=messages_this_week,
                messages_this_month=messages_this_month,
                message_types=message_types,
                top_users=top_users
            )
        except Exception as e:
            logger.error(f"Error getting message stats: {e}")
            return MessageStats(
                total_messages=0,
                messages_today=0,
                messages_this_week=0,
                messages_this_month=0,
                message_types={},
                top_users=[]
            )
    
    async def mark_messages_as_read(self, room_id: str, user_id: str) -> int:
        """
        將房間內的訊息標記為已讀
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            int: 標記的訊息數量
        """
        try:
            # 更新訊息狀態為已讀（排除自己的訊息）
            modified_count = await self.update_many(
                {
                    "room_id": room_id,
                    "user_id": {"$ne": user_id},
                    "status": MessageStatus.SENT
                },
                {
                    "$set": {
                        "status": MessageStatus.READ
                    }
                }
            )
            
            return modified_count
        except Exception as e:
            logger.error(f"Error marking messages as read: {e}")
            return 0
    
    async def get_unread_count(self, room_id: str, user_id: str) -> int:
        """
        獲取未讀訊息數量
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            int: 未讀訊息數量
        """
        try:
            count = await self.count_documents({
                "room_id": room_id,
                "user_id": {"$ne": user_id},
                "status": MessageStatus.SENT
            })
            
            return count
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0
    
    async def get_user_message_stats(self, user_id: str) -> Dict[str, Any]:
        """
        獲取使用者訊息統計
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            Dict[str, Any]: 使用者訊息統計資料
        """
        try:
            # 總訊息數
            total_messages = await self.count_documents({
                "user_id": user_id,
                "status": {"$ne": MessageStatus.DELETED}
            })
            
            # 今日訊息數
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            today_messages = await self.count_documents({
                "user_id": user_id,
                "status": {"$ne": MessageStatus.DELETED},
                "created_at": {"$gte": today_start}
            })
            
            # 本週訊息數
            week_start = today_start - timedelta(days=today_start.weekday())
            week_messages = await self.count_documents({
                "user_id": user_id,
                "status": {"$ne": MessageStatus.DELETED},
                "created_at": {"$gte": week_start}
            })
            
            return {
                "total_messages": total_messages,
                "today_messages": today_messages,
                "week_messages": week_messages
            }
        except Exception as e:
            logger.error(f"Error getting user message stats: {e}")
            return {
                "total_messages": 0,
                "today_messages": 0,
                "week_messages": 0
            }
    
    async def get_messages_by_user(
        self,
        room_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> List[MessageInDB]:
        """
        獲取特定使用者在房間的訊息
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            page: 頁數
            page_size: 每頁大小
            
        Returns:
            List[MessageInDB]: 訊息列表
        """
        try:
            skip = (page - 1) * page_size
            return await self.get_room_messages(
                room_id=room_id,
                skip=skip,
                limit=page_size,
                user_id=user_id
            )
        except Exception as e:
            logger.error(f"Error getting messages by user: {e}")
            return []
    
    async def delete_messages_by_user(self, room_id: str, user_id: str) -> int:
        """
        刪除特定使用者在房間的所有訊息
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            int: 刪除的訊息數量
        """
        try:
            modified_count = await self.update_many(
                {
                    "room_id": room_id,
                    "user_id": user_id,
                    "status": {"$ne": MessageStatus.DELETED}
                },
                {
                    "$set": {
                        "status": MessageStatus.DELETED,
                        "content": "此訊息已被刪除",
                        "edited": True,
                        "edited_at": datetime.now(UTC)
                    }
                }
            )
            
            logger.info(f"Deleted {modified_count} messages by user {user_id} in room {room_id}")
            return modified_count
        except Exception as e:
            logger.error(f"Error deleting messages by user: {e}")
            return 0
    
    async def delete_by_room_id(self, room_id: str) -> int:
        """
        刪除房間的所有訊息（硬刪除）
        
        Args:
            room_id: 房間 ID
            
        Returns:
            int: 刪除的訊息數量
        """
        try:
            # 直接從資料庫刪除所有該房間的訊息
            deleted_count = await self.delete_many({
                "room_id": room_id
            })
            
            logger.info(f"Deleted {deleted_count} messages from room {room_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting messages by room: {e}")
            return 0
    
    async def get_message_count_by_user(self, room_id: str, user_id: str) -> int:
        """
        獲取特定使用者在房間的訊息數量
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            int: 訊息數量
        """
        try:
            count = await self.count_documents({
                "room_id": room_id,
                "user_id": user_id,
                "status": {"$ne": MessageStatus.DELETED}
            })
            
            return count
        except Exception as e:
            logger.error(f"Error getting message count by user: {e}")
            return 0
    
    async def create_indexes(self):
        """創建必要的索引"""
        try:
            # 房間和創建時間複合索引
            await self.create_index([
                ("room_id", 1),
                ("created_at", -1)
            ])
            
            # 房間、類型和創建時間複合索引
            await self.create_index([
                ("room_id", 1),
                ("message_type", 1),
                ("created_at", -1)
            ])
            
            # 使用者和房間複合索引
            await self.create_index([
                ("user_id", 1),
                ("room_id", 1),
                ("created_at", -1)
            ])
            
            # 狀態索引
            await self.create_index([("status", 1)])
            
            # 回覆索引
            await self.create_index([("reply_to", 1)])
            
            # 全文搜尋索引
            await self.create_index([("content", "text")])
            
            logger.info("Message indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating message indexes: {e}")
    
    async def cleanup_old_messages(self, days: int = 30) -> int:
        """
        清理舊訊息
        
        Args:
            days: 保留天數
            
        Returns:
            int: 清理的訊息數量
        """
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)
            
            deleted_count = await self.delete_many({
                "created_at": {"$lt": cutoff_date},
                "status": MessageStatus.DELETED
            })
            
            logger.info(f"Cleaned up {deleted_count} old messages")
            return deleted_count
        except Exception as e:
            logger.error(f"Error cleaning up old messages: {e}")
            return 0