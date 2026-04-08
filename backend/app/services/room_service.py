"""房間服務層"""

import asyncio
import logging
import secrets
from datetime import UTC, datetime

from app.auth.password import get_password_hash, verify_password
from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.models.enums import JoinPolicy, MemberRole, RoomType
from app.models.room import (
    RoomCreate,
    RoomInDB,
    RoomJoinRequest,
    RoomResponse,
    RoomSummary,
    RoomUpdate,
)
from app.models.user import UserResponse
from app.repositories.message_repository import MessageRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class RoomService:
    """房間服務類別"""

    def __init__(
        self,
        room_repository: RoomRepository,
        user_repository: UserRepository,
        message_repository: MessageRepository,
        connection_manager=None,
    ):
        self.room_repo = room_repository
        self.user_repo = user_repository
        self.message_repo = message_repository
        self._connection_manager = connection_manager

    async def _prepare_room_data(self, room: RoomInDB) -> dict:
        """提取 RoomInDB 共用欄位並補填 owner_name"""
        room_data = room.model_dump()
        room_data["id"] = room.id if room.id else room_data.get("_id", "")
        room_data.pop("_id", None)
        room_data["has_password"] = bool(room.password_hash)
        room_data["member_count"] = len(room.members)
        if not room_data.get("owner_name") and room.owner_id:
            owner = await self.user_repo.get_by_id(room.owner_id)
            if owner:
                room_data["owner_name"] = owner.username
        return room_data

    async def _convert_to_summary(
        self, room: RoomInDB, user_id: str | None = None
    ) -> RoomSummary:
        """將 RoomInDB 轉換為 RoomSummary（列表 / 非成員用）"""
        room_data = await self._prepare_room_data(room)
        room_data["is_member"] = user_id in room.members if user_id else False
        return RoomSummary(**room_data)

    async def _convert_to_response(
        self, room: RoomInDB, user_id: str | None = None
    ) -> RoomResponse:
        """將 RoomInDB 轉換為 RoomResponse（成員詳情用）"""
        room_data = await self._prepare_room_data(room)
        # RoomResponse 只對成員回傳，is_member 恆為 True
        room_data["is_member"] = True
        # invite_code 僅 owner/admin 可見
        if user_id:
            role = room.member_roles.get(user_id)
            if role not in (MemberRole.OWNER, MemberRole.ADMIN):
                room_data["invite_code"] = None
        return RoomResponse(**room_data)

    async def _convert_many_summaries(
        self, rooms: list[RoomInDB], user_id: str | None = None
    ) -> list[RoomSummary]:
        """批次轉換 RoomInDB 為 RoomSummary（並行）"""
        return list(
            await asyncio.gather(*(self._convert_to_summary(r, user_id) for r in rooms))
        )

    async def _broadcast_room_event(
        self, message: dict, exclude_user_id: str | None = None
    ):
        """廣播房間事件給所有在線使用者（並行發送）"""
        if not self._connection_manager:
            return
        try:
            tasks = [
                self._connection_manager.send_event(user_id, message)
                for user_id in list(self._connection_manager.active_connections.keys())
                if user_id != exclude_user_id
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"廣播房間事件失敗: {result}")
        except Exception as e:  # intentional fail-open: 廣播失敗不中斷主流程
            logger.error(f"廣播房間事件時發生錯誤: {e}")

    async def _notify_room_change(self, room_id: str):
        """取得最新房間資料並廣播 room_updated 事件（使用 summary 避免洩漏敏感欄位）"""
        try:
            updated_room = await self.room_repo.get_by_id(room_id)
            if updated_room:
                room_summary = await self._convert_to_summary(updated_room)
                message = {"type": "room_updated", "room": room_summary.model_dump()}
                await self._broadcast_room_event(message)
        except Exception as e:  # intentional fail-open: 廣播/通知失敗不中斷主流程
            logger.error(f"廣播房間更新事件失敗: {e}")

    async def create_room(self, owner_id: str, room_data: RoomCreate) -> RoomResponse:
        """
        創建新房間

        Args:
            owner_id: 房間擁有者 ID
            room_data: 房間資料

        Returns:
            RoomResponse: 創建的房間

        Raises:
            ValueError: 當房間名稱已存在時
            Exception: 當資料庫操作失敗時
        """
        # 驗證用戶是否存在
        user = await self.user_repo.get_by_id(owner_id)
        if not user:
            raise NotFoundError("用戶不存在")

        # 處理密碼
        password_hash = None
        if room_data.password:
            logger.info(
                f"Creating room with password, password length: {len(room_data.password)}"
            )
            password_hash = await get_password_hash(room_data.password)
            logger.debug(f"Generated password hash: {password_hash[:20]}...")

        # 生成邀請碼（私人房間自動生成，公開房間可選）
        invite_code = None
        if room_data.room_type == RoomType.PRIVATE:
            # 私人房間自動設置為邀請制並生成邀請碼
            room_data.join_policy = JoinPolicy.INVITE
            invite_code = room_data.invite_code or secrets.token_urlsafe(16)
        elif room_data.join_policy == JoinPolicy.INVITE or room_data.invite_code:
            # 公開房間但選擇邀請制
            invite_code = room_data.invite_code or secrets.token_urlsafe(16)

        # 強制 is_public 與 room_type 一致，避免 DB 出現矛盾狀態
        is_public = room_data.room_type == RoomType.PUBLIC

        # 創建房間
        room_doc = RoomInDB(
            name=room_data.name,
            description=room_data.description,
            is_public=is_public,
            room_type=room_data.room_type,
            join_policy=room_data.join_policy,
            max_members=room_data.max_members,
            owner_id=owner_id,
            owner_name=user.username,
            members=[owner_id],  # 創建者自動加入
            member_roles={owner_id: MemberRole.OWNER},  # 設置擁有者角色
            password_hash=password_hash,
            invite_code=invite_code,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 先檢查房間名稱是否已存在
        existing_room = await self.room_repo.get_by_name(room_data.name)
        if existing_room:
            raise ConflictError(f"房間名稱已存在: {room_data.name}")

        # 儲存到資料庫
        created_room = await self.room_repo.create(room_doc)
        logger.info(f"房間創建成功: {created_room.id} by user {owner_id}")

        room_response = await self._convert_to_response(created_room, owner_id)

        try:
            # 廣播給其他人用 summary 避免洩漏 invite_code
            room_summary = await self._convert_to_summary(created_room)
            message = {
                "type": "room_created",
                "room": room_summary.model_dump(),
                "creator_id": owner_id,
            }
            await self._broadcast_room_event(message, exclude_user_id=owner_id)
        except Exception as e:  # intentional fail-open: 廣播失敗不中斷主流程
            logger.error(f"廣播新房間創建事件失敗: {e}")

        return room_response

    async def get_room_by_id(
        self, room_id: str, user_id: str | None = None
    ) -> RoomResponse:
        """根據 ID 獲取房間（成員詳情）

        Raises:
            NotFoundError: 房間不存在時
        """
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("房間不存在")
        return await self._convert_to_response(room, user_id)

    async def get_room_for_user(
        self, room_id: str, user_id: str
    ) -> RoomResponse | RoomSummary:
        """根據使用者身份取得房間（成員→完整詳情，非成員 PUBLIC→摘要，PRIVATE→404）

        Raises:
            NotFoundError: 房間不存在或 PRIVATE 房間非成員不可見時
        """
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("聊天室不存在")
        if user_id in room.members:
            return await self._convert_to_response(room, user_id)
        if room.room_type == RoomType.PRIVATE:
            raise NotFoundError("聊天室不存在")
        return await self._convert_to_summary(room, user_id)

    async def get_rooms(
        self,
        skip: int = 0,
        limit: int = 20,
        search: str | None = None,
        is_public: bool = True,
        user_id: str | None = None,
        exclude_joined: bool = False,
    ) -> list[RoomSummary]:
        """獲取房間列表

        exclude_joined=True 時回傳使用者尚未加入的公開房間（探索用）
        """
        if search:
            exclude_uid = user_id if exclude_joined else None
            rooms = await self.room_repo.search_rooms(
                search, skip, limit, is_public, exclude_user_id=exclude_uid
            )
        else:
            if exclude_joined and user_id:
                rooms = await self.room_repo.get_explore_rooms(user_id, skip, limit)
            elif user_id:
                rooms = await self.room_repo.get_rooms_for_user(user_id, skip, limit)
            else:
                rooms = await self.room_repo.get_public_rooms(skip, limit)

        return await self._convert_many_summaries(rooms, user_id)

    async def get_user_rooms(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> list[RoomSummary]:
        """獲取使用者參與的房間列表"""
        rooms = await self.room_repo.get_user_rooms(user_id, skip=skip, limit=limit)
        return await self._convert_many_summaries(rooms, user_id)

    async def update_room(
        self, room_id: str, owner_id: str, update_data: RoomUpdate
    ) -> RoomResponse:
        """
        更新房間資訊

        Args:
            room_id: 房間 ID
            owner_id: 房間擁有者 ID
            update_data: 更新資料

        Returns:
            RoomResponse: 更新後的房間

        Raises:
            NotFoundError: 房間不存在時
            ForbiddenError: 無權限時
            ConflictError: 名稱衝突時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("聊天室不存在")

        # 檢查權限
        if room.owner_id != owner_id:
            raise ForbiddenError("只有房間擁有者可以修改房間資訊")

        # 檢查新的最大成員數不能小於當前成員數
        if update_data.max_members is not None:
            current_member_count = len(room.members)
            if update_data.max_members < current_member_count:
                raise AppError(f"最大成員數不能小於當前成員數 ({current_member_count})")

        # 名稱唯一性檢查（商業邏輯，由 Service 層負責）
        if update_data.name is not None:
            existing_room = await self.room_repo.get_by_name(update_data.name)
            if existing_room and str(existing_room.id) != room_id:
                raise ConflictError(f"房間名稱已存在: {update_data.name}")

        # 同步 is_public 與 room_type，避免 DB 出現矛盾狀態
        if update_data.room_type is not None:
            update_data.is_public = update_data.room_type == RoomType.PUBLIC
        elif update_data.is_public is not None:
            update_data.room_type = (
                RoomType.PUBLIC if update_data.is_public else RoomType.PRIVATE
            )

        # 密碼雜湊（加密邏輯，由 Service 層負責）
        password_hash = None
        if update_data.password is not None:
            password_hash = await get_password_hash(update_data.password)

        # 更新房間
        updated_room = await self.room_repo.update(
            room_id, update_data, password_hash=password_hash
        )
        if not updated_room:
            raise NotFoundError("聊天室不存在")
        logger.info(f"Room updated: {room_id} by user {owner_id}")
        await self._notify_room_change(room_id)
        return await self._convert_to_response(updated_room)

    async def delete_room(self, room_id: str, owner_id: str) -> None:
        """
        刪除房間

        Args:
            room_id: 房間 ID
            owner_id: 房間擁有者 ID

        Raises:
            NotFoundError: 房間不存在時
            ForbiddenError: 無權限時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("聊天室不存在")

        # 檢查權限
        logger.info(
            f"[DELETE] Room owner check: room.owner_id={room.owner_id}, requesting_user_id={owner_id}"
        )
        if room.owner_id != owner_id:
            logger.warning(
                f"[DELETE] Permission denied: user {owner_id} tried to delete room owned by {room.owner_id}"
            )
            raise ForbiddenError("只有房間擁有者可以刪除房間")

        # 刪除房間
        success = await self.room_repo.delete(room_id)
        if not success:
            raise NotFoundError("聊天室不存在")

        # 同時刪除房間的所有訊息
        await self.message_repo.delete_by_room_id(room_id)

        logger.info(f"Room deleted: {room_id} by user {owner_id}")

        try:
            delete_message = {
                "type": "room_deleted",
                "room_id": room_id,
                "deleted_by": owner_id,
            }
            await self._broadcast_room_event(delete_message)
        except Exception as e:  # intentional fail-open: 廣播失敗不中斷主流程
            logger.error(f"發送房間刪除通知時發生錯誤: {e}")

    async def join_room(
        self, room_id: str, user_id: str, join_request: RoomJoinRequest | None = None
    ) -> str:
        """
        加入房間（支援新的權限系統）

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            join_request: 加入請求（包含密碼或邀請碼）

        Returns:
            str: 操作結果訊息

        Raises:
            NotFoundError: 房間不存在時
            ConflictError: 已是成員時
            ForbiddenError: 權限不足時
            AppError: 房間已滿或密碼錯誤時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("房間不存在")

        # 檢查是否已是成員
        if user_id in room.members:
            return "您已經是該房間的成員"

        # 檢查房間是否已滿
        if len(room.members) >= room.max_members:
            raise AppError("房間已滿")

        # 根據加入策略進行驗證
        if room.join_policy == JoinPolicy.DIRECT:
            # 直接加入（僅限公開房間）
            if room.room_type != RoomType.PUBLIC:
                raise ForbiddenError("該房間不允許直接加入")

        elif room.join_policy == JoinPolicy.PASSWORD:
            # 密碼驗證
            if not join_request or not join_request.password:
                logger.info(
                    f"Password required for room {room_id}, but no password provided"
                )
                raise AppError("需要提供密碼")

            if not room.password_hash:
                logger.error(
                    f"Room {room_id} has password policy but no password hash stored"
                )
                raise AppError("房間未設置密碼")

            logger.info(
                f"Verifying password for room {room_id}, provided password length: {len(join_request.password)}"
            )
            logger.debug(f"Stored password hash: {room.password_hash[:20]}...")

            if not await verify_password(join_request.password, room.password_hash):
                logger.warning(
                    f"Password verification failed for room {room_id} by user {user_id}"
                )
                raise AppError("密碼錯誤")

        elif room.join_policy == JoinPolicy.INVITE:
            # 邀請碼驗證
            if not join_request or not join_request.invite_code:
                raise AppError("需要提供邀請碼")

            if join_request.invite_code != room.invite_code:
                raise AppError("邀請碼無效")

            # 檢查邀請碼是否過期
            if (
                room.invite_code_expires_at
                and room.invite_code_expires_at < datetime.now(UTC)
            ):
                raise AppError("邀請碼已過期")

        # 原子加入房間（含 max_members 條件檢查 + 角色設定）
        success = await self.room_repo.add_member(room_id, user_id, MemberRole.MEMBER)
        if not success:
            raise AppError("房間已滿")
        logger.info(f"User {user_id} joined room {room_id}")

        await self._notify_room_change(room_id)

        return "成功加入房間"

    async def leave_room(self, room_id: str, user_id: str) -> str:
        """
        離開房間

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID

        Returns:
            str: 操作結果訊息

        Raises:
            NotFoundError: 房間不存在時
            ForbiddenError: 房間擁有者不能離開時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("房間不存在")

        # 檢查是否是房間擁有者
        if room.owner_id == user_id:
            raise ForbiddenError("房間擁有者不能離開房間，請刪除房間或轉移擁有權")

        # 從房間中移除使用者
        success = await self.room_repo.remove_member(room_id, user_id)
        if not success:
            raise AppError("離開房間失敗")

        logger.info(f"User {user_id} left room {room_id}")

        # 廣播 user_left 給房間內其他成員（成員離開是業務事件，由 Service 層主動通知）
        if self._connection_manager:
            user_info = self._connection_manager.user_info.get(user_id, {}).copy()
            if not user_info:
                user_info = {"id": user_id}
            await self._connection_manager.broadcast_to_room(
                room_id,
                {
                    "type": "user_left",
                    "user": user_info,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "room_id": room_id,
                    "removed": True,
                },
            )

        await self._notify_room_change(room_id)

        return "成功離開房間"

    async def get_room_members(
        self, room_id: str, skip: int = 0, limit: int = 50
    ) -> list[UserResponse]:
        """
        獲取房間成員列表（分頁 + 批量查詢）

        Args:
            room_id: 房間 ID
            skip: 跳過的成員數
            limit: 返回的成員數限制

        Returns:
            list[UserResponse]: 成員列表
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            return []

        # Python 層切片分頁
        member_ids_page = room.members[skip : skip + limit]
        if not member_ids_page:
            return []

        # 批量查詢取代 N+1
        users = await self.user_repo.get_by_ids(member_ids_page)

        members = []
        for user in users:
            # 確保正確映射 _id 到 id
            user_dict = user.model_dump()
            if "_id" in user_dict:
                user_dict["id"] = user_dict.pop("_id")
            elif user.id:
                user_dict["id"] = str(user.id)
            members.append(UserResponse(**user_dict))

        return members
