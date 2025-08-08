"""聊天室資料模型"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from .enums import JoinPolicy, MemberRole, RoomType


class RoomBase(BaseModel):
    """聊天室基礎模型"""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_public: bool = True  # 保留向後相容
    room_type: RoomType = Field(default=RoomType.PUBLIC)
    join_policy: JoinPolicy = Field(default=JoinPolicy.DIRECT)
    max_members: int = Field(default=100, ge=2, le=1000)

    @field_validator("room_type", "join_policy", mode="before")
    @classmethod
    def validate_enum(cls, v):
        """確保枚舉值的正確性"""
        if isinstance(v, str):
            return v
        return v.value if hasattr(v, "value") else v


class RoomCreate(RoomBase):
    """聊天室創建模型"""

    password: str | None = Field(None, min_length=6, max_length=128)
    invite_code: str | None = None


class RoomUpdate(BaseModel):
    """聊天室更新模型"""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_public: bool | None = None
    room_type: RoomType | None = None
    join_policy: JoinPolicy | None = None
    max_members: int | None = Field(None, ge=2, le=1000)
    password: str | None = Field(None, min_length=6, max_length=128)


class RoomInDB(RoomBase):
    """資料庫中的聊天室模型"""

    id: str | None = Field(default=None, alias="_id")
    owner_id: str
    members: list[str] = Field(default_factory=list)
    member_roles: dict[str, MemberRole] = Field(default_factory=dict)  # user_id -> role
    password_hash: str | None = None
    invite_code: str | None = None
    invite_code_expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class RoomResponse(RoomBase):
    """聊天室回應模型"""

    id: str
    owner_id: str
    members: list[str]
    member_roles: dict[str, MemberRole] = Field(default_factory=dict)
    member_count: int | None = None
    has_password: bool = False
    invite_code: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    @field_serializer("created_at", "updated_at")
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

    password: str | None = None
    invite_code: str | None = None
