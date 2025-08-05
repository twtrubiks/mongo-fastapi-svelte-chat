"""使用者資料存取層"""
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC
from pymongo.asynchronous.database import AsyncDatabase
from app.repositories.base import BaseRepository
from app.models.user import UserInDB, UserCreate, UserUpdate, UserResponse
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class UserAlreadyExistsError(Exception):
    """使用者已存在的異常"""
    pass


class EmailAlreadyExistsError(Exception):
    """電子郵件已存在的異常"""
    pass


class UserRepository(BaseRepository[UserInDB]):
    """使用者資料存取類別"""
    
    def __init__(self, database: AsyncDatabase):
        """
        初始化使用者 Repository
        
        Args:
            database: MongoDB 資料庫連線
        """
        super().__init__(database, "users")
    
    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        """
        根據 ID 獲取使用者
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            Optional[UserInDB]: 使用者物件，如果不存在則返回 None
        """
        try:
            document = await self.find_by_id(user_id)
            if document:
                return UserInDB(**document)
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
    
    async def get_by_username(self, username: str) -> Optional[UserInDB]:
        """
        根據使用者名稱獲取使用者
        
        Args:
            username: 使用者名稱
            
        Returns:
            Optional[UserInDB]: 使用者物件，如果不存在則返回 None
        """
        try:
            document = await self.find_one({"username": username})
            if document:
                return UserInDB(**document)
            return None
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {e}")
            return None
    
    async def get_by_email(self, email: str) -> Optional[UserInDB]:
        """
        根據電子郵件獲取使用者
        
        Args:
            email: 電子郵件
            
        Returns:
            Optional[UserInDB]: 使用者物件，如果不存在則返回 None
        """
        try:
            document = await self.find_one({"email": email})
            if document:
                return UserInDB(**document)
            return None
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {e}")
            return None
    
    async def create(self, user: UserInDB) -> Optional[UserInDB]:
        """
        創建新使用者
        
        Args:
            user: 使用者物件
            
        Returns:
            Optional[UserInDB]: 創建後的使用者物件，如果失敗則返回 None
        """
        try:
            # 檢查使用者名稱是否已存在
            existing_user = await self.get_by_username(user.username)
            if existing_user:
                logger.warning(f"Username {user.username} already exists")
                raise UserAlreadyExistsError(f"使用者名稱 '{user.username}' 已存在")
            
            # 檢查電子郵件是否已存在
            existing_email = await self.get_by_email(user.email)
            if existing_email:
                logger.warning(f"Email {user.email} already exists")
                raise EmailAlreadyExistsError(f"信箱 '{user.email}' 已被使用")
            
            # 準備文檔
            user_dict = user.model_dump(exclude={"id"})
            user_dict["created_at"] = datetime.now(UTC)
            user_dict["updated_at"] = datetime.now(UTC)
            
            # 插入文檔
            user_id = await self.insert_one(user_dict)
            if user_id:
                return await self.get_by_id(user_id)
            
            return None
        except (UserAlreadyExistsError, EmailAlreadyExistsError):
            # 重新拋出自定義異常
            raise
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None
    
    async def update(self, user_id: str, user_update: UserUpdate) -> Optional[UserInDB]:
        """
        更新使用者
        
        Args:
            user_id: 使用者 ID
            user_update: 更新資料
            
        Returns:
            Optional[UserInDB]: 更新後的使用者物件，如果失敗則返回 None
        """
        try:
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
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            
            if success:
                return await self.get_by_id(user_id)
            
            return None
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return None
    
    async def delete(self, user_id: str) -> bool:
        """
        刪除使用者（軟刪除）
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            bool: 是否刪除成功
        """
        try:
            # 軟刪除：將 is_active 設為 False
            success = await self.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": False}}
            )
            
            if success:
                logger.info(f"User {user_id} soft deleted")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return False
    
    async def hard_delete(self, user_id: str) -> bool:
        """
        硬刪除使用者
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            bool: 是否刪除成功
        """
        try:
            success = await self.delete_one({"_id": ObjectId(user_id)})
            if success:
                logger.info(f"User {user_id} hard deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Error hard deleting user {user_id}: {e}")
            return False
    
    async def get_all_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        include_inactive: bool = False
    ) -> List[UserInDB]:
        """
        獲取所有使用者
        
        Args:
            skip: 跳過的使用者數
            limit: 返回的使用者數限制
            include_inactive: 是否包含非活躍使用者
            
        Returns:
            List[UserInDB]: 使用者列表
        """
        try:
            query = {}
            if not include_inactive:
                query["is_active"] = True
            
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            users = []
            for doc in documents:
                users.append(UserInDB(**doc))
            
            return users
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    async def search_users(
        self, 
        keyword: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[UserInDB]:
        """
        搜尋使用者
        
        Args:
            keyword: 搜尋關鍵字
            skip: 跳過的使用者數
            limit: 返回的使用者數限制
            
        Returns:
            List[UserInDB]: 符合搜尋條件的使用者列表
        """
        try:
            query = {
                "$and": [
                    {"is_active": True},
                    {
                        "$or": [
                            {"username": {"$regex": keyword, "$options": "i"}},
                            {"full_name": {"$regex": keyword, "$options": "i"}},
                            {"email": {"$regex": keyword, "$options": "i"}}
                        ]
                    }
                ]
            }
            
            sort = [("username", 1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            users = []
            for doc in documents:
                users.append(UserInDB(**doc))
            
            return users
        except Exception as e:
            logger.error(f"Error searching users with keyword {keyword}: {e}")
            return []
    
    async def count_users(self, include_inactive: bool = False) -> int:
        """
        計算使用者總數
        
        Args:
            include_inactive: 是否包含非活躍使用者
            
        Returns:
            int: 使用者總數
        """
        try:
            query = {}
            if not include_inactive:
                query["is_active"] = True
            
            return await self.count_documents(query)
        except Exception as e:
            logger.error(f"Error counting users: {e}")
            return 0
    
    async def update_last_login(self, user_id: str) -> bool:
        """
        更新最後登入時間
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            bool: 是否更新成功
        """
        try:
            success = await self.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"last_login_at": datetime.now(UTC)}}
            )
            return success
        except Exception as e:
            logger.error(f"Error updating last login for user {user_id}: {e}")
            return False
    
    async def update_last_activity(self, user_id: str) -> bool:
        """
        更新使用者最後活動時間
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            bool: 是否更新成功
        """
        try:
            success = await self.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"last_activity": datetime.now(UTC)}}
            )
            return success
        except Exception as e:
            logger.error(f"Error updating last activity for user {user_id}: {e}")
            return False
    
    async def change_password(self, user_id: str, new_hashed_password: str) -> bool:
        """
        修改使用者密碼
        
        Args:
            user_id: 使用者 ID
            new_hashed_password: 新的加密密碼
            
        Returns:
            bool: 是否修改成功
        """
        try:
            success = await self.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "hashed_password": new_hashed_password,
                        "updated_at": datetime.now(UTC)
                    }
                }
            )
            return success
        except Exception as e:
            logger.error(f"Error changing password for user {user_id}: {e}")
            return False
    
    async def check_username_exists(self, username: str) -> bool:
        """
        檢查使用者名稱是否存在
        
        Args:
            username: 使用者名稱
            
        Returns:
            bool: 是否存在
        """
        try:
            return await self.exists({"username": username})
        except Exception as e:
            logger.error(f"Error checking username existence: {e}")
            return False
    
    async def check_email_exists(self, email: str) -> bool:
        """
        檢查電子郵件是否存在
        
        Args:
            email: 電子郵件
            
        Returns:
            bool: 是否存在
        """
        try:
            return await self.exists({"email": email})
        except Exception as e:
            logger.error(f"Error checking email existence: {e}")
            return False
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """
        獲取使用者統計資料
        
        Returns:
            Dict[str, Any]: 統計資料
        """
        try:
            # 總使用者數
            total_users = await self.count_documents({})
            
            # 活躍使用者數
            active_users = await self.count_documents({"is_active": True})
            
            # 今日註冊使用者數
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            today_registrations = await self.count_documents({
                "created_at": {"$gte": today_start}
            })
            
            # 本月註冊使用者數
            month_start = today_start.replace(day=1)
            month_registrations = await self.count_documents({
                "created_at": {"$gte": month_start}
            })
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "today_registrations": today_registrations,
                "month_registrations": month_registrations
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {
                "total_users": 0,
                "active_users": 0,
                "inactive_users": 0,
                "today_registrations": 0,
                "month_registrations": 0
            }
    
    async def create_indexes(self):
        """創建必要的索引"""
        try:
            # 使用者名稱唯一索引
            await self.create_index([("username", 1)], unique=True)
            
            # 電子郵件唯一索引
            await self.create_index([("email", 1)], unique=True)
            
            # 活躍狀態索引
            await self.create_index([("is_active", 1)])
            
            # 創建時間索引
            await self.create_index([("created_at", -1)])
            
            logger.info("User indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating user indexes: {e}")
    
    async def activate_user(self, user_id: str) -> bool:
        """
        啟用使用者
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            bool: 是否啟用成功
        """
        try:
            success = await self.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": True}}
            )
            
            if success:
                logger.info(f"User {user_id} activated")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error activating user {user_id}: {e}")
            return False
    
    async def deactivate_user(self, user_id: str) -> bool:
        """
        停用使用者
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            bool: 是否停用成功
        """
        try:
            success = await self.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"is_active": False}}
            )
            
            if success:
                logger.info(f"User {user_id} deactivated")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error deactivating user {user_id}: {e}")
            return False