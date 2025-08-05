"""房間服務層"""
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC
from app.models.room import RoomCreate, RoomInDB, RoomResponse, RoomUpdate, RoomJoinRequest
from app.models.user import UserResponse
from app.models.enums import MemberRole, RoomType, JoinPolicy
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.repositories.message_repository import MessageRepository
from app.database.improved_transaction import improved_transactional as transactional
import logging
import secrets
import bcrypt

logger = logging.getLogger(__name__)


class RoomService:
    """房間服務類別"""
    
    def __init__(self, room_repository: RoomRepository, user_repository: UserRepository, message_repository: MessageRepository):
        self.room_repo = room_repository
        self.user_repo = user_repository
        self.message_repo = message_repository
    
    def _convert_to_response(self, room: RoomInDB) -> RoomResponse:
        """將 RoomInDB 轉換為 RoomResponse，確保 id 字段正確"""
        room_data = room.model_dump()
        # 確保 id 字段有值，優先使用 room.id，否則使用 _id
        room_data["id"] = room.id if room.id else room_data.get("_id", "")
        # 移除 _id 字段以避免混淆
        room_data.pop("_id", None)
        
        # 添加 has_password 標誌
        room_data["has_password"] = bool(room.password_hash)
        
        room_response = RoomResponse(**room_data)
        room_response.member_count = len(room.members)
        return room_response
    
    async def _broadcast_room_created(self, connection_manager, room_response: RoomResponse, creator_id: str):
        """
        廣播新房間創建事件給所有連接的用戶（除了創建者）
        
        Args:
            connection_manager: WebSocket 連接管理器
            room_response: 新創建的房間響應對象
            creator_id: 創建者 ID
        """
        try:
            # 獲取所有活躍連接的用戶
            all_active_users = set()
            for user_id in connection_manager.active_connections.keys():
                if user_id != creator_id:  # 排除創建者
                    all_active_users.add(user_id)
            
            logger.info(f"廣播新房間 {room_response.id} 給 {len(all_active_users)} 個用戶")
            
            # 向每個用戶發送房間創建通知
            broadcast_message = {
                "type": "room_created",
                "room": room_response.model_dump(),
                "creator_id": creator_id
            }
            
            # 向所有活躍用戶發送通知
            for user_id in all_active_users:
                try:
                    await connection_manager.send_notification(user_id, broadcast_message)
                except Exception as e:
                    logger.error(f"向用戶 {user_id} 發送房間創建通知失敗: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"廣播房間創建事件時發生錯誤: {e}")
    
    async def create_room(
        self,
        owner_id: str,
        room_data: RoomCreate
    ) -> RoomResponse:
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
        try:
            # 驗證用戶是否存在
            user = await self.user_repo.get_by_id(owner_id)
            if not user:
                raise ValueError("用戶不存在")
            
            # 處理密碼
            password_hash = None
            if room_data.password:
                logger.info(f"Creating room with password, password length: {len(room_data.password)}")
                password_hash = bcrypt.hashpw(
                    room_data.password.encode('utf-8'), 
                    bcrypt.gensalt()
                ).decode('utf-8')
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
            
            # 創建房間
            room_doc = RoomInDB(
                name=room_data.name,
                description=room_data.description,
                is_public=room_data.is_public,
                room_type=room_data.room_type,
                join_policy=room_data.join_policy,
                max_members=room_data.max_members,
                owner_id=owner_id,
                members=[owner_id],  # 創建者自動加入
                member_roles={owner_id: MemberRole.OWNER},  # 設置擁有者角色
                password_hash=password_hash,
                invite_code=invite_code,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            
            # 先檢查房間名稱是否已存在
            existing_room = await self.room_repo.get_by_name(room_data.name)
            if existing_room:
                raise ValueError(f"房間名稱已存在: {room_data.name}")
            
            # 儲存到資料庫
            created_room = await self.room_repo.create(room_doc)
            
            if created_room:
                logger.info(f"房間創建成功: {created_room.id} by user {owner_id}")
                
                # 廣播新房間創建事件給所有連接的用戶
                try:
                    from app.websocket.manager import connection_manager
                    room_response = self._convert_to_response(created_room)
                    
                    # 廣播給所有連接的用戶（除了創建者）
                    await self._broadcast_room_created(connection_manager, room_response, owner_id)
                except Exception as e:
                    logger.error(f"廣播新房間創建事件失敗: {e}")
                    # 不影響房間創建的成功，只是通知失敗
                
                return self._convert_to_response(created_room)
            else:
                raise Exception("創建房間失敗")
                
        except ValueError as e:
            logger.error(f"創建房間驗證錯誤: {e}")
            raise e
        except Exception as e:
            logger.error(f"創建房間時發生錯誤: {e}")
            raise Exception("創建房間失敗")
    
    async def get_room_by_id(self, room_id: str) -> Optional[RoomResponse]:
        """
        根據 ID 獲取房間
        
        Args:
            room_id: 房間 ID
            
        Returns:
            Optional[RoomResponse]: 房間資料
        """
        room = await self.room_repo.get_by_id(room_id)
        if room:
            # 手動映射 _id 到 id，確保從實際的 id 字段獲取值
            room_data = room.model_dump()
            room_data["id"] = room.id or str(room.model_dump().get("_id", ""))
            if "_id" in room_data:
                room_data.pop("_id")
            room_response = RoomResponse(**room_data)
            room_response.member_count = len(room.members)
            return room_response
        return None
    
    async def get_rooms(
        self,
        skip: int = 0,
        limit: int = 20,
        search: Optional[str] = None,
        is_public: bool = True,
        user_id: Optional[str] = None
    ) -> List[RoomResponse]:
        """
        獲取房間列表 - 包含公開房間和用戶已加入的私人房間
        
        Args:
            skip: 跳過的數量
            limit: 限制數量
            search: 搜尋關鍵字
            is_public: 是否只顯示公開房間
            user_id: 用戶 ID（用於獲取用戶已加入的私人房間）
            
        Returns:
            List[RoomResponse]: 房間列表
        """
        if search:
            # 搜尋房間
            rooms = await self.room_repo.search_rooms(search, skip, limit, is_public)
        else:
            if user_id:
                # 獲取公開房間和用戶已加入的私人房間
                rooms = await self.room_repo.get_rooms_for_user(user_id, skip, limit)
            else:
                # 只獲取公開房間
                rooms = await self.room_repo.get_public_rooms(skip, limit)
        
        # 格式化房間資料
        formatted_rooms = []
        for room in rooms:
            formatted_rooms.append(self._convert_to_response(room))
        
        return formatted_rooms
    
    async def get_user_rooms(self, user_id: str) -> List[RoomResponse]:
        """
        獲取使用者參與的房間列表
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            List[RoomResponse]: 使用者房間列表
        """
        rooms = await self.room_repo.get_user_rooms(user_id)
        
        # 格式化房間資料
        formatted_rooms = []
        for room in rooms:
            formatted_rooms.append(self._convert_to_response(room))
        
        return formatted_rooms
    
    async def update_room(
        self,
        room_id: str,
        owner_id: str,
        update_data: RoomUpdate
    ) -> Optional[RoomResponse]:
        """
        更新房間資訊
        
        Args:
            room_id: 房間 ID
            owner_id: 房間擁有者 ID
            update_data: 更新資料
            
        Returns:
            Optional[RoomResponse]: 更新後的房間
            
        Raises:
            ValueError: 當參數無效或無權限時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            return None
        
        # 檢查權限
        if room.owner_id != owner_id:
            raise ValueError("只有房間擁有者可以修改房間資訊")
        
        # 檢查新的最大成員數不能小於當前成員數
        if update_data.max_members is not None:
            current_member_count = len(room.members)
            if update_data.max_members < current_member_count:
                raise ValueError(f"最大成員數不能小於當前成員數 ({current_member_count})")
        
        # 更新房間
        updated_room = await self.room_repo.update(room_id, update_data)
        if updated_room:
            logger.info(f"Room updated: {room_id} by user {owner_id}")
            room_response = RoomResponse(**updated_room.model_dump())
            room_response.member_count = len(updated_room.members)
            return room_response
        
        return None
    
    async def delete_room(self, room_id: str, owner_id: str) -> bool:
        """
        刪除房間
        
        Args:
            room_id: 房間 ID
            owner_id: 房間擁有者 ID
            
        Returns:
            bool: 是否成功刪除
            
        Raises:
            ValueError: 當參數無效或無權限時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            return False
        
        # 檢查權限
        logger.info(f"[DELETE] Room owner check: room.owner_id={room.owner_id}, requesting_user_id={owner_id}")
        if room.owner_id != owner_id:
            logger.warning(f"[DELETE] Permission denied: user {owner_id} tried to delete room owned by {room.owner_id}")
            raise ValueError("只有房間擁有者可以刪除房間")
        
        # 保存房間成員列表，用於後續通知
        room_members = list(room.members)
        
        # 刪除房間
        success = await self.room_repo.delete(room_id)
        
        if success:
            # 同時刪除房間的所有訊息
            await self.message_repo.delete_by_room_id(room_id)
            
            logger.info(f"Room deleted: {room_id} by user {owner_id}")
            
            # 發送房間刪除通知給所有用戶
            try:
                from app.websocket.manager import connection_manager
                
                # 準備刪除通知消息
                delete_message = {
                    "type": "room_deleted",
                    "room_id": room_id,
                    "deleted_by": owner_id
                }
                
                # 通知所有房間成員
                for member_id in room_members:
                    try:
                        await connection_manager.send_notification(member_id, delete_message)
                    except Exception as e:
                        logger.error(f"向用戶 {member_id} 發送房間刪除通知失敗: {e}")
                
                # 通知所有其他在線用戶（他們可能在房間列表中看到這個房間）
                all_active_users = set(connection_manager.active_connections.keys())
                for user_id in all_active_users:
                    if user_id not in room_members:  # 避免重複發送
                        try:
                            await connection_manager.send_notification(user_id, delete_message)
                        except Exception as e:
                            logger.error(f"向用戶 {user_id} 發送房間刪除通知失敗: {e}")
                
                logger.info(f"已發送房間 {room_id} 刪除通知給所有用戶")
                
            except Exception as e:
                logger.error(f"發送房間刪除通知時發生錯誤: {e}")
                # 不影響刪除操作的成功
            
            return True
        
        return False
    
    async def join_room(
        self, 
        room_id: str, 
        user_id: str,
        join_request: Optional[RoomJoinRequest] = None
    ) -> Dict[str, Any]:
        """
        加入房間（支援新的權限系統）
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            join_request: 加入請求（包含密碼或邀請碼）
            
        Returns:
            Dict[str, Any]: 操作結果
            
        Raises:
            ValueError: 當參數無效或權限不足時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise ValueError("房間不存在")
        
        # 檢查是否已是成員
        if user_id in room.members:
            return {"success": True, "message": "您已經是該房間的成員"}
        
        # 檢查房間是否已滿
        if len(room.members) >= room.max_members:
            raise ValueError("房間已滿")
        
        # 根據加入策略進行驗證
        if room.join_policy == JoinPolicy.DIRECT:
            # 直接加入（僅限公開房間）
            if room.room_type != RoomType.PUBLIC:
                raise ValueError("該房間不允許直接加入")
        
        elif room.join_policy == JoinPolicy.PASSWORD:
            # 密碼驗證
            if not join_request or not join_request.password:
                logger.info(f"Password required for room {room_id}, but no password provided")
                raise ValueError("需要提供密碼")
            
            if not room.password_hash:
                logger.error(f"Room {room_id} has password policy but no password hash stored")
                raise ValueError("房間未設置密碼")
            
            logger.info(f"Verifying password for room {room_id}, provided password length: {len(join_request.password)}")
            logger.debug(f"Stored password hash: {room.password_hash[:20]}...")
            
            if not bcrypt.checkpw(
                join_request.password.encode('utf-8'),
                room.password_hash.encode('utf-8')
            ):
                logger.warning(f"Password verification failed for room {room_id} by user {user_id}")
                raise ValueError("密碼錯誤")
        
        elif room.join_policy == JoinPolicy.INVITE:
            # 邀請碼驗證
            if not join_request or not join_request.invite_code:
                raise ValueError("需要提供邀請碼")
            
            if join_request.invite_code != room.invite_code:
                raise ValueError("邀請碼無效")
            
            # 檢查邀請碼是否過期
            if room.invite_code_expires_at and room.invite_code_expires_at < datetime.now(UTC):
                raise ValueError("邀請碼已過期")
        
        elif room.join_policy == JoinPolicy.APPROVAL:
            # 需要審核（這裡應該創建加入申請而不是直接加入）
            raise ValueError("該房間需要申請審核，請提交加入申請")
        
        # 加入房間
        success = await self.room_repo.add_member(room_id, user_id)
        
        if success:
            # 設置成員角色為普通成員
            await self.room_repo.update_member_role(room_id, user_id, MemberRole.MEMBER)
            logger.info(f"User {user_id} joined room {room_id}")
            return {"success": True, "message": "成功加入房間"}
        
        return {"success": False, "message": "加入房間失敗"}
    
    async def leave_room(self, room_id: str, user_id: str) -> Dict[str, Any]:
        """
        離開房間
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            Dict[str, Any]: 操作結果
            
        Raises:
            ValueError: 當參數無效時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise ValueError("房間不存在")
        
        # 檢查是否是房間擁有者
        if room.owner_id == user_id:
            raise ValueError("房間擁有者不能離開房間，請刪除房間或轉移擁有權")
        
        # 從房間中移除使用者
        success = await self.room_repo.remove_member(room_id, user_id)
        
        if success:
            logger.info(f"User {user_id} left room {room_id}")
            return {"success": True, "message": "成功離開房間"}
        
        return {"success": False, "message": "離開房間失敗"}
    
    async def get_room_members(self, room_id: str) -> List[UserResponse]:
        """
        獲取房間成員列表
        
        Args:
            room_id: 房間 ID
            
        Returns:
            List[UserResponse]: 成員列表
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            return []
        
        # 獲取成員資訊
        members = []
        for member_id in room.members:
            user = await self.user_repo.get_by_id(member_id)
            if user:
                # 確保正確映射 _id 到 id
                user_dict = user.model_dump()
                if "_id" in user_dict:
                    user_dict["id"] = user_dict.pop("_id")
                elif user.id:
                    user_dict["id"] = str(user.id)
                members.append(UserResponse(**user_dict))
        
        return members
    
    @transactional(retry_count=3, timeout=30.0)
    async def transfer_ownership(
        self,
        room_id: str,
        current_owner_id: str,
        new_owner_id: str
    ) -> Dict[str, Any]:
        """
        轉移房間擁有權（使用事務確保資料一致性）
        
        Args:
            room_id: 房間 ID
            current_owner_id: 當前擁有者 ID
            new_owner_id: 新擁有者 ID
            
        Returns:
            Dict[str, Any]: 操作結果
            
        Raises:
            ValueError: 當參數無效或無權限時
        """
        # 獲取房間
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise ValueError("房間不存在")
        
        # 檢查當前擁有者權限
        if room.owner_id != current_owner_id:
            raise ValueError("只有房間擁有者可以轉移擁有權")
        
        # 轉移擁有權
        success = await self.room_repo.transfer_ownership(room_id, new_owner_id)
        
        if success:
            logger.info(f"Room ownership transferred: {room_id} from {current_owner_id} to {new_owner_id}")
            return {"success": True, "message": "擁有權轉移成功"}
        
        return {"success": False, "message": "擁有權轉移失敗"}
    
    async def is_user_member(self, room_id: str, user_id: str) -> bool:
        """
        檢查使用者是否為房間成員
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            bool: 是否為房間成員
        """
        return await self.room_repo.is_member(room_id, user_id)
    
    async def is_room_owner(self, room_id: str, user_id: str) -> bool:
        """
        檢查使用者是否為房間擁有者
        
        Args:
            room_id: 房間 ID
            user_id: 使用者 ID
            
        Returns:
            bool: 是否為房間擁有者
        """
        return await self.room_repo.is_owner(room_id, user_id)
    
    async def get_room_stats(self, room_id: str) -> Dict[str, Any]:
        """
        獲取房間統計資訊
        
        Args:
            room_id: 房間 ID
            
        Returns:
            Dict[str, Any]: 房間統計資訊
        """
        # 獲取房間基本資訊
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            return {}
        
        # 獲取訊息統計
        message_stats = await self.message_repo.get_message_stats(room_id)
        
        return {
            "room_id": room_id,
            "member_count": len(room.members),
            "max_members": room.max_members,
            "message_count": message_stats.total_messages,
            "today_messages": message_stats.messages_today,
            "created_at": room.created_at,
            "updated_at": room.updated_at
        }