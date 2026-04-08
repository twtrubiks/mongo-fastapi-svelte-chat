"""通知模型"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.utils.datetime_utils import format_datetime_for_json


class NotificationType(StrEnum):
    """通知類型"""

    MESSAGE = "message"
    SYSTEM = "system"


class NotificationStatus(StrEnum):
    """通知狀態"""

    UNREAD = "unread"
    READ = "read"


class NotificationBase(BaseModel):
    """通知基礎模型"""

    user_id: str = Field(..., description="接收者 ID")
    title: str = Field(..., description="通知標題")
    content: str = Field(..., description="通知內容")
    type: NotificationType = Field(..., description="通知類型")
    status: NotificationStatus = Field(
        default=NotificationStatus.UNREAD, description="通知狀態"
    )
    metadata: dict | None = Field(default=None, description="額外元數據")
    sender_id: str | None = Field(default=None, description="發送者 ID")
    room_id: str | None = Field(default=None, description="相關房間 ID")
    read_at: datetime | None = Field(default=None, description="閱讀時間")


class NotificationCreate(NotificationBase):
    """創建通知的模型"""


class NotificationUpdate(BaseModel):
    """更新通知的模型"""

    title: str | None = None
    content: str | None = None
    status: NotificationStatus | None = None
    read_at: datetime | None = None
    metadata: dict | None = None


class NotificationInDB(NotificationBase):
    """資料庫中的通知模型"""

    id: str | None = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class NotificationResponse(BaseModel):
    """通知響應模型"""

    id: str
    user_id: str
    title: str
    content: str
    type: NotificationType
    status: NotificationStatus
    metadata: dict | None = None
    sender_id: str | None = None
    room_id: str | None = None
    read_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at", "read_at")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        """序列化日期時間"""
        if dt is None:
            return None
        return format_datetime_for_json(dt)


class NotificationListResponse(BaseModel):
    """通知列表響應模型"""

    notifications: list[NotificationResponse]
    unread_count: int


class NotificationStats(BaseModel):
    """通知統計模型"""

    total_count: int
    unread_count: int
    read_count: int
    type_counts: dict
    recent_activity: list[dict]
