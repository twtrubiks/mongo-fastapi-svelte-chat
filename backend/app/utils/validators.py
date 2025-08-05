"""驗證工具"""
import re
import os
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pathlib import Path
from email_validator import validate_email, EmailNotValidError
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """驗證錯誤"""
    pass


class Validators:
    """驗證器類別"""
    
    # 正則表達式模式
    PATTERNS = {
        'username': r'^[a-zA-Z0-9_]{3,20}$',
        'password': r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,50}$',
        'phone': r'^\+?1?\d{9,15}$',
        'url': r'^https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?$',
        'hex_color': r'^#(?:[0-9a-fA-F]{3}){1,2}$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        'ip_address': r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$',
        'slug': r'^[a-z0-9]+(?:-[a-z0-9]+)*$',
        'chinese_name': r'^[\u4e00-\u9fa5]{2,8}$',
        'english_name': r'^[a-zA-Z\s]{2,50}$'
    }
    
    @staticmethod
    def validate_string(
        value: str,
        min_length: int = 1,
        max_length: int = 255,
        pattern: Optional[str] = None,
        allow_empty: bool = False
    ) -> bool:
        """
        驗證字符串
        
        Args:
            value: 要驗證的字符串
            min_length: 最小長度
            max_length: 最大長度
            pattern: 正則表達式模式
            allow_empty: 是否允許空字符串
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if not isinstance(value, str):
            raise ValidationError("值必須是字符串")
        
        if not allow_empty and not value.strip():
            raise ValidationError("字符串不能為空")
        
        # 如果允許空字符串且值為空，則跳過長度檢查
        if allow_empty and not value:
            return True
        
        if len(value) < min_length:
            raise ValidationError(f"字符串長度不能少於 {min_length} 個字符")
        
        if len(value) > max_length:
            raise ValidationError(f"字符串長度不能超過 {max_length} 個字符")
        
        if pattern and not re.match(pattern, value):
            raise ValidationError("字符串格式不正確")
        
        return True
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        驗證電子郵件地址
        
        Args:
            email: 電子郵件地址
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        try:
            # 在測試環境中跳過 DNS 查詢
            validated_email = validate_email(email, check_deliverability=False)
            return True
        except EmailNotValidError as e:
            raise ValidationError(f"無效的電子郵件地址: {str(e)}")
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """
        驗證用戶名
        
        Args:
            username: 用戶名
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            username,
            min_length=3,
            max_length=20,
            pattern=Validators.PATTERNS['username']
        )
    
    @staticmethod
    def validate_password(password: str) -> bool:
        """
        驗證密碼強度
        
        Args:
            password: 密碼
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if len(password) < 8:
            raise ValidationError("密碼長度不能少於 8 個字符")
        
        if len(password) > 50:
            raise ValidationError("密碼長度不能超過 50 個字符")
        
        if not re.search(r'[a-z]', password):
            raise ValidationError("密碼必須包含至少一個小寫字母")
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError("密碼必須包含至少一個大寫字母")
        
        if not re.search(r'\d', password):
            raise ValidationError("密碼必須包含至少一個數字")
        
        # 檢查常見弱密碼
        weak_passwords = ['12345678', 'password', 'qwerty123', 'abc123456']
        if password.lower() in weak_passwords:
            raise ValidationError("密碼過於簡單，請使用更複雜的密碼")
        
        return True
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """
        驗證電話號碼
        
        Args:
            phone: 電話號碼
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            phone,
            min_length=9,
            max_length=15,
            pattern=Validators.PATTERNS['phone']
        )
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        驗證 URL
        
        Args:
            url: URL 地址
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            url,
            pattern=Validators.PATTERNS['url']
        )
    
    @staticmethod
    def validate_number(
        value: Union[int, float],
        min_value: Optional[Union[int, float]] = None,
        max_value: Optional[Union[int, float]] = None
    ) -> bool:
        """
        驗證數字
        
        Args:
            value: 要驗證的數字
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if not isinstance(value, (int, float)):
            raise ValidationError("值必須是數字")
        
        if min_value is not None and value < min_value:
            raise ValidationError(f"數字不能小於 {min_value}")
        
        if max_value is not None and value > max_value:
            raise ValidationError(f"數字不能大於 {max_value}")
        
        return True
    
    @staticmethod
    def validate_integer(
        value: int,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ) -> bool:
        """
        驗證整數
        
        Args:
            value: 要驗證的整數
            min_value: 最小值
            max_value: 最大值
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if not isinstance(value, int):
            raise ValidationError("值必須是整數")
        
        return Validators.validate_number(value, min_value, max_value)
    
    @staticmethod
    def validate_list(
        value: List[Any],
        min_length: int = 0,
        max_length: Optional[int] = None,
        item_validator: Optional[callable] = None
    ) -> bool:
        """
        驗證列表
        
        Args:
            value: 要驗證的列表
            min_length: 最小長度
            max_length: 最大長度
            item_validator: 項目驗證器
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if not isinstance(value, list):
            raise ValidationError("值必須是列表")
        
        if len(value) < min_length:
            raise ValidationError(f"列表長度不能少於 {min_length}")
        
        if max_length is not None and len(value) > max_length:
            raise ValidationError(f"列表長度不能超過 {max_length}")
        
        if item_validator:
            for i, item in enumerate(value):
                try:
                    item_validator(item)
                except ValidationError as e:
                    raise ValidationError(f"列表項目 {i}: {str(e)}")
        
        return True
    
    @staticmethod
    def validate_dict(
        value: Dict[str, Any],
        required_keys: Optional[List[str]] = None,
        optional_keys: Optional[List[str]] = None,
        key_validators: Optional[Dict[str, callable]] = None
    ) -> bool:
        """
        驗證字典
        
        Args:
            value: 要驗證的字典
            required_keys: 必需的鍵
            optional_keys: 可選的鍵
            key_validators: 鍵值驗證器
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if not isinstance(value, dict):
            raise ValidationError("值必須是字典")
        
        # 檢查必需的鍵
        if required_keys:
            for key in required_keys:
                if key not in value:
                    raise ValidationError(f"缺少必需的鍵: {key}")
        
        # 檢查不允許的鍵
        if required_keys or optional_keys:
            allowed_keys = set(required_keys or []) | set(optional_keys or [])
            for key in value.keys():
                if key not in allowed_keys:
                    raise ValidationError(f"不允許的鍵: {key}")
        
        # 驗證鍵值
        if key_validators:
            for key, validator in key_validators.items():
                if key in value:
                    try:
                        validator(value[key])
                    except ValidationError as e:
                        raise ValidationError(f"鍵 '{key}': {str(e)}")
        
        return True
    
    @staticmethod
    def validate_date(
        value: Union[str, datetime],
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None,
        date_format: str = "%Y-%m-%d"
    ) -> bool:
        """
        驗證日期
        
        Args:
            value: 要驗證的日期
            min_date: 最小日期
            max_date: 最大日期
            date_format: 日期格式
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if isinstance(value, str):
            try:
                date_obj = datetime.strptime(value, date_format)
            except ValueError:
                raise ValidationError(f"無效的日期格式，應為 {date_format}")
        elif isinstance(value, datetime):
            date_obj = value
        else:
            raise ValidationError("日期必須是字符串或 datetime 對象")
        
        if min_date and date_obj < min_date:
            raise ValidationError(f"日期不能早於 {min_date.strftime(date_format)}")
        
        if max_date and date_obj > max_date:
            raise ValidationError(f"日期不能晚於 {max_date.strftime(date_format)}")
        
        return True
    
    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
        """
        驗證檔案擴展名
        
        Args:
            filename: 檔案名稱
            allowed_extensions: 允許的擴展名列表
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if not filename:
            raise ValidationError("檔案名稱不能為空")
        
        file_ext = Path(filename).suffix.lower()
        
        if file_ext not in [ext.lower() for ext in allowed_extensions]:
            raise ValidationError(f"不允許的檔案擴展名: {file_ext}")
        
        return True
    
    @staticmethod
    def validate_file_size(file_path: str, max_size: int) -> bool:
        """
        驗證檔案大小
        
        Args:
            file_path: 檔案路徑
            max_size: 最大大小（字節）
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        if not os.path.exists(file_path):
            raise ValidationError("檔案不存在")
        
        file_size = os.path.getsize(file_path)
        
        if file_size > max_size:
            max_size_mb = max_size / (1024 * 1024)
            raise ValidationError(f"檔案大小超過限制 ({max_size_mb:.1f}MB)")
        
        return True
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """
        驗證 IP 地址
        
        Args:
            ip: IP 地址
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            ip,
            pattern=Validators.PATTERNS['ip_address']
        )
    
    @staticmethod
    def validate_uuid(uuid_string: str) -> bool:
        """
        驗證 UUID
        
        Args:
            uuid_string: UUID 字符串
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            uuid_string,
            pattern=Validators.PATTERNS['uuid']
        )
    
    @staticmethod
    def validate_hex_color(color: str) -> bool:
        """
        驗證十六進制顏色值
        
        Args:
            color: 顏色值
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            color,
            pattern=Validators.PATTERNS['hex_color']
        )
    
    @staticmethod
    def validate_slug(slug: str) -> bool:
        """
        驗證 URL slug
        
        Args:
            slug: URL slug
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            slug,
            min_length=1,
            max_length=50,
            pattern=Validators.PATTERNS['slug']
        )
    
    @staticmethod
    def validate_chinese_name(name: str) -> bool:
        """
        驗證中文姓名
        
        Args:
            name: 中文姓名
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            name,
            min_length=2,
            max_length=8,
            pattern=Validators.PATTERNS['chinese_name']
        )
    
    @staticmethod
    def validate_english_name(name: str) -> bool:
        """
        驗證英文姓名
        
        Args:
            name: 英文姓名
            
        Returns:
            bool: 是否通過驗證
            
        Raises:
            ValidationError: 驗證失敗
        """
        return Validators.validate_string(
            name,
            min_length=2,
            max_length=50,
            pattern=Validators.PATTERNS['english_name']
        )
    
    @staticmethod
    def sanitize_string(value: str) -> str:
        """
        清理字符串（移除危險字符）
        
        Args:
            value: 要清理的字符串
            
        Returns:
            str: 清理後的字符串
        """
        if not isinstance(value, str):
            return str(value)
        
        # 移除控制字符
        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
        
        # 移除 HTML 標籤
        value = re.sub(r'<[^>]*>', '', value)
        
        # 移除 SQL 注入相關字符
        dangerous_chars = ['<', '>', '"', "'", '&', 'script', 'javascript', 'vbscript']
        for char in dangerous_chars:
            value = value.replace(char, '')
        
        return value.strip()
    
    @staticmethod
    def validate_and_sanitize(
        value: str,
        validator_func: callable,
        sanitize: bool = True
    ) -> str:
        """
        驗證並清理字符串
        
        Args:
            value: 要處理的字符串
            validator_func: 驗證函數
            sanitize: 是否清理字符串
            
        Returns:
            str: 處理後的字符串
            
        Raises:
            ValidationError: 驗證失敗
        """
        if sanitize:
            value = Validators.sanitize_string(value)
        
        validator_func(value)
        
        return value


# 便捷驗證函數
def validate_user_input(
    username: str,
    email: str,
    password: str,
    full_name: Optional[str] = None
) -> Dict[str, str]:
    """
    驗證使用者輸入
    
    Args:
        username: 用戶名
        email: 電子郵件
        password: 密碼
        full_name: 全名（可選）
        
    Returns:
        Dict[str, str]: 清理後的輸入
        
    Raises:
        ValidationError: 驗證失敗
    """
    cleaned_data = {}
    
    # 驗證用戶名
    cleaned_data['username'] = Validators.validate_and_sanitize(
        username, Validators.validate_username
    )
    
    # 驗證電子郵件
    cleaned_data['email'] = Validators.validate_and_sanitize(
        email, Validators.validate_email
    )
    
    # 驗證密碼
    Validators.validate_password(password)
    cleaned_data['password'] = password
    
    # 驗證全名（如果提供）
    if full_name:
        cleaned_data['full_name'] = Validators.validate_and_sanitize(
            full_name, lambda x: Validators.validate_string(x, min_length=2, max_length=50)
        )
    
    return cleaned_data


def validate_message_content(content: str) -> str:
    """
    驗證訊息內容
    
    Args:
        content: 訊息內容
        
    Returns:
        str: 清理後的內容
        
    Raises:
        ValidationError: 驗證失敗
    """
    return Validators.validate_and_sanitize(
        content,
        lambda x: Validators.validate_string(x, min_length=1, max_length=10000)
    )


def validate_room_name(name: str) -> str:
    """
    驗證房間名稱
    
    Args:
        name: 房間名稱
        
    Returns:
        str: 清理後的名稱
        
    Raises:
        ValidationError: 驗證失敗
    """
    return Validators.validate_and_sanitize(
        name,
        lambda x: Validators.validate_string(x, min_length=1, max_length=50)
    )