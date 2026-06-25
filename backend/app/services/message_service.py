"""訊息服務層"""

import logging
from datetime import UTC, datetime

from pymongo.errors import DuplicateKeyError

from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.message import (
    MAX_CONTENT_LENGTH,
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

# 斷線 gap 補發上限：超過此數量改為全量重載（避免一次推送過多訊息）
SYNC_MAX_GAP = 200


class MessageService:
    """訊息服務類別"""

    def __init__(
        self,
        message_repository: MessageRepository,
        room_repository: RoomRepository,
        user_repository: UserRepository,
        connection_manager=None,
    ):
        self.message_repo = message_repository
        self.room_repo = room_repository
        self.user_repo = user_repository
        self._connection_manager = connection_manager

    @staticmethod
    def validate_message_content(content: str) -> str:
        """
        驗證訊息內容（商業邏輯，集中管理）

        Args:
            content: 訊息內容

        Returns:
            str: 處理後的內容（已 strip）

        Raises:
            AppError: 當內容無效時
        """
        content = content.strip()
        if not content:
            raise AppError("訊息內容不能為空")

        if len(content) > MAX_CONTENT_LENGTH:
            raise AppError(f"訊息內容太長（最大 {MAX_CONTENT_LENGTH} 字元）")

        return content

    async def create_message(
        self,
        user_id: str,
        message_data: MessageCreate,
        skip_membership_check: bool = False,
    ) -> MessageResponse:
        """
        創建新訊息

        Args:
            user_id: 使用者 ID
            message_data: 訊息資料 (包含 room_id)
            skip_membership_check: 是否跳過成員資格檢查（僅供系統 bot 以固定身分
                發訊息使用——bot 不是房間成員；一般使用者一律維持 False）

        Returns:
            MessageResponse: 創建的訊息

        Raises:
            ValueError: 當參數無效時
            Exception: 當資料庫操作失敗時
        """
        # 驗證訊息內容（在 DB 查詢之前快速失敗）
        validated_content = self.validate_message_content(message_data.content)

        # 從 message_data 中獲取 room_id
        room_id = message_data.room_id

        # 驗證房間是否存在
        logger.info(f"Checking if room {room_id} exists")
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            logger.error(f"Room {room_id} not found")
            raise NotFoundError("房間不存在")
        logger.info(f"Room {room_id} found")

        # 驗證使用者是否為房間成員（系統 bot 以固定身分發訊息時跳過）
        if not skip_membership_check:
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

        # 冪等去重：客戶端重送相同 client_id 時直接回傳既有訊息（快速路徑）。
        # 必須放在成員資格驗證之後，避免非成員以 (room_id, client_id) 探測訊息內容。
        if message_data.client_id:
            existing = await self.message_repo.get_by_client_id(
                room_id, message_data.client_id
            )
            if existing:
                logger.info(
                    f"Idempotent resend detected: client_id={message_data.client_id}"
                )
                return MessageResponse(**existing.model_dump())

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

        # 取得房間內單調遞增序號（允許空洞：建立失敗時該序號作廢）
        seq = await self.message_repo.next_room_seq(room_id)

        # 創建訊息
        message_doc = MessageInDB(
            room_id=room_id,
            user_id=user_id,
            username=user.username,
            content=validated_content,
            message_type=message_data.message_type,
            reply_to=message_data.reply_to,
            metadata=message_data.metadata,
            seq=seq,
            client_id=message_data.client_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        logger.info(f"Creating message for user {user_id} in room {room_id}")
        try:
            created_message = await self.message_repo.create(message_doc)
        except DuplicateKeyError:
            # 併發重送撞 (room_id, client_id) 唯一索引：
            # 這不是基礎設施錯誤，而是冪等契約的預期結果——回傳既有訊息。
            # （僅在 client_id 存在時可能發生，messages 沒有其他唯一索引）
            if message_data.client_id:
                existing = await self.message_repo.get_by_client_id(
                    room_id, message_data.client_id
                )
                if existing:
                    logger.info(
                        f"Idempotent resend (race): client_id={message_data.client_id}"
                    )
                    return MessageResponse(**existing.model_dump())
            raise
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
        before_seq: int | None = None,
    ) -> list[MessageResponse]:
        """
        獲取房間訊息列表

        Args:
            room_id: 房間 ID
            skip: 跳過的訊息數
            limit: 返回的訊息數限制
            message_type: 訊息類型篩選
            user_id: 使用者 ID 篩選
            before_seq: 游標分頁——只取序號小於此值的訊息

        Returns:
            List[MessageResponse]: 訊息列表
        """
        messages = await self.message_repo.get_room_messages(
            room_id=room_id,
            skip=skip,
            limit=limit,
            message_type=message_type,
            user_id=user_id,
            before_seq=before_seq,
        )
        return await self._format_with_avatars(messages)

    async def get_room_messages_for_context(
        self,
        room_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> list[MessageInDB]:
        """獲取房間近期訊息（領域模型，不補頭像）。

        供 @bot 多輪歷史、/summary transcript 等純文字用途——這些呼叫端只需
        username/content，不渲染頭像。相較 get_room_messages 省去
        _format_with_avatars 的批次使用者查詢（一次 $in），避免無謂 DB 往返。

        Returns:
            list[MessageInDB]: 訊息列表（最舊→最新排序）
        """
        return await self.message_repo.get_room_messages(
            room_id=room_id, skip=skip, limit=limit
        )

    async def sync_messages_since(
        self, room_id: str, last_seq: int, max_gap: int = SYNC_MAX_GAP
    ) -> tuple[list[MessageResponse], bool]:
        """
        斷線重連補發：回傳序號大於 last_seq 的訊息

        gap 超過 max_gap 時改為全量重載（回傳最新訊息 + full_reload 標記），
        避免長時間離線後一次推送過多訊息。

        Args:
            room_id: 房間 ID
            last_seq: 客戶端已知的最後序號
            max_gap: gap 上限，超過則全量重載

        Returns:
            tuple[list[MessageResponse], bool]: (訊息列表, 是否全量重載)
        """
        gap_count = await self.message_repo.count_after_seq(room_id, last_seq)

        if gap_count == 0:
            return [], False

        if gap_count > max_gap:
            # gap 過大：回傳最新 50 條，客戶端應清空重載
            messages = await self.get_room_messages(room_id, skip=0, limit=50)
            return messages, True

        messages = await self.message_repo.get_after_seq(
            room_id, last_seq, limit=max_gap
        )
        return await self._format_with_avatars(messages), False

    async def _format_with_avatars(
        self, messages: list[MessageInDB]
    ) -> list[MessageResponse]:
        """將 MessageInDB 轉為 MessageResponse 並批次補上使用者頭像"""
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

        # 驗證訊息內容
        if update_data.content is not None:
            update_data.content = self.validate_message_content(update_data.content)

        # 更新訊息
        updated_message = await self.message_repo.update(message_id, update_data)
        if not updated_message:
            raise NotFoundError("訊息不存在")
        logger.info(f"Message updated: {message_id} by user {user_id}")
        response = MessageResponse(**updated_message.model_dump())

        # 廣播編輯事件給房間內所有成員（編輯是業務事件，由 Service 層主動通知）
        if self._connection_manager:
            await self._connection_manager.broadcast_to_room(
                message.room_id,
                {
                    "type": "message_edited",
                    "room_id": message.room_id,
                    # 只廣播會變動的欄位，前端依 id 合併
                    "message": response.model_dump(
                        include={
                            "id",
                            "content",
                            "status",
                            "edited",
                            "edited_at",
                            "updated_at",
                            "metadata",
                        }
                    ),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

        return response

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

        # 廣播刪除事件給房間內所有成員（與歷史載入行為一致：前端直接移除該訊息）
        if self._connection_manager:
            await self._connection_manager.broadcast_to_room(
                message.room_id,
                {
                    "type": "message_deleted",
                    "room_id": message.room_id,
                    "message_id": message_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )

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
