"""邀請和加入申請服務層"""
from typing import List, Optional, Dict, Any
from datetime import datetime, UTC, timedelta
from app.models.invitation import (
    RoomInvitation, InvitationCreate, InvitationResponse,
    JoinRequest, JoinRequestCreate, JoinRequestResponse, JoinRequestReview
)
from app.models.enums import InvitationStatus, JoinRequestStatus
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.database.improved_transaction import improved_transactional as transactional
from pymongo.asynchronous.database import AsyncDatabase
import secrets
import logging

logger = logging.getLogger(__name__)


class InvitationService:
    """邀請和加入申請服務類別"""
    
    def __init__(self, db: AsyncDatabase, room_repository: RoomRepository, user_repository: UserRepository):
        self.db = db
        self.room_repo = room_repository
        self.user_repo = user_repository
        self.invitations_collection = db["room_invitations"]
        self.join_requests_collection = db["join_requests"]
    
    async def create_invitation(
        self,
        user_id: str,
        invitation_data: InvitationCreate,
        base_url: str = "http://localhost:5173"
    ) -> InvitationResponse:
        """
        創建房間邀請
        
        Args:
            user_id: 創建者 ID
            invitation_data: 邀請資料
            base_url: 基礎 URL 用於生成邀請鏈接
            
        Returns:
            InvitationResponse: 創建的邀請
            
        Raises:
            ValueError: 當參數無效時
        """
        # 檢查房間是否存在
        room = await self.room_repo.get_by_id(invitation_data.room_id)
        if not room:
            raise ValueError("房間不存在")
        
        # 檢查權限（只有房主和管理員可以創建邀請）
        if user_id != room.owner_id:
            # 檢查是否為管理員
            user_role = room.member_roles.get(user_id)
            if user_role not in ["owner", "admin"]:
                raise ValueError("只有房主和管理員可以創建邀請")
        
        # 獲取創建者資訊
        inviter = await self.user_repo.get_by_id(user_id)
        if not inviter:
            raise ValueError("使用者不存在")
        
        # 生成邀請碼
        import secrets
        import string
        # 生成8位隨機字母數字組合
        characters = string.ascii_letters + string.digits
        invite_code = ''.join(secrets.choice(characters) for _ in range(8))
        
        # 計算過期時間
        expires_at = datetime.now(UTC) + timedelta(hours=invitation_data.expires_in_hours)
        
        # 創建邀請
        invitation = RoomInvitation(
            room_id=invitation_data.room_id,
            room_name=room.name,
            invite_code=invite_code,
            inviter_id=user_id,
            inviter_name=inviter.username,
            max_uses=invitation_data.max_uses,
            expires_at=expires_at
        )
        
        # 儲存到資料庫
        result = await self.invitations_collection.insert_one(invitation.model_dump(exclude={"id"}))
        invitation.id = str(result.inserted_id)
        
        # 生成邀請鏈接
        invite_link = f"{base_url}/app/rooms/join?code={invite_code}"
        
        logger.info(f"Created invitation for room {invitation_data.room_id} by user {user_id}")
        
        return InvitationResponse(
            **invitation.model_dump(),
            invite_link=invite_link
        )
    
    async def validate_invitation(self, invite_code: str) -> Optional[RoomInvitation]:
        """
        驗證邀請碼
        
        Args:
            invite_code: 邀請碼
            
        Returns:
            Optional[RoomInvitation]: 有效的邀請，如果無效則返回 None
        """
        # 首先查找手動創建的邀請 (room_invitations 集合)
        invitation_doc = await self.invitations_collection.find_one({
            "invite_code": invite_code,
            "status": InvitationStatus.PENDING.value
        })
        
        if invitation_doc:
            invitation = RoomInvitation(**invitation_doc)
            
            # 檢查是否過期
            if invitation.expires_at < datetime.now(UTC):
                # 更新狀態為過期
                await self.invitations_collection.update_one(
                    {"_id": invitation_doc["_id"]},
                    {"$set": {"status": InvitationStatus.EXPIRED.value}}
                )
                return None
            
            # 檢查使用次數
            if invitation.max_uses and invitation.uses_count >= invitation.max_uses:
                # 更新狀態為已接受（已用完）
                await self.invitations_collection.update_one(
                    {"_id": invitation_doc["_id"]},
                    {"$set": {"status": InvitationStatus.ACCEPTED.value}}
                )
                return None
            
            return invitation
        
        # 如果沒找到手動邀請，查找房間自帶的邀請碼
        room = await self.room_repo.get_by_invite_code(invite_code)
        if room:
            # 獲取房主資訊
            owner = await self.user_repo.get_by_id(room.owner_id)
            if owner:
                # 為房間邀請碼創建臨時的 RoomInvitation 對象
                return RoomInvitation(
                    id=None,  # 房間邀請碼沒有單獨的 ID
                    room_id=room.id,
                    room_name=room.name,
                    invite_code=invite_code,
                    inviter_id=room.owner_id,
                    inviter_name=owner.username,
                    max_uses=None,  # 房間邀請碼沒有使用次數限制
                    uses_count=0,
                    expires_at=datetime.now(UTC) + timedelta(days=365),  # 房間邀請碼永不過期
                    status=InvitationStatus.PENDING,
                    created_at=room.created_at
                )
        
        return None
    
    async def use_invitation(self, invite_code: str) -> bool:
        """
        使用邀請（增加使用次數）
        
        Args:
            invite_code: 邀請碼
            
        Returns:
            bool: 是否成功使用
        """
        # 嘗試更新手動創建的邀請
        result = await self.invitations_collection.update_one(
            {"invite_code": invite_code},
            {"$inc": {"uses_count": 1}}
        )
        
        if result.modified_count > 0:
            return True
            
        # 如果是房間邀請碼，直接返回成功（房間邀請碼沒有使用次數限制）
        room = await self.room_repo.get_by_invite_code(invite_code)
        if room:
            return True
            
        return False
    
    async def get_room_invitations(
        self,
        room_id: str,
        user_id: str,
        active_only: bool = True
    ) -> List[InvitationResponse]:
        """
        獲取房間的邀請列表
        
        Args:
            room_id: 房間 ID
            user_id: 請求者 ID
            active_only: 是否只返回有效的邀請
            
        Returns:
            List[InvitationResponse]: 邀請列表
        """
        # 檢查權限
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise ValueError("房間不存在")
        
        if user_id != room.owner_id:
            user_role = room.member_roles.get(user_id)
            if user_role not in ["owner", "admin"]:
                raise ValueError("無權查看邀請列表")
        
        # 構建查詢
        query = {"room_id": room_id}
        if active_only:
            query["status"] = InvitationStatus.PENDING.value
            query["expires_at"] = {"$gt": datetime.now(UTC)}
        
        # 查詢邀請
        cursor = self.invitations_collection.find(query).sort("created_at", -1)
        invitations = []
        
        async for doc in cursor:
            invitation = RoomInvitation(**doc)
            invite_link = f"http://localhost:5173/app/rooms/join?code={invitation.invite_code}"
            invitations.append(InvitationResponse(
                **invitation.model_dump(),
                invite_link=invite_link
            ))
        
        return invitations
    
    async def revoke_invitation(self, invite_code: str, user_id: str) -> bool:
        """
        撤銷邀請
        
        Args:
            invite_code: 邀請碼
            user_id: 操作者 ID
            
        Returns:
            bool: 是否成功撤銷
        """
        # 查找邀請
        invitation_doc = await self.invitations_collection.find_one({
            "invite_code": invite_code
        })
        
        if not invitation_doc:
            raise ValueError("邀請不存在")
        
        invitation = RoomInvitation(**invitation_doc)
        
        # 檢查權限
        room = await self.room_repo.get_by_id(invitation.room_id)
        if not room:
            raise ValueError("房間不存在")
        
        if user_id != room.owner_id and user_id != invitation.inviter_id:
            user_role = room.member_roles.get(user_id)
            if user_role not in ["owner", "admin"]:
                raise ValueError("無權撤銷此邀請")
        
        # 更新狀態
        result = await self.invitations_collection.update_one(
            {"_id": invitation_doc["_id"]},
            {"$set": {"status": InvitationStatus.REJECTED.value}}
        )
        
        return result.modified_count > 0
    
    async def create_join_request(
        self,
        user_id: str,
        request_data: JoinRequestCreate
    ) -> JoinRequestResponse:
        """
        創建加入申請
        
        Args:
            user_id: 申請者 ID
            request_data: 申請資料
            
        Returns:
            JoinRequestResponse: 創建的申請
        """
        # 檢查房間是否存在
        room = await self.room_repo.get_by_id(request_data.room_id)
        if not room:
            raise ValueError("房間不存在")
        
        # 檢查是否已是成員
        if user_id in room.members:
            raise ValueError("您已經是該房間的成員")
        
        # 檢查是否已有待處理的申請
        existing_request = await self.join_requests_collection.find_one({
            "room_id": request_data.room_id,
            "requester_id": user_id,
            "status": JoinRequestStatus.PENDING.value
        })
        
        if existing_request:
            raise ValueError("您已經提交過加入申請，請等待審核")
        
        # 獲取申請者資訊
        requester = await self.user_repo.get_by_id(user_id)
        if not requester:
            raise ValueError("使用者不存在")
        
        # 創建申請
        join_request = JoinRequest(
            room_id=request_data.room_id,
            room_name=room.name,
            requester_id=user_id,
            requester_name=requester.username,
            message=request_data.message
        )
        
        # 儲存到資料庫
        result = await self.join_requests_collection.insert_one(join_request.model_dump(exclude={"id"}))
        join_request.id = str(result.inserted_id)
        
        logger.info(f"Created join request for room {request_data.room_id} by user {user_id}")
        
        return JoinRequestResponse(**join_request.model_dump())
    
    async def get_room_join_requests(
        self,
        room_id: str,
        user_id: str,
        status: Optional[JoinRequestStatus] = None
    ) -> List[JoinRequestResponse]:
        """
        獲取房間的加入申請列表
        
        Args:
            room_id: 房間 ID
            user_id: 請求者 ID
            status: 篩選狀態
            
        Returns:
            List[JoinRequestResponse]: 申請列表
        """
        # 檢查權限
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise ValueError("房間不存在")
        
        if user_id != room.owner_id:
            user_role = room.member_roles.get(user_id)
            if user_role not in ["owner", "admin"]:
                raise ValueError("無權查看加入申請")
        
        # 構建查詢
        query = {"room_id": room_id}
        if status:
            query["status"] = status.value
        
        # 查詢申請
        cursor = self.join_requests_collection.find(query).sort("created_at", -1)
        requests = []
        
        async for doc in cursor:
            join_request = JoinRequest(**doc)
            requests.append(JoinRequestResponse(**join_request.model_dump()))
        
        return requests
    
    async def review_join_request(
        self,
        request_id: str,
        user_id: str,
        review: JoinRequestReview
    ) -> bool:
        """
        審核加入申請
        
        Args:
            request_id: 申請 ID
            user_id: 審核者 ID
            review: 審核結果
            
        Returns:
            bool: 是否成功審核
        """
        # 查找申請
        request_doc = await self.join_requests_collection.find_one({
            "_id": request_id,
            "status": JoinRequestStatus.PENDING.value
        })
        
        if not request_doc:
            raise ValueError("申請不存在或已處理")
        
        join_request = JoinRequest(**request_doc)
        
        # 檢查權限
        room = await self.room_repo.get_by_id(join_request.room_id)
        if not room:
            raise ValueError("房間不存在")
        
        if user_id != room.owner_id:
            user_role = room.member_roles.get(user_id)
            if user_role not in ["owner", "admin"]:
                raise ValueError("無權審核加入申請")
        
        # 如果批准，將使用者加入房間
        if review.status == JoinRequestStatus.APPROVED:
            # 檢查房間是否已滿
            if len(room.members) >= room.max_members:
                raise ValueError("房間已滿，無法批准申請")
            
            # 加入房間
            success = await self.room_repo.add_member(join_request.room_id, join_request.requester_id)
            if not success:
                raise ValueError("加入房間失敗")
            
            # 設置成員角色
            await self.room_repo.update_member_role(
                join_request.room_id,
                join_request.requester_id,
                "member"
            )
        
        # 更新申請狀態
        result = await self.join_requests_collection.update_one(
            {"_id": request_doc["_id"]},
            {
                "$set": {
                    "status": review.status.value,
                    "reviewed_by": user_id,
                    "reviewed_at": datetime.now(UTC),
                    "review_comment": review.comment
                }
            }
        )
        
        logger.info(f"Join request {request_id} reviewed by {user_id}: {review.status.value}")
        
        return result.modified_count > 0
    
    async def get_user_join_requests(
        self,
        user_id: str,
        status: Optional[JoinRequestStatus] = None
    ) -> List[JoinRequestResponse]:
        """
        獲取使用者的加入申請列表
        
        Args:
            user_id: 使用者 ID
            status: 篩選狀態
            
        Returns:
            List[JoinRequestResponse]: 申請列表
        """
        # 構建查詢
        query = {"requester_id": user_id}
        if status:
            query["status"] = status.value
        
        # 查詢申請
        cursor = self.join_requests_collection.find(query).sort("created_at", -1)
        requests = []
        
        async for doc in cursor:
            join_request = JoinRequest(**doc)
            requests.append(JoinRequestResponse(**join_request.model_dump()))
        
        return requests