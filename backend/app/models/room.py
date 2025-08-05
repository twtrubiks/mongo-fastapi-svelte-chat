"""聊天室資料模型"""
from datetime import datetime, UTC
from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict, field_validator, field_serializer
from bson import ObjectId
from .enums import RoomType, JoinPolicy, MemberRole
import secrets
import bcrypt

class RoomBase(BaseModel):
    """聊天室基礎模型"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: bool = True  # 保留向後相容
    room_type: RoomType = Field(default=RoomType.PUBLIC)
    join_policy: JoinPolicy = Field(default=JoinPolicy.DIRECT)
    max_members: int = Field(default=100, ge=2, le=1000)
    
    @field_validator('room_type', 'join_policy', mode='before')
    @classmethod
    def validate_enum(cls, v):
        """確保枚舉值的正確性"""
        if isinstance(v, str):
            return v
        return v.value if hasattr(v, 'value') else v

class RoomCreate(RoomBase):
    """聊天室創建模型"""
    password: Optional[str] = Field(None, min_length=6, max_length=128)
    invite_code: Optional[str] = None

class RoomUpdate(BaseModel):
    """聊天室更新模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None
    room_type: Optional[RoomType] = None
    join_policy: Optional[JoinPolicy] = None
    max_members: Optional[int] = Field(None, ge=2, le=1000)
    password: Optional[str] = Field(None, min_length=6, max_length=128)

class RoomInDB(RoomBase):
    """資料庫中的聊天室模型"""
    id: Optional[str] = Field(default=None, alias="_id")
    owner_id: str
    members: List[str] = Field(default_factory=list)
    member_roles: Dict[str, MemberRole] = Field(default_factory=dict)  # user_id -> role
    password_hash: Optional[str] = None
    invite_code: Optional[str] = None
    invite_code_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

class RoomResponse(RoomBase):
    """聊天室回應模型"""
    id: str
    owner_id: str
    members: List[str]
    member_roles: Dict[str, MemberRole] = Field(default_factory=dict)
    member_count: Optional[int] = None
    has_password: bool = False
    invite_code: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )
    
    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime) -> str:
        """確保時間序列化時包含時區信息"""
        if dt.tzinfo is None:
            # 如果沒有時區信息，假設為 UTC
            dt = dt.replace(tzinfo=UTC)
        return dt.isoformat()

class RoomMember(BaseModel):
    """聊天室成員模型"""
    user_id: str
    username: str
    role: MemberRole = MemberRole.MEMBER
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class RoomJoinRequest(BaseModel):
    """加入房間的請求模型"""
    password: Optional[str] = None
    invite_code: Optional[str] = None