"""使用者服務層"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from app.auth.password import get_password_hash, verify_password
from app.config import settings
from app.core.exceptions import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.models.user import UserCreate, UserInDB, UserResponse, UserUpdate
from app.repositories.user_repository import UserRepository
from app.utils.user_cache import invalidate_user_cache

logger = logging.getLogger(__name__)


class UserService:
    """使用者服務類別"""

    def __init__(
        self,
        user_repository: UserRepository,
    ):
        self.user_repo = user_repository

    @staticmethod
    def _to_user_response(user: UserInDB) -> UserResponse:
        """將 UserInDB 轉為 UserResponse（統一 _id → id 映射）"""
        user_dict = user.model_dump()
        if "_id" in user_dict:
            user_dict["id"] = str(user_dict["_id"])
            user_dict.pop("_id", None)
        return UserResponse(**user_dict)

    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        創建新使用者

        Args:
            user_data: 使用者創建資料

        Returns:
            UserResponse: 創建的使用者

        Raises:
            ConflictError: 當使用者名稱或信箱已存在時
        """
        # 唯一性檢查（先於 bcrypt，避免衝突時白費 CPU）
        existing_user, existing_email = await asyncio.gather(
            self.user_repo.get_by_username(user_data.username),
            self.user_repo.get_by_email(user_data.email),
        )
        if existing_user:
            raise ConflictError("使用者名稱已存在")
        if existing_email:
            raise ConflictError("信箱已被使用")

        # 唯一性通過後才做 bcrypt 雜湊
        hashed_password = await get_password_hash(user_data.password)
        user_doc = UserInDB(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_user = await self.user_repo.create(user_doc)
        logger.info(f"User created: {created_user.id}")
        return self._to_user_response(created_user)

    async def get_user_by_id(self, user_id: str) -> UserResponse:
        """
        根據 ID 獲取使用者

        Args:
            user_id: 使用者 ID

        Returns:
            UserResponse: 使用者資料

        Raises:
            NotFoundError: 使用者不存在時
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("使用者不存在")
        return self._to_user_response(user)

    async def get_user_by_username(self, username: str) -> UserInDB | None:
        """
        根據用戶名獲取使用者（包含密碼）

        Args:
            username: 用戶名

        Returns:
            Optional[UserInDB]: 使用者資料（包含密碼）
        """
        return await self.user_repo.get_by_username(username)

    async def update_user(
        self, user_id: str, update_data: UserUpdate, current_user_id: str
    ) -> UserResponse:
        """
        更新使用者資料

        Args:
            user_id: 使用者 ID
            update_data: 更新資料
            current_user_id: 當前使用者 ID

        Returns:
            UserResponse: 更新後的使用者

        Raises:
            NotFoundError: 使用者不存在時
            ForbiddenError: 無權限時
            ConflictError: 信箱衝突時
        """
        # 檢查權限（只能更新自己的資料）
        if user_id != current_user_id:
            raise ForbiddenError("您只能更新自己的資料")

        # 獲取使用者
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("使用者不存在")

        # 檢查新信箱是否已被使用
        if update_data.email is not None:
            existing_email = await self.user_repo.get_by_email(update_data.email)
            if existing_email and existing_email.id != user_id:
                raise ConflictError("信箱已被使用")

        # 準備更新資料，處理密碼加密
        update_dict = update_data.model_dump(exclude_unset=True)
        if "password" in update_dict:
            # 將密碼轉換為雜湊密碼
            hashed_password = await get_password_hash(update_dict.pop("password"))
            # 創建新的更新資料，將 password 替換為已雜湊的值
            update_dict["password"] = hashed_password
            # 重新創建 UserUpdate 物件
            update_data = UserUpdate(**update_dict)

        # 更新使用者
        updated_user = await self.user_repo.update(user_id, update_data)
        if not updated_user:
            raise NotFoundError("使用者不存在")
        logger.info(f"User updated: {user_id}")
        await invalidate_user_cache(user_id)
        return self._to_user_response(updated_user)

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        """
        修改使用者密碼

        Args:
            user_id: 使用者 ID
            current_password: 目前密碼
            new_password: 新密碼

        Raises:
            NotFoundError: 使用者不存在時
            AppError: 目前密碼錯誤時
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundError("使用者不存在")

        if not await verify_password(current_password, user.hashed_password):
            raise AppError("目前密碼錯誤")

        hashed_password = await get_password_hash(new_password)
        update_data = UserUpdate(password=hashed_password)
        updated_user = await self.user_repo.update(user_id, update_data)
        if not updated_user:
            raise NotFoundError("使用者不存在")
        logger.info(f"Password changed for user: {user_id}")
        await invalidate_user_cache(user_id)

    async def delete_user(self, user_id: str, current_user_id: str) -> None:
        """
        刪除使用者

        Args:
            user_id: 使用者 ID
            current_user_id: 當前使用者 ID

        Raises:
            NotFoundError: 使用者不存在時
            ForbiddenError: 無權限時
        """
        # 檢查權限（只能刪除自己的帳號）
        if user_id != current_user_id:
            raise ForbiddenError("您只能刪除自己的帳號")

        # 軟刪除（設置為不活躍）
        success = await self.user_repo.delete(user_id)
        if not success:
            raise NotFoundError("使用者不存在")
        logger.info(f"User deleted: {user_id}")
        await invalidate_user_cache(user_id)

    async def authenticate_user(self, username: str, password: str) -> dict[str, Any]:
        """
        驗證使用者登入

        Args:
            username: 用戶名
            password: 密碼

        Returns:
            Optional[Dict[str, Any]]: 驗證結果和 token
        """
        # 查找使用者
        user = await self.user_repo.get_by_username(username)
        if not user:
            raise UnauthorizedError("使用者名稱或密碼錯誤")

        # 驗證密碼
        if not await verify_password(password, user.hashed_password):
            raise UnauthorizedError("使用者名稱或密碼錯誤")

        # 檢查使用者是否活躍
        if not user.is_active:
            raise UnauthorizedError("使用者名稱或密碼錯誤")

        # 創建 token
        access_token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": str(user.id)},
            expires_delta=access_token_expires,
        )

        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": str(user.id)}
        )

        # 更新最後登入時間
        await self.user_repo.update_last_login(user.id)

        logger.info(f"User authenticated: {user.username}")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": self._to_user_response(user),
        }

    async def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """
        使用 refresh token 換發新的 access token 和 refresh token

        Args:
            refresh_token: JWT refresh token

        Returns:
            Optional[Dict[str, Any]]: 新的 token 組合，驗證失敗則返回 None
        """
        # 解碼 refresh token
        payload = decode_refresh_token(refresh_token)
        if not payload:
            raise UnauthorizedError("無效或過期的 Refresh Token")

        user_id = payload.get("user_id")
        username = payload.get("sub")
        if not user_id or not username:
            raise UnauthorizedError("無效或過期的 Refresh Token")

        # 確認使用者存在且為活躍狀態
        user = await self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("無效或過期的 Refresh Token")

        # 發行新的 token 組合（refresh token rotation）
        access_token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            data={"sub": username, "user_id": user_id},
            expires_delta=access_token_expires,
        )
        new_refresh_token = create_refresh_token(
            data={"sub": username, "user_id": user_id}
        )

        logger.info(f"Token refreshed for user: {username}")

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }
