"""房間資料存取層"""
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC
from pymongo.asynchronous.database import AsyncDatabase
from app.repositories.base import BaseRepository
from app.models.room import RoomInDB, RoomCreate, RoomUpdate, RoomResponse, RoomMember
from app.models.enums import MemberRole
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class RoomRepository(BaseRepository[RoomInDB]):
    """房間資料存取類別"""
    
    def __init__(self, database: AsyncDatabase):
        """
        初始化房間 Repository
        
        Args:
            database: MongoDB 資料庫連線
        """
        super().__init__(database, "rooms")
    
    async def get_by_id(self, room_id: str) -> Optional[RoomInDB]:
        """
        根據 ID 獲取房間
        
        Args:
            room_id: 房間 ID
            
        Returns:
            Optional[RoomInDB]: 房間物件，如果不存在則返回 None
        """
        try:
            document = await self.find_by_id(room_id)
            if document:
                # 確保 _id 正確映射到 id 字段
                if "_id" in document and "id" not in document:
                    document["id"] = document["_id"]
                return RoomInDB(**document)
            return None
        except Exception as e:
            logger.error(f"Error getting room by ID {room_id}: {e}")
            return None
    
    async def get_by_name(self, name: str) -> Optional[RoomInDB]:
        """
        根據名稱獲取房間
        
        Args:
            name: 房間名稱
            
        Returns:
            Optional[RoomInDB]: 房間物件，如果不存在則返回 None
        """
        try:
            document = await self.find_one({"name": name})
            if document:
                # 確保 _id 正確映射到 id 字段
                if "_id" in document and "id" not in document:
                    document["id"] = document["_id"]
                return RoomInDB(**document)
            return None
        except Exception as e:
            logger.error(f"Error getting room by name {name}: {e}")
            return None
    
    async def get_by_invite_code(self, invite_code: str) -> Optional[RoomInDB]:
        """
        根據邀請碼獲取房間
        
        Args:
            invite_code: 房間邀請碼
            
        Returns:
            Optional[RoomInDB]: 房間物件，如果不存在則返回 None
        """
        try:
            document = await self.find_one({"invite_code": invite_code})
            if document:
                # 確保 _id 正確映射到 id 字段
                if "_id" in document and "id" not in document:
                    document["id"] = document["_id"]
                return RoomInDB(**document)
            return None
        except Exception as e:
            logger.error(f"Error getting room by invite code {invite_code}: {e}")
            return None
    
    async def create(self, room: RoomInDB) -> Optional[RoomInDB]:
        """
        創建新房間
        
        Args:
            room: 房間物件
            
        Returns:
            Optional[RoomInDB]: 創建後的房間物件，如果失敗則返回 None
        """
        try:
            # 檢查房間名稱是否已存在
            existing_room = await self.get_by_name(room.name)
            if existing_room:
                logger.warning(f"房間名稱已存在: {room.name}")
                return None
            
            # 準備文檔
            room_dict = room.model_dump(exclude={"id"})
            room_dict["created_at"] = datetime.now(UTC)
            room_dict["updated_at"] = datetime.now(UTC)
            
            # 確保房主在成員列表中
            if room.owner_id not in room.members:
                room_dict["members"] = [room.owner_id] + room.members
            
            # 插入文檔
            room_id = await self.insert_one(room_dict)
            
            if room_id:
                created_room = await self.get_by_id(room_id)
                return created_room
            
            return None
            
        except Exception as e:
            logger.error(f"創建房間時發生錯誤: {e}")
            return None
    
    async def update(self, room_id: str, room_update: RoomUpdate) -> Optional[RoomInDB]:
        """
        更新房間
        
        Args:
            room_id: 房間 ID
            room_update: 更新資料
            
        Returns:
            Optional[RoomInDB]: 更新後的房間物件，如果失敗則返回 None
        """
        try:
            # 準備更新資料
            update_data = {}
            if room_update.name is not None:
                # 檢查新名稱是否已被其他房間使用
                existing_room = await self.get_by_name(room_update.name)
                if existing_room and str(existing_room.id) != room_id:
                    logger.warning(f"Room name {room_update.name} already exists")
                    return None
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
            
            if room_update.password is not None:
                # 如果設置了密碼，則對密碼進行哈希處理
                from app.utils.password import get_password_hash
                update_data["password_hash"] = get_password_hash(room_update.password)
            
            if not update_data:
                # 沒有需要更新的資料
                return await self.get_by_id(room_id)
            
            # 執行更新
            success = await self.update_one(
                {"_id": ObjectId(room_id)},
                {"$set": update_data}
            )
            
            if success:
                return await self.get_by_id(room_id)
            
            return None
        except Exception as e:
            logger.error(f"Error updating room {room_id}: {e}")
            return None
    
    async def delete(self, room_id: str) -> bool:
        """
        刪除房間
        
        Args:
            room_id: 房間 ID
            
        Returns:
            bool: 是否刪除成功
        """
        try:
            success = await self.delete_one({"_id": ObjectId(room_id)})
            if success:
                logger.info(f"Room {room_id} deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting room {room_id}: {e}")
            return False
    
    async def get_public_rooms(
        self, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[RoomInDB]:
        """
        獲取公開房間列表
        
        Args:
            skip: 跳過的房間數
            limit: 返回的房間數限制
            
        Returns:
            List[RoomInDB]: 公開房間列表
        """
        try:
            query = {"is_public": True}
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            rooms = []
            for doc in documents:
                # 確保 _id 正確映射到 id 字段
                if "_id" in doc and "id" not in doc:
                    doc["id"] = doc["_id"]
                rooms.append(RoomInDB(**doc))
            
            return rooms
        except Exception as e:
            logger.error(f"Error getting public rooms: {e}")
            return []
    
    async def get_user_rooms(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[RoomInDB]:
        """
        獲取使用者所屬的房間列表
        
        Args:
            user_id: 使用者 ID
            skip: 跳過的房間數
            limit: 返回的房間數限制
            
        Returns:
            List[RoomInDB]: 使用者所屬的房間列表
        """
        try:
            query = {"members": user_id}
            sort = [("updated_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            rooms = []
            for doc in documents:
                # 確保 _id 正確映射到 id 字段
                if "_id" in doc and "id" not in doc:
                    doc["id"] = doc["_id"]
                rooms.append(RoomInDB(**doc))
            
            return rooms
        except Exception as e:
            logger.error(f"Error getting user rooms: {e}")
            return []
    
    async def get_owned_rooms(
        self, 
        owner_id: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> List[RoomInDB]:
        """
        獲取使用者擁有的房間列表
        
        Args:
            owner_id: 房主 ID
            skip: 跳過的房間數
            limit: 返回的房間數限制
            
        Returns:
            List[RoomInDB]: 使用者擁有的房間列表
        """
        try:
            query = {"owner_id": owner_id}
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            rooms = []
            for doc in documents:
                # 確保 _id 正確映射到 id 字段
                if "_id" in doc and "id" not in doc:
                    doc["id"] = doc["_id"]
                rooms.append(RoomInDB(**doc))
            
            return rooms
        except Exception as e:
            logger.error(f"Error getting owned rooms: {e}")
            return []
    
    async def get_rooms_for_user(
        self, 
        user_id: str,
        skip: int = 0, 
        limit: int = 20
    ) -> List[RoomInDB]:
        """
        獲取用戶可見的房間列表（公開房間 + 用戶已加入的私人房間）
        
        Args:
            user_id: 用戶 ID
            skip: 跳過的房間數
            limit: 返回的房間數限制
            
        Returns:
            List[RoomInDB]: 房間列表
        """
        try:
            # 查詢條件：公開房間 或者 用戶是成員的房間
            query = {
                "$or": [
                    {"is_public": True},  # 公開房間
                    {"members": user_id}  # 用戶已加入的房間
                ]
            }
            
            sort = [("created_at", -1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            rooms = []
            for doc in documents:
                # 確保 _id 正確映射到 id 字段
                if "_id" in doc and "id" not in doc:
                    doc["id"] = doc["_id"]
                rooms.append(RoomInDB(**doc))
            
            return rooms
        except Exception as e:
            logger.error(f"Error getting rooms for user {user_id}: {e}")
            return []
    
    async def search_rooms(
        self, 
        keyword: str, 
        skip: int = 0, 
        limit: int = 20,
        public_only: bool = True
    ) -> List[RoomInDB]:
        """
        搜尋房間
        
        Args:
            keyword: 搜尋關鍵字
            skip: 跳過的房間數
            limit: 返回的房間數限制
            public_only: 是否只搜尋公開房間
            
        Returns:
            List[RoomInDB]: 符合搜尋條件的房間列表
        """
        try:
            query = {
                "$or": [
                    {"name": {"$regex": keyword, "$options": "i"}},
                    {"description": {"$regex": keyword, "$options": "i"}}
                ]
            }
            
            if public_only:
                query["is_public"] = True
            
            sort = [("name", 1)]
            documents = await self.find_many(query, skip=skip, limit=limit, sort=sort)
            
            rooms = []
            for doc in documents:
                # 確保 _id 正確映射到 id 字段
                if "_id" in doc and "id" not in doc:
                    doc["id"] = doc["_id"]
                rooms.append(RoomInDB(**doc))
            
            return rooms
        except Exception as e:
            logger.error(f"Error searching rooms with keyword {keyword}: {e}")
            return []
    
    async def add_member(self, room_id: str, user_id: str) -> bool:
        """
        添加成員到房間
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            bool: 是否添加成功
        """
        try:
            # 檢查房間是否存在
            room = await self.get_by_id(room_id)
            if not room:
                logger.warning(f"Room {room_id} not found")
                return False
            
            # 檢查使用者是否已經是成員
            if user_id in room.members:
                logger.info(f"User {user_id} is already a member of room {room_id}")
                return True
            
            # 檢查房間是否已滿
            if len(room.members) >= room.max_members:
                logger.warning(f"Room {room_id} is full")
                return False
            
            # 添加成員
            success = await self.update_one(
                {"_id": ObjectId(room_id)},
                {"$push": {"members": user_id}}
            )
            
            if success:
                logger.info(f"User {user_id} added to room {room_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error adding member to room: {e}")
            return False
    
    async def remove_member(self, room_id: str, user_id: str) -> bool:
        """
        從房間移除成員
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            bool: 是否移除成功
        """
        try:
            # 檢查房間是否存在
            room = await self.get_by_id(room_id)
            if not room:
                logger.warning(f"Room {room_id} not found")
                return False
            
            # 檢查使用者是否是成員
            if user_id not in room.members:
                logger.info(f"User {user_id} is not a member of room {room_id}")
                return True
            
            # 不能移除房主
            if user_id == room.owner_id:
                logger.warning(f"Cannot remove owner {user_id} from room {room_id}")
                return False
            
            # 移除成員
            success = await self.update_one(
                {"_id": ObjectId(room_id)},
                {"$pull": {"members": user_id}}
            )
            
            if success:
                logger.info(f"User {user_id} removed from room {room_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error removing member from room: {e}")
            return False
    
    async def is_member(self, room_id: str, user_id: str) -> bool:
        """
        檢查使用者是否為房間成員
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            bool: 是否為成員
        """
        try:
            room = await self.get_by_id(room_id)
            if room:
                return user_id in room.members
            return False
        except Exception as e:
            logger.error(f"Error checking membership: {e}")
            return False
    
    async def is_owner(self, room_id: str, user_id: str) -> bool:
        """
        檢查使用者是否為房間擁有者
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            bool: 是否為擁有者
        """
        try:
            room = await self.get_by_id(room_id)
            if room:
                return user_id == room.owner_id
            return False
        except Exception as e:
            logger.error(f"Error checking ownership: {e}")
            return False
    
    async def transfer_ownership(self, room_id: str, new_owner_id: str) -> bool:
        """
        轉移房間擁有權
        
        Args:
            room_id: 房間 ID
            new_owner_id: 新擁有者 ID
            
        Returns:
            bool: 是否轉移成功
        """
        try:
            # 檢查房間是否存在
            room = await self.get_by_id(room_id)
            if not room:
                logger.warning(f"Room {room_id} not found")
                return False
            
            # 檢查新擁有者是否是成員
            if new_owner_id not in room.members:
                logger.warning(f"New owner {new_owner_id} is not a member of room {room_id}")
                return False
            
            # 轉移擁有權
            success = await self.update_one(
                {"_id": ObjectId(room_id)},
                {"$set": {"owner_id": new_owner_id}}
            )
            
            if success:
                logger.info(f"Room {room_id} ownership transferred to {new_owner_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error transferring ownership: {e}")
            return False
    
    async def update_member_role(self, room_id: str, user_id: str, role: MemberRole) -> bool:
        """
        更新成員角色
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            role: 新角色
            
        Returns:
            bool: 是否更新成功
        """
        try:
            # 檢查房間是否存在
            room = await self.get_by_id(room_id)
            if not room:
                logger.warning(f"Room {room_id} not found")
                return False
            
            # 檢查使用者是否是成員
            if user_id not in room.members:
                logger.warning(f"User {user_id} is not a member of room {room_id}")
                return False
            
            # 更新成員角色
            success = await self.update_one(
                {"_id": ObjectId(room_id)},
                {"$set": {f"member_roles.{user_id}": role.value}}
            )
            
            if success:
                logger.info(f"User {user_id} role updated to {role.value} in room {room_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error updating member role: {e}")
            return False
    
    async def get_member_count(self, room_id: str) -> int:
        """
        獲取房間成員數量
        
        Args:
            room_id: 房間 ID
            
        Returns:
            int: 成員數量
        """
        try:
            room = await self.get_by_id(room_id)
            if room:
                return len(room.members)
            return 0
        except Exception as e:
            logger.error(f"Error getting member count: {e}")
            return 0
    
    async def get_room_stats(self) -> Dict[str, Any]:
        """
        獲取房間統計資料
        
        Returns:
            Dict[str, Any]: 統計資料
        """
        try:
            # 總房間數
            total_rooms = await self.count_documents({})
            
            # 公開房間數
            public_rooms = await self.count_documents({"is_public": True})
            
            # 私人房間數
            private_rooms = total_rooms - public_rooms
            
            # 今日建立房間數
            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
            today_created = await self.count_documents({
                "created_at": {"$gte": today_start}
            })
            
            # 本月建立房間數
            month_start = today_start.replace(day=1)
            month_created = await self.count_documents({
                "created_at": {"$gte": month_start}
            })
            
            # 平均成員數
            avg_members_pipeline = [
                {
                    "$project": {
                        "member_count": {"$size": "$members"}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "avg_members": {"$avg": "$member_count"}
                    }
                }
            ]
            
            avg_result = await self.aggregate(avg_members_pipeline)
            avg_members = avg_result[0]["avg_members"] if avg_result else 0
            
            return {
                "total_rooms": total_rooms,
                "public_rooms": public_rooms,
                "private_rooms": private_rooms,
                "today_created": today_created,
                "month_created": month_created,
                "avg_members": round(avg_members, 2)
            }
        except Exception as e:
            logger.error(f"Error getting room stats: {e}")
            return {
                "total_rooms": 0,
                "public_rooms": 0,
                "private_rooms": 0,
                "today_created": 0,
                "month_created": 0,
                "avg_members": 0
            }
    
    async def count_rooms(self, public_only: bool = False) -> int:
        """
        計算房間總數
        
        Args:
            public_only: 是否只計算公開房間
            
        Returns:
            int: 房間總數
        """
        try:
            query = {}
            if public_only:
                query["is_public"] = True
            
            return await self.count_documents(query)
        except Exception as e:
            logger.error(f"Error counting rooms: {e}")
            return 0
    
    async def count_user_rooms(self, user_id: str) -> int:
        """
        計算使用者參與的房間數量
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            int: 使用者參與的房間數量
        """
        try:
            query = {"members": user_id}
            return await self.count_documents(query)
        except Exception as e:
            logger.error(f"Error counting user rooms: {e}")
            return 0
    
    async def check_room_name_exists(self, name: str) -> bool:
        """
        檢查房間名稱是否存在
        
        Args:
            name: 房間名稱
            
        Returns:
            bool: 是否存在
        """
        try:
            return await self.exists({"name": name})
        except Exception as e:
            logger.error(f"Error checking room name existence: {e}")
            return False
    
    async def create_indexes(self):
        """創建必要的索引"""
        try:
            # 房間名稱唯一索引
            await self.create_index([("name", 1)], unique=True)
            
            # 房主索引
            await self.create_index([("owner_id", 1)])
            
            # 成員索引
            await self.create_index([("members", 1)])
            
            # 公開狀態和創建時間複合索引
            await self.create_index([
                ("is_public", 1),
                ("created_at", -1)
            ])
            
            # 全文搜尋索引
            await self.create_index([
                ("name", "text"),
                ("description", "text")
            ])
            
            logger.info("Room indexes created successfully")
        except Exception as e:
            logger.error(f"Error creating room indexes: {e}")
    
    async def get_popular_rooms(self, limit: int = 10) -> List[RoomInDB]:
        """
        獲取熱門房間（按成員數排序）
        
        Args:
            limit: 返回數量限制
            
        Returns:
            List[RoomInDB]: 熱門房間列表
        """
        try:
            pipeline = [
                {"$match": {"is_public": True}},
                {
                    "$addFields": {
                        "member_count": {"$size": "$members"}
                    }
                },
                {"$sort": {"member_count": -1}},
                {"$limit": limit}
            ]
            
            documents = await self.aggregate(pipeline)
            
            rooms = []
            for doc in documents:
                # 移除臨時欄位
                doc.pop("member_count", None)
                # 確保 _id 正確映射到 id 字段
                if "_id" in doc and "id" not in doc:
                    doc["id"] = doc["_id"]
                rooms.append(RoomInDB(**doc))
            
            return rooms
        except Exception as e:
            logger.error(f"Error getting popular rooms: {e}")
            return []