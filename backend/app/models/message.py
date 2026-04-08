"""訊息資料模型"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.utils.datetime_utils import format_datetime_for_json

# 訊息內容長度上限（所有類型統一）
MAX_CONTENT_LENGTH = 2000


class MessageType(StrEnum):
    """訊息類型"""

    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    SYSTEM = "system"


class MessageStatus(StrEnum):
    """訊息狀態"""

    SENT = "sent"
    DELETED = "deleted"


class MessageBase(BaseModel):
    """訊息基礎模型"""

    content: str = Field(
        ..., min_length=1, max_length=MAX_CONTENT_LENGTH, description="訊息內容"
    )
    message_type: MessageType = Field(default=MessageType.TEXT, description="訊息類型")
    reply_to: str | None = Field(None, description="回覆的訊息 ID")
    metadata: dict[str, Any] | None = Field(None, description="訊息元數據")


class MessageCreate(MessageBase):
    """創建訊息模型"""

    room_id: str = Field(..., description="房間 ID")


class MessageUpdate(BaseModel):
    """更新訊息模型"""

    content: str | None = Field(
        None, min_length=1, max_length=MAX_CONTENT_LENGTH, description="訊息內容"
    )
    status: MessageStatus | None = Field(None, description="訊息狀態")
    metadata: dict[str, Any] | None = Field(None, description="訊息元數據")


class MessageInDB(MessageBase):
    """資料庫中的訊息模型"""

    id: str | None = Field(None, alias="_id", description="訊息 ID")
    room_id: str = Field(..., description="房間 ID")
    user_id: str = Field(..., description="發送者 ID")
    username: str = Field(..., description="發送者用戶名")
    status: MessageStatus = Field(default=MessageStatus.SENT, description="訊息狀態")
    edited: bool = Field(default=False, description="是否已編輯")
    edited_at: datetime | None = Field(None, description="編輯時間")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="創建時間"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="更新時間"
    )

    model_config = ConfigDict(populate_by_name=True)


class MessageResponse(BaseModel):
    """訊息響應模型 - 使用平面化結構以利用 MongoDB 優勢"""

    id: str = Field(..., description="訊息 ID")
    room_id: str = Field(..., description="房間 ID")
    user_id: str = Field(..., description="發送者 ID")
    username: str = Field(..., description="發送者用戶名")
    avatar: str | None = Field(None, description="發送者頭像")
    content: str = Field(..., description="訊息內容")
    message_type: MessageType = Field(..., description="訊息類型")
    reply_to: str | None = Field(None, description="回覆的訊息 ID")
    metadata: dict[str, Any] | None = Field(None, description="訊息元數據")
    status: MessageStatus = Field(..., description="訊息狀態")
    edited: bool = Field(..., description="是否已編輯")
    edited_at: datetime | None = Field(None, description="編輯時間")
    created_at: datetime = Field(..., description="創建時間")
    updated_at: datetime = Field(..., description="更新時間")

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at", "edited_at")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        """序列化日期時間"""
        if dt is None:
            return None
        return format_datetime_for_json(dt)


class MessageListResponse(BaseModel):
    """訊息列表響應模型"""

    messages: list[MessageResponse] = Field(..., description="訊息列表")
    total: int = Field(..., description="總訊息數")
    page: int = Field(..., description="目前頁數")
    page_size: int = Field(..., description="每頁大小")
    has_next: bool = Field(..., description="是否有下一頁")
    has_prev: bool = Field(..., description="是否有上一頁")


class MessageSearchQuery(BaseModel):
    """訊息搜尋查詢模型"""

    keyword: str | None = Field(
        None, min_length=1, max_length=100, description="搜尋關鍵字"
    )
    message_type: MessageType | None = Field(None, description="訊息類型")
    user_id: str | None = Field(None, description="發送者 ID")
    start_date: datetime | None = Field(None, description="開始日期")
    end_date: datetime | None = Field(None, description="結束日期")
    page: int = Field(1, ge=1, description="頁數")
    page_size: int = Field(20, ge=1, le=100, description="每頁大小")


class ReplyToMessage(BaseModel):
    """回覆訊息資訊模型"""

    id: str = Field(..., description="被回覆訊息 ID")
    content: str = Field(..., description="被回覆訊息內容")
    username: str = Field(..., description="被回覆訊息發送者")
    created_at: datetime = Field(..., description="被回覆訊息時間")

    model_config = ConfigDict(from_attributes=True)


class MessageWithReply(MessageResponse):
    """包含回覆資訊的訊息模型"""

    reply_to_message: ReplyToMessage | None = Field(
        None, description="被回覆的訊息資訊"
    )
