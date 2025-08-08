"""使用者資料模型"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer

# 移除複雜的 PyObjectId，統一使用 str 類型處理


class UserBase(BaseModel):
    """使用者基礎模型"""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str | None = None
    avatar: str | None = None
    is_active: bool = True


class UserCreate(UserBase):
    """使用者創建模型"""

    password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    """使用者更新模型"""

    full_name: str | None = None
    email: EmailStr | None = None
    avatar: str | None = None
    password: str | None = Field(None, min_length=6)


class UserInDB(UserBase):
    """資料庫中的使用者模型"""

    id: str | None = Field(default=None, alias="_id")
    hashed_password: str
    last_login_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(populate_by_name=True)


class UserResponse(UserBase):
    """使用者回應模型"""

    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        """確保時間以 ISO 格式輸出，並包含時區標記"""
        if dt is None:
            return None
        if dt.tzinfo is None:
            # 如果沒有時區信息，假設為 UTC
            dt = dt.replace(tzinfo=UTC)
        # 使用 isoformat() 會自動包含時區標記
        return dt.isoformat()


class Token(BaseModel):
    """Token 回應模型"""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    """認證回應模型（包含用戶資料和token）"""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse


class TokenData(BaseModel):
    """Token 資料模型"""

    username: str | None = None
    user_id: str | None = None
