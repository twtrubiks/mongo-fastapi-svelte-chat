"""使用者服務層"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, UTC
from app.models.user import UserCreate, UserInDB, UserResponse, UserUpdate
from app.auth.password import verify_password, get_password_hash
from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_access_token
from app.repositories.user_repository import UserRepository, UserAlreadyExistsError, EmailAlreadyExistsError
from app.repositories.room_repository import RoomRepository
from app.repositories.message_repository import MessageRepository
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class UserService:
    """使用者服務類別"""
    
    def __init__(self, user_repository: UserRepository, room_repository: RoomRepository, message_repository: MessageRepository):
        self.user_repo = user_repository
        self.room_repo = room_repository
        self.message_repo = message_repository
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """
        創建新使用者
        
        Args:
            user_data: 使用者創建資料
            
        Returns:
            UserResponse: 創建的使用者
            
        Raises:
            ValueError: 當使用者名稱或信箱已存在時
            Exception: 當資料庫操作失敗時
        """
        # 創建使用者
        hashed_password = await get_password_hash(user_data.password)
        user_doc = UserInDB(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        try:
            created_user = await self.user_repo.create(user_doc)
            if created_user:
                logger.info(f"User created: {created_user.id}")
                # 正確轉換：MongoDB 的 _id 轉為 API 的 id
                user_dict = created_user.model_dump()
                if "_id" in user_dict:
                    user_dict["id"] = str(user_dict["_id"])
                    user_dict.pop("_id", None)
                return UserResponse(**user_dict)
            else:
                raise Exception("創建使用者失敗")
            
        except UserAlreadyExistsError as e:
            logger.warning(f"User already exists: {e}")
            raise ValueError("使用者名稱已存在")
        except EmailAlreadyExistsError as e:
            logger.warning(f"Email already exists: {e}")
            raise ValueError("信箱已被使用")
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise Exception("創建使用者失敗")
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """
        根據 ID 獲取使用者
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            Optional[UserResponse]: 使用者資料
        """
        user = await self.user_repo.get_by_id(user_id)
        if user:
            user_dict = user.model_dump()
            if "_id" in user_dict:
                user_dict["id"] = str(user_dict["_id"])
                user_dict.pop("_id", None)
            return UserResponse(**user_dict)
        return None
    
    async def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        """
        根據用戶名獲取使用者（包含密碼）
        
        Args:
            username: 用戶名
            
        Returns:
            Optional[UserInDB]: 使用者資料（包含密碼）
        """
        return await self.user_repo.get_by_username(username)
    
    async def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """
        根據信箱獲取使用者
        
        Args:
            email: 信箱
            
        Returns:
            Optional[UserResponse]: 使用者資料
        """
        user = await self.user_repo.get_by_email(email)
        if user:
            user_dict = user.model_dump()
            if "_id" in user_dict:
                user_dict["id"] = str(user_dict["_id"])
                user_dict.pop("_id", None)
            return UserResponse(**user_dict)
        return None
    
    async def update_user(
        self,
        user_id: str,
        update_data: UserUpdate,
        current_user_id: str
    ) -> Optional[UserResponse]:
        """
        更新使用者資料
        
        Args:
            user_id: 使用者 ID
            update_data: 更新資料
            current_user_id: 當前使用者 ID
            
        Returns:
            Optional[UserResponse]: 更新後的使用者
            
        Raises:
            ValueError: 當參數無效或無權限時
        """
        # 檢查權限（只能更新自己的資料）
        if user_id != current_user_id:
            raise ValueError("您只能更新自己的資料")
        
        # 獲取使用者
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return None
        
        # 檢查新信箱是否已被使用
        if update_data.email is not None:
            existing_email = await self.user_repo.get_by_email(update_data.email)
            if existing_email and existing_email.id != user_id:
                raise ValueError("信箱已被使用")
        
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
        if updated_user:
            logger.info(f"User updated: {user_id}")
            user_dict = updated_user.model_dump()
            if "_id" in user_dict:
                user_dict["id"] = str(user_dict["_id"])
                user_dict.pop("_id", None)
            return UserResponse(**user_dict)
        
        return None
    
    async def delete_user(self, user_id: str, current_user_id: str) -> bool:
        """
        刪除使用者
        
        Args:
            user_id: 使用者 ID
            current_user_id: 當前使用者 ID
            
        Returns:
            bool: 是否成功刪除
            
        Raises:
            ValueError: 當參數無效或無權限時
        """
        # 檢查權限（只能刪除自己的帳號）
        if user_id != current_user_id:
            raise ValueError("您只能刪除自己的帳號")
        
        # 軟刪除（設置為不活躍）
        success = await self.user_repo.delete(user_id)
        
        if success:
            logger.info(f"User deleted: {user_id}")
            return True
        
        return False
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
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
            return None
        
        # 驗證密碼
        if not await verify_password(password, user.hashed_password):
            return None
        
        # 檢查使用者是否活躍
        if not user.is_active:
            return None
        
        # 創建 token
        access_token_expires = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "user_id": str(user.id)},
            expires_delta=access_token_expires
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
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name or "",
                "is_active": user.is_active
            }
        }
    
    async def get_current_user_from_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        從 token 獲取當前使用者
        
        Args:
            token: JWT token
            
        Returns:
            Optional[Dict[str, Any]]: 使用者資料
        """
        # 解碼 token
        payload = decode_access_token(token)
        if not payload:
            return None
        
        # 獲取使用者資訊
        user_id = payload.get("user_id")
        username = payload.get("sub")
        
        if not user_id or not username:
            return None
        
        user = await self.user_repo.get_by_id(user_id)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        return {
            "_id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name or "",
            "is_active": user.is_active
        }
    
    async def search_users(
        self,
        query: str,
        limit: int = 10,
        exclude_user_id: Optional[str] = None
    ) -> List[UserResponse]:
        """
        搜尋使用者
        
        Args:
            query: 搜尋關鍵字
            limit: 限制數量
            exclude_user_id: 排除的使用者 ID
            
        Returns:
            List[UserResponse]: 搜尋結果
        """
        # 使用 Repository 搜尋使用者
        users = await self.user_repo.search_users(query, limit, exclude_user_id)
        
        # 格式化結果
        formatted_users = []
        for user in users:
            user_dict = user.model_dump()
            if "_id" in user_dict:
                user_dict["id"] = str(user_dict["_id"])
                user_dict.pop("_id", None)
            formatted_users.append(UserResponse(**user_dict))
        
        return formatted_users
    
    async def get_user_activity_stats(self, user_id: str) -> Dict[str, Any]:
        """
        獲取使用者活動統計
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            Dict[str, Any]: 活動統計資料
        """
        # 獲取使用者基本資訊
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {}
        
        # 獲取使用者參與的房間數
        room_count = await self.room_repo.count_user_rooms(user_id)
        
        # 獲取使用者發送的訊息數
        message_stats = await self.message_repo.get_user_message_stats(user_id)
        
        return {
            "user_id": user_id,
            "username": user.username,
            "joined_rooms": room_count,
            "total_messages": message_stats.get("total_messages", 0),
            "today_messages": message_stats.get("today_messages", 0),
            "week_messages": message_stats.get("week_messages", 0),
            "created_at": user.created_at,
            "last_login": getattr(user, 'last_login', None)
        }
    
    async def update_last_activity(self, user_id: str):
        """
        更新使用者最後活動時間
        
        Args:
            user_id: 使用者 ID
        """
        await self.user_repo.update_last_activity(user_id)
    
    async def get_online_users(self, room_id: Optional[str] = None) -> List[UserResponse]:
        """
        獲取在線使用者列表
        
        Args:
            room_id: 房間 ID（可選）
            
        Returns:
            List[UserResponse]: 在線使用者列表
        """
        # 從連線管理器獲取在線使用者
        from app.websocket.manager import connection_manager
        
        if room_id:
            # 獲取特定房間的在線使用者
            room_users = connection_manager.get_room_users(room_id)
            return [UserResponse(**user) for user in room_users]
        else:
            # 獲取所有在線使用者
            online_users = []
            # 創建副本以避免迭代時字典大小變化的錯誤
            user_info_copy = dict(connection_manager.user_info)
            for user_id, user_info in user_info_copy.items():
                try:
                    online_users.append(UserResponse(**user_info))
                except Exception as e:
                    logger.warning(f"Failed to process user {user_id}: {e}")
                    continue
            return online_users
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        修改密碼
        
        Args:
            user_id: 使用者 ID
            current_password: 當前密碼
            new_password: 新密碼
            
        Returns:
            bool: 是否成功修改
            
        Raises:
            ValueError: 當參數無效時
        """
        # 獲取使用者
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False
        
        # 驗證當前密碼
        if not await verify_password(current_password, user.hashed_password):
            raise ValueError("當前密碼不正確")
        
        # 更新密碼
        new_hashed_password = await get_password_hash(new_password)
        success = await self.user_repo.change_password(user_id, new_hashed_password)
        
        if success:
            logger.info(f"Password changed for user: {user_id}")
            return True
        
        return False


# 注意：全域實例已移除，應使用依賴注入
# user_service = UserService()