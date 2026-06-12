"""訊息資料存取層"""

import logging
import re
from datetime import UTC, datetime

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase

from app.models.message import (
    MessageInDB,
    MessageListResponse,
    MessageResponse,
    MessageSearchQuery,
    MessageStatus,
    MessageType,
    MessageUpdate,
    MessageWithReply,
    ReplyToMessage,
)
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository[MessageInDB]):
    """訊息資料存取類別"""

    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "messages")

    def _to_model(self, document: dict) -> MessageInDB:
        return MessageInDB(**document)

    async def next_room_seq(self, room_id: str) -> int:
        """
        取得房間的下一個訊息序號（原子遞增）

        使用 counters collection 的 findOneAndUpdate $inc，
        MongoDB 為單一事實來源：原子、持久、崩潰不會回退。
        序號保證單調遞增，但允許有空洞（建立訊息失敗時該序號作廢）。

        Args:
            room_id: 房間 ID

        Returns:
            int: 該房間的下一個序號（從 1 開始）
        """
        document = await self.db["counters"].find_one_and_update(
            {"_id": f"room_seq:{room_id}"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return document["seq"]

    async def get_by_client_id(
        self, room_id: str, client_id: str
    ) -> MessageInDB | None:
        """
        根據 (room_id, client_id) 查詢訊息（冪等去重用）

        Args:
            room_id: 房間 ID
            client_id: 客戶端產生的訊息 ID

        Returns:
            Optional[MessageInDB]: 訊息物件，不存在則返回 None
        """
        document = await self.find_one({"room_id": room_id, "client_id": client_id})
        if document:
            return self._to_model(document)
        return None

    async def get_with_reply(self, message_id: str) -> MessageWithReply | None:
        """
        根據 ID 獲取訊息（包含回覆資訊）

        Args:
            message_id: 訊息 ID

        Returns:
            Optional[MessageWithReply]: 包含回覆資訊的訊息物件，如果不存在則返回 None
        """
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
                    created_at=reply_msg.created_at,
                )

        return MessageWithReply(
            **message_response.model_dump(), reply_to_message=reply_to_message
        )

    async def create(self, message: MessageInDB) -> MessageInDB | None:
        """
        創建新訊息

        Args:
            message: 訊息物件

        Returns:
            Optional[MessageInDB]: 創建後的訊息物件，如果失敗則返回 None
        """
        # 準備文檔
        message_dict = message.model_dump(exclude={"id"})
        # created_at / updated_at 由 base.insert_one 統一設置（含毫秒截斷）
        message_dict["status"] = MessageStatus.SENT

        # 插入文檔
        await self.insert_one(message_dict)
        # 從記憶體重建（避免 re-fetch），pymongo 已注入 _id
        self._normalize_id(message_dict)
        for key, val in message_dict.items():
            if isinstance(val, datetime):
                message_dict[key] = val.replace(tzinfo=None)
        return self._to_model(message_dict)

    async def update(
        self, message_id: str, message_update: MessageUpdate
    ) -> MessageInDB | None:
        """
        更新訊息

        Args:
            message_id: 訊息 ID
            message_update: 更新資料

        Returns:
            Optional[MessageInDB]: 更新後的訊息物件，如果失敗則返回 None
        """
        # 準備更新資料
        update_data = {}
        if message_update.content is not None:
            update_data["content"] = message_update.content
            update_data["edited"] = True
            _now = datetime.now(UTC)
            update_data["edited_at"] = _now.replace(
                microsecond=_now.microsecond // 1000 * 1000
            )

        if message_update.status is not None:
            update_data["status"] = message_update.status

        if message_update.metadata is not None:
            update_data["metadata"] = message_update.metadata

        if not update_data:
            # 沒有需要更新的資料
            return await self.get_by_id(message_id)

        # 執行更新
        success = await self.update_one(
            {"_id": ObjectId(message_id)}, {"$set": update_data}
        )

        if success:
            return await self.get_by_id(message_id)

        return None

    async def delete(self, message_id: str) -> bool:
        """
        刪除訊息（軟刪除）

        Args:
            message_id: 訊息 ID

        Returns:
            bool: 是否刪除成功
        """
        # 軟刪除：更新狀態和內容
        _now = datetime.now(UTC)
        edited_at = _now.replace(microsecond=_now.microsecond // 1000 * 1000)
        success = await self.update_one(
            {"_id": ObjectId(message_id)},
            {
                "$set": {
                    "status": MessageStatus.DELETED,
                    "content": "此訊息已被刪除",
                    "edited": True,
                    "edited_at": edited_at,
                }
            },
        )

        if success:
            logger.info(f"Message {message_id} soft deleted")
            return True

        return False

    async def get_room_messages(
        self,
        room_id: str,
        skip: int = 0,
        limit: int = 20,
        message_type: MessageType | None = None,
        user_id: str | None = None,
        include_deleted: bool = False,
        before_seq: int | None = None,
    ) -> list[MessageInDB]:
        """
        獲取房間訊息列表

        Args:
            room_id: 房間 ID
            skip: 跳過的訊息數
            limit: 返回的訊息數限制
            message_type: 訊息類型篩選
            user_id: 使用者 ID 篩選
            include_deleted: 是否包含已刪除的訊息
            before_seq: 游標分頁——只取序號小於此值的訊息（提供時忽略 skip）

        Returns:
            List[MessageInDB]: 訊息列表
        """
        # 構建查詢條件
        query = {"room_id": room_id}
        if not include_deleted:
            query["status"] = {"$ne": MessageStatus.DELETED}
        if message_type:
            query["message_type"] = message_type
        if user_id:
            query["user_id"] = user_id

        # 游標分頁：以 seq 為游標，不受訊息增刪造成的偏移影響
        if before_seq is not None:
            query["seq"] = {"$lt": before_seq}
            sort = [("seq", -1)]
            documents = await self.find_many(query, skip=0, limit=limit, sort=sort)
        else:
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)

        messages = [self._to_model(doc) for doc in documents]
        messages.reverse()  # 反轉順序（最舊的在前面）

        return messages

    async def count_after_seq(self, room_id: str, after_seq: int) -> int:
        """
        計算房間內序號大於 after_seq 的訊息數（gap 大小估算）

        Args:
            room_id: 房間 ID
            after_seq: 客戶端已知的最後序號

        Returns:
            int: gap 訊息數
        """
        return await self.count_documents(
            {
                "room_id": room_id,
                "seq": {"$gt": after_seq},
                "status": {"$ne": MessageStatus.DELETED},
            }
        )

    async def get_after_seq(
        self, room_id: str, after_seq: int, limit: int = 200
    ) -> list[MessageInDB]:
        """
        獲取房間內序號大於 after_seq 的訊息（斷線 gap 補發）

        Args:
            room_id: 房間 ID
            after_seq: 客戶端已知的最後序號
            limit: 返回的訊息數上限

        Returns:
            List[MessageInDB]: 訊息列表（序號由小到大）
        """
        documents = await self.find_many(
            {
                "room_id": room_id,
                "seq": {"$gt": after_seq},
                "status": {"$ne": MessageStatus.DELETED},
            },
            skip=0,
            limit=limit,
            sort=[("seq", 1)],
        )
        return [self._to_model(doc) for doc in documents]

    async def search_messages(
        self, room_id: str, search_query: MessageSearchQuery
    ) -> MessageListResponse:
        """
        搜尋房間訊息

        Args:
            room_id: 房間 ID
            search_query: 搜尋查詢

        Returns:
            MessageListResponse: 搜尋結果
        """
        # 構建搜尋查詢
        query = {"room_id": room_id, "status": {"$ne": MessageStatus.DELETED}}

        if search_query.keyword:
            escaped_keyword = re.escape(search_query.keyword)
            query["content"] = {"$regex": escaped_keyword, "$options": "i"}

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
        documents = await self.find_many(
            query, skip=skip, limit=search_query.page_size, sort=sort
        )

        # 格式化結果（find_many 已透過 _normalize_id 處理 _id → id）
        formatted_messages = [MessageResponse(**doc) for doc in documents]

        return MessageListResponse(
            messages=formatted_messages,
            total=total,
            page=search_query.page,
            page_size=search_query.page_size,
            has_next=skip + search_query.page_size < total,
            has_prev=search_query.page > 1,
        )

    async def delete_by_room_id(self, room_id: str) -> int:
        """
        刪除房間的所有訊息（硬刪除）

        Args:
            room_id: 房間 ID

        Returns:
            int: 刪除的訊息數量
        """
        # 直接從資料庫刪除所有該房間的訊息
        deleted_count = await self.delete_many({"room_id": room_id})

        logger.info(f"Deleted {deleted_count} messages from room {room_id}")
        return deleted_count
