"""房間資料存取層"""

import logging
import re

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.enums import MemberRole
from app.models.room import RoomInDB, RoomUpdate
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class RoomRepository(BaseRepository[RoomInDB]):
    """房間資料存取類別"""

    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "rooms")

    def _to_model(self, document: dict) -> RoomInDB:
        return RoomInDB(**document)

    async def get_by_name(self, name: str) -> RoomInDB | None:
        document = await self.find_one({"name": name})
        if document:
            return self._to_model(document)
        return None

    async def get_by_invite_code(self, invite_code: str) -> RoomInDB | None:
        document = await self.find_one({"invite_code": invite_code})
        if document:
            return self._to_model(document)
        return None

    async def update(
        self,
        room_id: str,
        room_update: RoomUpdate,
        password_hash: str | None = None,
    ) -> RoomInDB | None:
        """
        更新房間（純資料操作，驗證與加密由 Service 層負責）

        Args:
            room_id: 房間 ID
            room_update: 更新資料
            password_hash: 已雜湊的密碼（由 Service 層傳入）

        Returns:
            Optional[RoomInDB]: 更新後的房間物件，如果失敗則返回 None
        """
        update_data = {}
        if room_update.name is not None:
            update_data["name"] = room_update.name
        if room_update.description is not None:
            update_data["description"] = room_update.description
        if room_update.is_public is not None:
            update_data["is_public"] = room_update.is_public
        if room_update.max_members is not None:
            update_data["max_members"] = room_update.max_members
        if room_update.room_type is not None:
            update_data["room_type"] = room_update.room_type.value
        if room_update.join_policy is not None:
            update_data["join_policy"] = room_update.join_policy.value
        if password_hash is not None:
            update_data["password_hash"] = password_hash

        if not update_data:
            return await self.get_by_id(room_id)

        success = await self.update_one(
            {"_id": ObjectId(room_id)}, {"$set": update_data}
        )

        if success:
            return await self.get_by_id(room_id)

        return None

    async def delete(self, room_id: str) -> bool:
        """
        刪除房間

        Args:
            room_id: 房間 ID

        Returns:
            bool: 是否刪除成功
        """
        success = await self.delete_one({"_id": ObjectId(room_id)})
        if success:
            logger.info(f"Room {room_id} deleted")
            return True
        return False

    async def get_public_rooms(self, skip: int = 0, limit: int = 20) -> list[RoomInDB]:
        documents = await self.find_many(
            {"is_public": True}, skip=skip, limit=limit, sort=[("created_at", -1)]
        )
        return [self._to_model(doc) for doc in documents]

    async def get_user_rooms(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> list[RoomInDB]:
        documents = await self.find_many(
            {"members": user_id}, skip=skip, limit=limit, sort=[("updated_at", -1)]
        )
        return [self._to_model(doc) for doc in documents]

    async def get_rooms_for_user(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> list[RoomInDB]:
        """公開房間 + 用戶已加入的私人房間"""
        query = {
            "$or": [
                {"is_public": True},
                {"members": user_id},
            ]
        }
        documents = await self.find_many(
            query, skip=skip, limit=limit, sort=[("created_at", -1)]
        )
        return [self._to_model(doc) for doc in documents]

    async def get_explore_rooms(
        self, user_id: str, skip: int = 0, limit: int = 20
    ) -> list[RoomInDB]:
        """公開房間中排除使用者已加入的（探索用）"""
        query = {"is_public": True, "members": {"$nin": [user_id]}}
        documents = await self.find_many(
            query, skip=skip, limit=limit, sort=[("created_at", -1)]
        )
        return [self._to_model(doc) for doc in documents]

    async def search_rooms(
        self,
        keyword: str,
        skip: int = 0,
        limit: int = 20,
        public_only: bool = True,
        exclude_user_id: str | None = None,
    ) -> list[RoomInDB]:
        escaped = re.escape(keyword)
        query: dict = {
            "$or": [
                {"name": {"$regex": escaped, "$options": "i"}},
                {"description": {"$regex": escaped, "$options": "i"}},
            ]
        }

        if public_only:
            query["is_public"] = True

        if exclude_user_id:
            query["members"] = {"$nin": [exclude_user_id]}

        documents = await self.find_many(
            query, skip=skip, limit=limit, sort=[("name", 1)]
        )
        return [self._to_model(doc) for doc in documents]

    async def add_member(self, room_id: str, user_id: str, role: MemberRole) -> bool:
        """
        原子添加成員到房間（含 max_members 條件檢查 + 角色設定）

        使用 $expr 條件確保成員數不超過 max_members，並在同一次 update_one 中
        同時執行 $addToSet members 和 $set member_roles，避免非原子多步寫入。

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            role: 成員角色（由 Service 層決定）

        Returns:
            bool: 是否添加成功（False 表示房間已滿或不存在）
        """
        success = await self.update_one(
            {
                "_id": ObjectId(room_id),
                "$expr": {"$lt": [{"$size": "$members"}, "$max_members"]},
            },
            {
                "$addToSet": {"members": user_id},
                "$set": {f"member_roles.{user_id}": role.value},
            },
        )

        if success:
            logger.info(
                f"User {user_id} added to room {room_id} with role {role.value}"
            )
        return success

    async def remove_member(self, room_id: str, user_id: str) -> bool:
        """
        從房間移除成員（純資料操作，商業邏輯驗證由 Service 層負責）

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID

        Returns:
            bool: 是否移除成功
        """
        success = await self.update_one(
            {"_id": ObjectId(room_id)},
            {
                "$pull": {"members": user_id},
                "$unset": {f"member_roles.{user_id}": ""},
            },
        )

        if success:
            logger.info(f"User {user_id} removed from room {room_id}")
        return success

    async def is_member(self, room_id: str, user_id: str) -> bool:
        """
        檢查使用者是否為房間成員

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID

        Returns:
            bool: 是否為成員
        """
        room = await self.get_by_id(room_id)
        if room:
            return user_id in room.members
        return False

    async def update_member_role(
        self, room_id: str, user_id: str, role: MemberRole
    ) -> bool:
        """
        更新成員角色

        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            role: 新角色

        Returns:
            bool: 是否更新成功
        """
        # 單次原子更新：查詢條件同時確認房間存在且使用者為成員
        success = await self.update_one(
            {"_id": ObjectId(room_id), "members": user_id},
            {"$set": {f"member_roles.{user_id}": role.value}},
        )

        if success:
            logger.info(
                f"User {user_id} role updated to {role.value} in room {room_id}"
            )
        return success
