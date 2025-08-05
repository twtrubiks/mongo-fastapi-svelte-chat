"""資料驗證的測試"""
import pytest
from unittest.mock import Mock
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, UTC
import re


class TestDataValidation:
    """測試各種資料驗證功能"""
    
    def test_user_model_validation(self):
        """測試用戶模型驗證"""
        # 定義簡單的用戶模型
        class UserModel(BaseModel):
            username: str = Field(..., min_length=3, max_length=30)
            email: str
            password: str = Field(..., min_length=8)
            age: Optional[int] = Field(None, ge=13, le=150)
            
            @field_validator('username')
            @classmethod
            def username_valid(cls, v):
                if not re.match(r'^[a-zA-Z0-9_]+$', v):
                    raise ValueError('Username must contain only letters, numbers and underscore')
                return v
            
            @field_validator('email')
            @classmethod
            def email_valid(cls, v):
                if '@' not in v:
                    raise ValueError('Invalid email format')
                return v
        
        # 測試有效的用戶
        valid_user = UserModel(
            username="john_doe",
            email="john@example.com",
            password="SecurePass123",
            age=25
        )
        assert valid_user.username == "john_doe"
        assert valid_user.age == 25
        
        # 測試無效的用戶名
        with pytest.raises(ValueError) as exc_info:
            UserModel(
                username="jo",  # 太短
                email="test@example.com",
                password="password123"
            )
        assert "at least 3 characters" in str(exc_info.value)
        
        # 測試無效的密碼
        with pytest.raises(ValueError) as exc_info:
            UserModel(
                username="user123",
                email="user@example.com",
                password="pass"  # 太短
            )
        assert "at least 8 characters" in str(exc_info.value)
    
    def test_message_model_validation(self):
        """測試訊息模型驗證"""
        # 定義簡單的訊息模型
        class MessageModel(BaseModel):
            room_id: str
            sender_id: str
            content: str = Field(..., min_length=1, max_length=10000)
            message_type: str = Field(default="text")
            created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
            
            @field_validator('content')
            @classmethod
            def clean_content(cls, v):
                v = v.strip()
                if not v:
                    raise ValueError('Message content cannot be empty')
                return v
            
            @field_validator('message_type')
            @classmethod
            def validate_message_type(cls, v):
                valid_types = {'text', 'image', 'file', 'video', 'audio', 'system'}
                if v not in valid_types:
                    raise ValueError(f"Invalid message type: {v}")
                return v
        
        # 測試有效的訊息
        valid_message = MessageModel(
            room_id="room123",
            sender_id="user123",
            content="Hello, world!"
        )
        assert valid_message.content == "Hello, world!"
        assert valid_message.message_type == "text"
        
        # 測試內容清理
        message_with_spaces = MessageModel(
            room_id="room123",
            sender_id="user123",
            content="  Hello World  "
        )
        assert message_with_spaces.content == "Hello World"
        
        # 測試無效的訊息類型
        with pytest.raises(ValueError) as exc_info:
            MessageModel(
                room_id="room123",
                sender_id="user123",
                content="test",
                message_type="invalid"
            )
        assert "Invalid message type" in str(exc_info.value)
    
    def test_room_model_validation(self):
        """測試房間模型驗證"""
        # 定義簡單的房間模型
        class RoomModel(BaseModel):
            name: str = Field(..., min_length=1, max_length=100)
            description: Optional[str] = Field(None, max_length=500)
            room_type: str = Field(default="public")
            max_members: int = Field(default=100, ge=2, le=10000)
            owner_id: str
            members: List[str] = Field(default_factory=list)
            
            @field_validator('name')
            @classmethod
            def clean_room_name(cls, v):
                v = v.strip()
                if v.isdigit():
                    raise ValueError('Room name cannot be only numbers')
                return v
            
            @field_validator('room_type')
            @classmethod
            def validate_room_type(cls, v):
                valid_types = {'public', 'private', 'direct'}
                if v not in valid_types:
                    raise ValueError(f"Invalid room type: {v}")
                return v
        
        # 測試有效的房間
        valid_room = RoomModel(
            name="General Discussion",
            description="A room for general chat",
            owner_id="user123",
            members=["user123", "user456"]
        )
        assert valid_room.name == "General Discussion"
        assert len(valid_room.members) == 2
        
        # 測試無效的房間名稱
        with pytest.raises(ValueError) as exc_info:
            RoomModel(
                name="12345",
                owner_id="user123"
            )
        assert "only numbers" in str(exc_info.value)
    
    def test_file_upload_validation(self):
        """測試檔案上傳驗證"""
        # 定義簡單的檔案上傳模型
        class FileUploadModel(BaseModel):
            filename: str
            content_type: str
            size: int = Field(..., gt=0, le=104857600)  # 最大 100MB
            uploaded_by: str
            
            @field_validator('filename')
            @classmethod
            def validate_filename(cls, v):
                v = v.strip()
                if len(v) > 255:
                    raise ValueError('Filename too long')
                
                # 檢查危險字符
                if '..' in v or '/' in v or '\\' in v:
                    raise ValueError('Filename contains dangerous characters')
                
                return v
            
            @field_validator('content_type')
            @classmethod
            def validate_content_type(cls, v):
                allowed_prefixes = ['image/', 'video/', 'audio/', 'text/', 'application/pdf']
                
                if not any(v.startswith(prefix) for prefix in allowed_prefixes):
                    raise ValueError(f'Content type {v} is not allowed')
                
                return v
        
        # 測試有效的檔案上傳
        valid_file = FileUploadModel(
            filename="document.pdf",
            content_type="application/pdf",
            size=1024 * 1024,  # 1MB
            uploaded_by="user123"
        )
        assert valid_file.filename == "document.pdf"
        assert valid_file.size == 1024 * 1024
        
        # 測試危險檔名
        with pytest.raises(ValueError) as exc_info:
            FileUploadModel(
                filename="../../../etc/passwd",
                content_type="text/plain",
                size=100,
                uploaded_by="user123"
            )
        assert "dangerous characters" in str(exc_info.value)
    
    def test_api_request_validation(self):
        """測試 API 請求驗證"""
        # 定義分頁參數模型
        class PaginationParams(BaseModel):
            page: int = Field(1, ge=1, le=1000)
            page_size: int = Field(20, ge=1, le=100)
        
        # 定義搜索參數模型
        class SearchParams(BaseModel):
            query: str = Field(..., min_length=1, max_length=200)
            sort_by: Optional[str] = None
            sort_order: str = Field("desc")
            
            @field_validator('query')
            @classmethod
            def clean_search_query(cls, v):
                v = v.strip()
                # 移除危險字符
                v = re.sub(r'[<>\"\'\\]', '', v)
                return v
            
            @field_validator('sort_order')
            @classmethod
            def validate_sort_order(cls, v):
                if v not in ['asc', 'desc']:
                    raise ValueError('Sort order must be asc or desc')
                return v
        
        # 測試分頁參數
        valid_pagination = PaginationParams(page=2, page_size=50)
        assert valid_pagination.page == 2
        assert valid_pagination.page_size == 50
        
        # 測試搜索參數
        valid_search = SearchParams(
            query="python programming",
            sort_by="created_at"
        )
        assert valid_search.query == "python programming"
        assert valid_search.sort_order == "desc"
    
    def test_business_logic_validation(self):
        """測試業務邏輯驗證"""
        # Mock 業務驗證器
        class BusinessValidator:
            def __init__(self):
                self.user_service = Mock()
                self.room_service = Mock()
            
            def validate_room_creation(self, user_id: str, room_data: dict):
                """驗證房間創建"""
                errors = []
                
                # 檢查用戶是否存在
                if not self.user_service.user_exists(user_id):
                    errors.append("User does not exist")
                
                # 檢查用戶是否被封禁
                if self.user_service.is_banned(user_id):
                    errors.append("Banned users cannot create rooms")
                
                # 檢查房間名稱是否重複
                if self.room_service.room_name_exists(room_data['name']):
                    errors.append("Room name already exists")
                
                return len(errors) == 0, errors
            
            def validate_message_sending(self, user_id: str, room_id: str, message: dict):
                """驗證訊息發送"""
                errors = []
                
                # 檢查用戶是否在房間中
                if not self.room_service.is_member(room_id, user_id):
                    errors.append("User is not a member of this room")
                
                # 檢查用戶是否被禁言
                if self.room_service.is_muted(room_id, user_id):
                    errors.append("User is muted in this room")
                
                return len(errors) == 0, errors
        
        # 設置 Mock 行為
        validator = BusinessValidator()
        
        # 測試房間創建驗證
        validator.user_service.user_exists.return_value = True
        validator.user_service.is_banned.return_value = False
        validator.room_service.room_name_exists.return_value = False
        
        valid, errors = validator.validate_room_creation(
            "user123",
            {"name": "New Room", "room_type": "public"}
        )
        assert valid is True
        assert len(errors) == 0
        
        # 測試失敗的驗證
        validator.user_service.is_banned.return_value = True
        validator.room_service.room_name_exists.return_value = True
        
        valid, errors = validator.validate_room_creation(
            "user123",
            {"name": "Existing Room", "room_type": "public"}
        )
        assert valid is False
        assert "Banned users cannot create rooms" in errors
        assert "Room name already exists" in errors
    
    def test_input_normalization(self):
        """測試輸入正規化"""
        # 定義正規化器
        class InputNormalizer:
            @staticmethod
            def normalize_email(email: str) -> str:
                """正規化電子郵件地址"""
                # 轉小寫
                email = email.lower().strip()
                
                # 移除 Gmail 的點和加號別名
                if '@gmail.com' in email:
                    local, domain = email.split('@')
                    # 移除點
                    local = local.replace('.', '')
                    # 移除加號後的部分
                    if '+' in local:
                        local = local.split('+')[0]
                    email = f"{local}@{domain}"
                
                return email
            
            @staticmethod
            def normalize_phone(phone: str) -> str:
                """正規化電話號碼"""
                # 移除所有非數字字符
                phone = re.sub(r'\D', '', phone)
                
                # 處理國碼
                if phone.startswith('886'):  # 台灣
                    phone = '0' + phone[3:]
                elif len(phone) == 10 and phone[0] != '0':  # 可能缺少 0
                    phone = '0' + phone
                
                return phone
            
            @staticmethod
            def normalize_whitespace(text: str) -> str:
                """正規化空白字符"""
                # 合併連續空格
                text = re.sub(r'\s+', ' ', text)
                
                # 移除前後空白
                text = text.strip()
                
                return text
        
        # 測試電子郵件正規化
        assert InputNormalizer.normalize_email("John.Doe+test@GMAIL.com") == "johndoe@gmail.com"
        assert InputNormalizer.normalize_email("  USER@EXAMPLE.COM  ") == "user@example.com"
        
        # 測試電話正規化
        assert InputNormalizer.normalize_phone("0912-345-678") == "0912345678"
        assert InputNormalizer.normalize_phone("886912345678") == "0912345678"
        
        # 測試空白正規化
        assert InputNormalizer.normalize_whitespace("  multiple   spaces  ") == "multiple spaces"