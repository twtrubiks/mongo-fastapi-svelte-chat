"""使用者資料存取層"""

import logging
from datetime import UTC, datetime

from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase

from app.models.user import UserInDB, UserUpdate
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[UserInDB]):
    """使用者資料存取類別"""

    def __init__(self, database: AsyncDatabase):
        super().__init__(database, "users")

    def _to_model(self, document: dict) -> UserInDB:
        return UserInDB(**document)

    async def get_by_ids(self, user_ids: list[str]) -> list[UserInDB]:
        """
        根據多個 ID 批量獲取使用者

        Args:
            user_ids: 使用者 ID 列表

        Returns:
            list[UserInDB]: 使用者物件列表（保持輸入順序）
        """
        if not user_ids:
            return []

        object_ids = [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]
        if not object_ids:
            return []

        documents = await self.find_many(
            {"_id": {"$in": object_ids}}, limit=len(object_ids)
        )

        # 建立 map，按輸入順序返回（跳過驗證失敗的個別文件）
        user_map: dict[str, UserInDB] = {}
        for doc in documents:
            try:
                user_map[doc["_id"]] = UserInDB(**doc)
            except Exception as e:
                logger.warning(f"Skipping user {doc.get('_id')}: validation error: {e}")

        return [user_map[uid] for uid in user_ids if uid in user_map]

    async def get_by_username(self, username: str) -> UserInDB | None:
        document = await self.find_one({"username": username})
        if document:
            return self._to_model(document)
        return None

    async def get_by_email(self, email: str) -> UserInDB | None:
        document = await self.find_one({"email": email})
        if document:
            return self._to_model(document)
        return None

    async def update(self, user_id: str, user_update: UserUpdate) -> UserInDB | None:
        """
        更新使用者

        Args:
            user_id: 使用者 ID
            user_update: 更新資料

        Returns:
            Optional[UserInDB]: 更新後的使用者物件，如果失敗則返回 None
        """
        # 準備更新資料
        update_data = {}
        if user_update.full_name is not None:
            update_data["full_name"] = user_update.full_name
        if user_update.email is not None:
            # 檢查新電子郵件是否已被其他使用者使用
            existing_user = await self.get_by_email(user_update.email)
            if existing_user and str(existing_user.id) != user_id:
                logger.warning(f"Email {user_update.email} already exists")
                return None
            update_data["email"] = user_update.email
        if user_update.password is not None:
            # 這裡應該傳入已經雜湊的密碼
            update_data["hashed_password"] = user_update.password
        if user_update.avatar is not None:
            update_data["avatar"] = user_update.avatar

        if not update_data:
            # 沒有需要更新的資料
            return await self.get_by_id(user_id)

        # 執行更新
        success = await self.update_one(
            {"_id": ObjectId(user_id)}, {"$set": update_data}
        )

        if success:
            return await self.get_by_id(user_id)

        return None

    async def delete(self, user_id: str) -> bool:
        """
        刪除使用者（軟刪除）

        Args:
            user_id: 使用者 ID

        Returns:
            bool: 是否刪除成功
        """
        # 軟刪除：將 is_active 設為 False
        success = await self.update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"is_active": False}}
        )

        if success:
            logger.info(f"User {user_id} soft deleted")
            return True

        return False

    async def update_last_login(self, user_id: str) -> bool:
        """
        更新最後登入時間

        Args:
            user_id: 使用者 ID

        Returns:
            bool: 是否更新成功
        """
        return await self.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login_at": datetime.now(UTC)}},
        )
