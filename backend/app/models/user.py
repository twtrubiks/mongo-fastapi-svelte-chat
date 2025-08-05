"""使用者資料模型"""
from datetime import datetime, UTC
from typing import Optional, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from bson import ObjectId

# 移除複雜的 PyObjectId，統一使用 str 類型處理

class UserBase(BaseModel):
    """使用者基礎模型"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool = True

class UserCreate(UserBase):
    """使用者創建模型"""
    password: str = Field(..., min_length=6)

class UserUpdate(BaseModel):
    """使用者更新模型"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None
    password: Optional[str] = Field(None, min_length=6)

class UserInDB(UserBase):
    """資料庫中的使用者模型"""
    id: Optional[str] = Field(default=None, alias="_id")
    hashed_password: str
    last_login_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(
        populate_by_name=True
    )

class UserResponse(UserBase):
    """使用者回應模型"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True
    )

class Token(BaseModel):
    """Token 回應模型"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

class AuthResponse(BaseModel):
    """認證回應模型（包含用戶資料和token）"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: UserResponse

class TokenData(BaseModel):
    """Token 資料模型"""
    username: Optional[str] = None
    user_id: Optional[str] = None