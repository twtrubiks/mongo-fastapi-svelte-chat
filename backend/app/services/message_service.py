"""訊息服務層"""

import logging
from datetime import UTC, datetime

from app.models.message import (
    MessageCreate,
    MessageInDB,
    MessageListResponse,
    MessageResponse,
    MessageSearchQuery,
    MessageStats,
    MessageType,
    MessageUpdate,
    MessageWithReply,
)
from app.repositories.message_repository import MessageRepository
from app.repositories.room_repository import RoomRepository

UTC = UTC

logger = logging.getLogger(__name__)


class MessageService:
    """訊息服務類別"""

    def __init__(
        self, message_repository: MessageRepository, room_repository: RoomRepository
    ):
        self.message_repo = message_repository
        self.room_repo = room_repository

    async def create_message(
        self, user_id: str, message_data: MessageCreate
    ) -> MessageResponse:
        """
        創建新訊息

        Args:
            user_id: 使用者 ID
            message_data: 訊息資料 (包含 room_id)

        Returns:
            MessageResponse: 創建的訊息

        Raises:
            ValueError: 當參數無效時
            Exception: 當資料庫操作失敗時
        """
        # 從 message_data 中獲取 room_id
        room_id = message_data.room_id

        # 驗證房間是否存在
        logger.info(f"Checking if room {room_id} exists")
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            logger.error(f"Room {room_id} not found")
            raise ValueError("房間不存在")
        logger.info(f"Room {room_id} found")

        # 驗證使用者是否為房間成員
        logger.info(f"Checking if user {user_id} is member of room {room_id}")
        is_member = await self.room_repo.is_member(room_id, user_id)
        logger.info(f"User {user_id} is member of room {room_id}: {is_member}")
        if not is_member:
            raise ValueError("使用者不是該房間的成員")

        # 獲取使用者資訊
        logger.info(f"Getting user info for user {user_id}")
        from app.repositories.user_repository import UserRepository

        user_repo = UserRepository(self.message_repo.db)
        user = await user_repo.get_by_id(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            raise ValueError("使用者不存在")
        logger.info(f"User {user_id} found: {user.username}")

        # 驗證 reply_to 訊息是否存在
        if message_data.reply_to:
            logger.info(f"Validating reply_to message: {message_data.reply_to}")
            reply_message = await self.message_repo.get_by_id(message_data.reply_to)
            if not reply_message:
                logger.error(f"Reply_to message {message_data.reply_to} not found")
                raise ValueError("回覆的訊息不存在")
            logger.info(f"Reply_to message {message_data.reply_to} found")

        # 創建訊息
        message_doc = MessageInDB(
            room_id=room_id,
            user_id=user_id,
            username=user.username,
            content=message_data.content,
            message_type=message_data.message_type,
            reply_to=message_data.reply_to,
            metadata=message_data.metadata,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        try:
            logger.info(f"Creating message for user {user_id} in room {room_id}")
            created_message = await self.message_repo.create(message_doc)
            if created_message:
                logger.info(f"Message created: {created_message.id} by user {user_id}")
                return MessageResponse(**created_message.model_dump())
            else:
                logger.error("Message creation returned None")
                raise Exception("創建訊息失敗")

        except Exception as e:
            logger.error(f"Error creating message: {e}", exc_info=True)
            # 避免遞歸錯誤訊息
            if "創建訊息失敗" in str(e):
                raise e from e
            else:
                raise Exception(f"創建訊息失敗: {str(e)}") from e

    async def get_message_by_id(self, message_id: str) -> MessageWithReply | None:
        """
        根據 ID 獲取訊息

        Args:
            message_id: 訊息 ID

        Returns:
            Optional[MessageWithReply]: 訊息資料（包含回覆資訊）
        """
        return await self.message_repo.get_with_reply(message_id)

    async def get_room_messages(
        self,
        room_id: str,
        skip: int = 0,
        limit: int = 20,
        message_type: MessageType | None = None,
        user_id: str | None = None,
    ) -> list[MessageResponse]:
        """
        獲取房間訊息列表

        Args:
            room_id: 房間 ID
            skip: 跳過的訊息數
            limit: 返回的訊息數限制
            message_type: 訊息類型篩選
            user_id: 使用者 ID 篩選

        Returns:
            List[MessageResponse]: 訊息列表
        """
        messages = await self.message_repo.get_room_messages(
            room_id=room_id,
            skip=skip,
            limit=limit,
            message_type=message_type,
            user_id=user_id,
        )

        # 將 MessageInDB 轉換為 MessageResponse - 利用 MongoDB 反規範化優勢
        formatted_messages = []
        for msg in messages:
            # 準備訊息數據，確保 _id 映射到 id
            msg_dict = msg.model_dump()
            if "_id" in msg_dict:
                msg_dict["id"] = msg_dict.pop("_id")

            # 直接使用 MessageInDB 中的 username，無需額外查詢
            formatted_messages.append(MessageResponse(**msg_dict))

        return formatted_messages

    async def update_message(
        self, message_id: str, user_id: str, update_data: MessageUpdate
    ) -> MessageResponse | None:
        """
        更新訊息

        Args:
            message_id: 訊息 ID
            user_id: 更新者 ID
            update_data: 更新資料

        Returns:
            Optional[MessageResponse]: 更新後的訊息

        Raises:
            ValueError: 當參數無效或無權限時
        """
        # 獲取訊息
        message = await self.message_repo.get_by_id(message_id)
        if not message:
            return None

        # 檢查權限
        if message.user_id != user_id:
            raise ValueError("您只能編輯自己的訊息")

        # 更新訊息
        updated_message = await self.message_repo.update(message_id, update_data)
        if updated_message:
            logger.info(f"Message updated: {message_id} by user {user_id}")
            return MessageResponse(**updated_message.model_dump())

        return None

    async def delete_message(self, message_id: str, user_id: str) -> bool:
        """
        刪除訊息（軟刪除）

        Args:
            message_id: 訊息 ID
            user_id: 刪除者 ID

        Returns:
            bool: 是否成功刪除

        Raises:
            ValueError: 當參數無效或無權限時
        """
        # 獲取訊息
        message = await self.message_repo.get_by_id(message_id)
        if not message:
            return False

        # 檢查權限
        if message.user_id != user_id:
            raise ValueError("您只能刪除自己的訊息")

        # 刪除訊息
        success = await self.message_repo.delete(message_id)
        if success:
            logger.info(f"Message deleted: {message_id} by user {user_id}")
            return True

        return False

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
        return await self.message_repo.search_messages(room_id, search_query)

    async def get_message_stats(self, room_id: str) -> MessageStats:
        """
        獲取房間訊息統計

        Args:
            room_id: 房間 ID

        Returns:
            MessageStats: 訊息統計資料
        """
        return await self.message_repo.get_message_stats(room_id)

    async def get_recent_messages(
        self, room_id: str, limit: int = 50
    ) -> list[MessageResponse]:
        """
        獲取房間最近的訊息

        Args:
            room_id: 房間 ID
            limit: 訊息數量限制

        Returns:
            List[MessageResponse]: 最近的訊息列表
        """
        return await self.message_repo.get_recent_messages(room_id, limit)

    async def mark_messages_as_read(self, room_id: str, user_id: str) -> int:
        """
        將房間內的訊息標記為已讀

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID

        Returns:
            int: 標記的訊息數量
        """
        return await self.message_repo.mark_messages_as_read(room_id, user_id)

    async def get_unread_count(self, room_id: str, user_id: str) -> int:
        """
        獲取未讀訊息數量

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID

        Returns:
            int: 未讀訊息數量
        """
        return await self.message_repo.get_unread_count(room_id, user_id)
