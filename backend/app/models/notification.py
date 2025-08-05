"""通知模型"""
from typing import Optional, List
from datetime import datetime, UTC
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from enum import Enum
from bson import ObjectId


def format_datetime_for_json(v: datetime) -> str:
    """統一的時間格式化函數，確保 UTC 時間以 Z 結尾"""
    if v.tzinfo is None:
        # 如果沒有時區資訊，假設為 UTC
        iso_str = v.replace(tzinfo=UTC).isoformat()
    else:
        iso_str = v.isoformat()

    # 將 +00:00 格式轉換為 Z 格式，確保前端兼容性
    if iso_str.endswith('+00:00'):
        return iso_str.replace('+00:00', 'Z')
    return iso_str


class NotificationType(str, Enum):
    """通知類型"""
    MESSAGE = "message"
    ROOM_INVITE = "room_invite"
    ROOM_JOIN = "room_join"
    ROOM_LEAVE = "room_leave"
    SYSTEM = "system"
    MENTION = "mention"


class NotificationStatus(str, Enum):
    """通知狀態"""
    UNREAD = "unread"
    READ = "read"
    DISMISSED = "dismissed"


class NotificationBase(BaseModel):
    """通知基礎模型"""
    user_id: str = Field(..., description="接收者 ID")
    title: str = Field(..., description="通知標題")
    content: str = Field(..., description="通知內容")
    type: NotificationType = Field(..., description="通知類型")
    status: NotificationStatus = Field(default=NotificationStatus.UNREAD, description="通知狀態")
    metadata: Optional[dict] = Field(default=None, description="額外元數據")
    sender_id: Optional[str] = Field(default=None, description="發送者 ID")
    room_id: Optional[str] = Field(default=None, description="相關房間 ID")
    is_read: bool = Field(default=False, description="是否已讀")
    read_at: Optional[datetime] = Field(default=None, description="閱讀時間")


class NotificationCreate(NotificationBase):
    """創建通知的模型"""
    pass


class NotificationUpdate(BaseModel):
    """更新通知的模型"""
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[NotificationStatus] = None
    is_read: Optional[bool] = None
    read_at: Optional[datetime] = None
    metadata: Optional[dict] = None


class NotificationInDB(NotificationBase):
    """資料庫中的通知模型"""
    id: Optional[str] = Field(default=None, alias="_id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


class NotificationResponse(BaseModel):
    """通知響應模型"""
    id: str
    user_id: str
    title: str
    content: str
    type: NotificationType
    status: NotificationStatus
    metadata: Optional[dict] = None
    sender_id: Optional[str] = None
    room_id: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )

    @field_serializer('created_at', 'updated_at', 'read_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """序列化日期時間"""
        if dt is None:
            return None
        return format_datetime_for_json(dt)


class NotificationBatch(BaseModel):
    """批量通知模型"""
    user_ids: List[str] = Field(..., description="接收者 ID 列表")
    title: str = Field(..., description="通知標題")
    content: str = Field(..., description="通知內容")
    type: NotificationType = Field(..., description="通知類型")
    metadata: Optional[dict] = Field(default=None, description="額外元數據")
    sender_id: Optional[str] = Field(default=None, description="發送者 ID")
    room_id: Optional[str] = Field(default=None, description="相關房間 ID")


class NotificationListResponse(BaseModel):
    """通知列表響應模型"""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    has_next: bool


class NotificationStats(BaseModel):
    """通知統計模型"""
    total_count: int
    unread_count: int
    read_count: int
    dismissed_count: int
    type_counts: dict
    recent_activity: List[dict]
