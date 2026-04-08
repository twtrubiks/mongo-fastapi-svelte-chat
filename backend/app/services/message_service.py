"""訊息服務層"""

import logging
from datetime import UTC, datetime

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.message import (
    MessageCreate,
    MessageInDB,
    MessageListResponse,
    MessageResponse,
    MessageSearchQuery,
    MessageType,
    MessageUpdate,
    MessageWithReply,
)
from app.repositories.message_repository import MessageRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class MessageService:
    """訊息服務類別"""

    def __init__(
        self,
        message_repository: MessageRepository,
        room_repository: RoomRepository,
        user_repository: UserRepository,
    ):
        self.message_repo = message_repository
        self.room_repo = room_repository
        self.user_repo = user_repository

    # 訊息長度限制（依類型區分）
    MAX_CONTENT_LENGTH = {"image": 2000, "file": 2000, "default": 1000}

    @staticmethod
    def validate_message_content(content: str, message_type: str = "text") -> str:
        """
        驗證訊息內容（商業邏輯，集中管理）

        Args:
            content: 訊息內容
            message_type: 訊息類型

        Returns:
            str: 處理後的內容（已 strip）

        Raises:
            ValueError: 當內容無效時
        """
        content = content.strip()
        if not content:
            raise AppError("訊息內容不能為空")

        max_length = MessageService.MAX_CONTENT_LENGTH.get(
            message_type, MessageService.MAX_CONTENT_LENGTH["default"]
        )
        if len(content) > max_length:
            raise AppError(f"訊息內容太長（最大 {max_length} 字元）")

        return content

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
            raise NotFoundError("房間不存在")
        logger.info(f"Room {room_id} found")

        # 驗證使用者是否為房間成員
        logger.info(f"Checking if user {user_id} is member of room {room_id}")
        is_member = await self.room_repo.is_member(room_id, user_id)
        logger.info(f"User {user_id} is member of room {room_id}: {is_member}")
        if not is_member:
            raise ForbiddenError("使用者不是該房間的成員")

        # 獲取使用者資訊
        logger.info(f"Getting user info for user {user_id}")
        user_repo = self.user_repo
        user = await user_repo.get_by_id(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            raise NotFoundError("使用者不存在")
        logger.info(f"User {user_id} found: {user.username}")

        # 驗證 reply_to 訊息是否存在且在同一房間
        if message_data.reply_to:
            logger.info(f"Validating reply_to message: {message_data.reply_to}")
            reply_message = await self.message_repo.get_by_id(message_data.reply_to)
            if not reply_message:
                logger.error(f"Reply_to message {message_data.reply_to} not found")
                raise NotFoundError("回覆的訊息不存在")
            if reply_message.room_id != room_id:
                raise AppError("不能跨房間回覆訊息")
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

        logger.info(f"Creating message for user {user_id} in room {room_id}")
        created_message = await self.message_repo.create(message_doc)
        logger.info(f"Message created: {created_message.id} by user {user_id}")
        return MessageResponse(**created_message.model_dump())

    async def get_message_by_id(self, message_id: str) -> MessageWithReply:
        """
        根據 ID 獲取訊息

        Args:
            message_id: 訊息 ID

        Returns:
            MessageWithReply: 訊息資料（包含回覆資訊）

        Raises:
            NotFoundError: 訊息不存在時
        """
        message = await self.message_repo.get_with_reply(message_id)
        if not message:
            raise NotFoundError("訊息不存在")
        return message

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

        # 批次查詢使用者頭像
        unique_user_ids = list({msg.user_id for msg in messages})
        avatar_map: dict[str, str | None] = {}
        if unique_user_ids:
            users = await self.user_repo.get_by_ids(unique_user_ids)
            avatar_map = {u.id: u.avatar for u in users if u.id}

        # 將 MessageInDB 轉換為 MessageResponse - 利用 MongoDB 反規範化優勢
        formatted_messages = []
        for msg in messages:
            # 準備訊息數據，確保 _id 映射到 id
            msg_dict = msg.model_dump()
            if "_id" in msg_dict:
                msg_dict["id"] = msg_dict.pop("_id")

            msg_dict["avatar"] = avatar_map.get(msg.user_id)
            formatted_messages.append(MessageResponse(**msg_dict))

        return formatted_messages

    async def update_message(
        self, message_id: str, user_id: str, update_data: MessageUpdate
    ) -> MessageResponse:
        """
        更新訊息

        Args:
            message_id: 訊息 ID
            user_id: 更新者 ID
            update_data: 更新資料

        Returns:
            MessageResponse: 更新後的訊息

        Raises:
            NotFoundError: 訊息不存在時
            ForbiddenError: 無權限時
        """
        # 獲取訊息
        message = await self.message_repo.get_by_id(message_id)
        if not message:
            raise NotFoundError("訊息不存在")

        # 檢查權限
        if message.user_id != user_id:
            raise ForbiddenError("您只能編輯自己的訊息")

        # 更新訊息
        updated_message = await self.message_repo.update(message_id, update_data)
        if not updated_message:
            raise NotFoundError("訊息不存在")
        logger.info(f"Message updated: {message_id} by user {user_id}")
        return MessageResponse(**updated_message.model_dump())

    async def delete_message(self, message_id: str, user_id: str) -> None:
        """
        刪除訊息（軟刪除）

        Args:
            message_id: 訊息 ID
            user_id: 刪除者 ID

        Raises:
            NotFoundError: 訊息不存在時
            ForbiddenError: 無權限時
        """
        # 獲取訊息
        message = await self.message_repo.get_by_id(message_id)
        if not message:
            raise NotFoundError("訊息不存在")

        # 檢查權限
        if message.user_id != user_id:
            raise ForbiddenError("您只能刪除自己的訊息")

        # 刪除訊息
        success = await self.message_repo.delete(message_id)
        if not success:
            raise NotFoundError("訊息不存在")
        logger.info(f"Message deleted: {message_id} by user {user_id}")

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
