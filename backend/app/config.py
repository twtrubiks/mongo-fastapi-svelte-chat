"""應用程式設定檔案"""
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional

class Settings(BaseSettings):
    """應用程式設定類別"""
    
    # MongoDB 設定
    MONGODB_URL: str = "mongodb://root:password@localhost:27017"
    MONGODB_DATABASE: str = "chatroom"
    MONGODB_MIN_POOL_SIZE: int = 5
    MONGODB_MAX_POOL_SIZE: int = 50
    MONGODB_SERVER_SELECTION_TIMEOUT: int = 5000
    MONGODB_SOCKET_TIMEOUT: int = 10000
    MONGODB_CONNECT_TIMEOUT: int = 10000
    
    # JWT 設定
    JWT_SECRET: str = "your_super_secret_jwt_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30
    
    # Redis 設定
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    REDIS_MAX_CONNECTIONS: int = 20
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    RATE_LIMIT_BURST_SIZE: int = 10
    
    # 應用程式設定
    DEBUG: bool = True
    
    # 檔案上傳設定
    MAX_FILE_SIZE: int = 10485760  # 10MB
    UPLOAD_DIR: str = "uploads"
    
    # 檔案類型限制
    ALLOWED_IMAGE_EXTENSIONS: str = ".jpg,.jpeg,.png,.gif,.webp,.bmp"
    ALLOWED_DOCUMENT_EXTENSIONS: str = ".pdf,.doc,.docx,.txt,.md"
    ALLOWED_VIDEO_EXTENSIONS: str = ".mp4,.mov,.avi,.mkv,.webm"
    ALLOWED_AUDIO_EXTENSIONS: str = ".mp3,.wav,.ogg,.m4a,.flac"
    
    # 檔案大小限制（字節）
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_DOCUMENT_SIZE: int = 50 * 1024 * 1024  # 50MB
    MAX_VIDEO_SIZE: int = 100 * 1024 * 1024  # 100MB
    MAX_AUDIO_SIZE: int = 20 * 1024 * 1024  # 20MB
    
    # 圖片處理設定
    IMAGE_QUALITY: int = 85
    GENERATE_THUMBNAILS: bool = True
    THUMBNAIL_SIZES: str = "small:150x150,medium:300x300,large:600x600"
    
    # 檔案清理設定
    AUTO_CLEANUP_ENABLED: bool = True
    CLEANUP_DAYS: int = 30
    
    # 檔案儲存設定
    ENABLE_FILE_DEDUPLICATION: bool = True
    FILE_HASH_ALGORITHM: str = "sha256"
    
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True
    )

settings = Settings()