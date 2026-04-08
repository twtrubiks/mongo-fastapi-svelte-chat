"""應用程式設定檔案"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """應用程式設定類別"""

    # MongoDB 設定
    MONGODB_URL: str = "mongodb://root:password@localhost:27017"
    MONGODB_DATABASE: str = "chatroom"

    # JWT 設定（必須透過環境變數或 .env 設定，無預設值）
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 小時
    JWT_REFRESH_EXPIRE_DAYS: int = 7  # Refresh token 有效期 7 天

    # Redis 設定
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str | None = None
    REDIS_MAX_CONNECTIONS: int = 20
    USER_CACHE_TTL: int = 300  # 使用者快取 TTL（秒），預設 5 分鐘

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000
    RATE_LIMIT_BURST_SIZE: int = 10

    # 應用程式設定
    DEBUG: bool = True
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS 和允許的主機設定
    ALLOWED_HOSTS: str = "*"  # 開發環境允許所有主機，生產環境應該限制
    CORS_ORIGINS: str = "*"  # 開發環境允許所有來源，生產環境應該限制

    # 檔案上傳設定
    UPLOAD_DIR: str = "uploads"
    GENERATE_THUMBNAILS: bool = True

    model_config = ConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
