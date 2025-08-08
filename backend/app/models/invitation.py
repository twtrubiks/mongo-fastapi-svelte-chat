"""邀請和加入申請資料模型"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import InvitationStatus, JoinRequestStatus


class RoomInvitation(BaseModel):
    """房間邀請模型"""

    id: str | None = Field(default=None, alias="_id")
    room_id: str
    room_name: str
    invite_code: str
    inviter_id: str
    inviter_name: str
    max_uses: int | None = Field(None, ge=1)  # 最大使用次數
    uses_count: int = 0  # 已使用次數
    expires_at: datetime
    status: InvitationStatus = InvitationStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class InvitationCreate(BaseModel):
    """創建邀請請求"""

    room_id: str
    max_uses: int | None = Field(None, ge=1)
    expires_in_hours: int = Field(default=24, ge=1, le=168)  # 1-168小時


class InvitationResponse(BaseModel):
    """邀請回應模型"""

    id: str
    room_id: str
    room_name: str
    invite_code: str
    inviter_name: str
    max_uses: int | None = None
    uses_count: int
    expires_at: datetime
    status: InvitationStatus
    created_at: datetime
    invite_link: str  # 完整的邀請鏈接

    model_config = ConfigDict(from_attributes=True)


class JoinRequest(BaseModel):
    """加入申請模型"""

    id: str | None = Field(default=None, alias="_id")
    room_id: str
    room_name: str
    requester_id: str
    requester_name: str
    message: str | None = Field(None, max_length=500)  # 申請理由
    status: JoinRequestStatus = JoinRequestStatus.PENDING
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class JoinRequestCreate(BaseModel):
    """創建加入申請"""

    room_id: str
    message: str | None = Field(None, max_length=500)


class JoinRequestResponse(BaseModel):
    """加入申請回應模型"""

    id: str
    room_id: str
    room_name: str
    requester_id: str
    requester_name: str
    message: str | None = None
    status: JoinRequestStatus
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JoinRequestReview(BaseModel):
    """審核加入申請"""

    status: JoinRequestStatus = Field(..., description="APPROVED or REJECTED")
    comment: str | None = Field(None, max_length=500)
