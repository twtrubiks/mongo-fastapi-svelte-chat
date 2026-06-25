"""應用程式設定檔案"""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """應用程式設定類別"""

    # MongoDB 設定（含認證的連線字串請放 .env，預設值不帶憑證）
    MONGODB_URL: str = "mongodb://localhost:27017"
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

    # AI 助理（@bot / summary）— 供應商切換：nvidia（NIM，OpenAI 相容端點）| gemini（Google 原生 SDK）
    AI_PROVIDER: str = "nvidia"
    # NVIDIA NIM（OpenAI 相容端點）；未設定 key 時 @bot 回「尚未配置」而不打 API；取得 key：https://build.nvidia.com/
    NVIDIA_API_KEY: str | None = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3-super-120b-a12b"
    # Gemini（Google AI Studio）；AI_PROVIDER=gemini 時生效，取得 key：https://aistudio.google.com/
    GOOGLE_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    # 每使用者每分鐘 @bot 上限（複用 Redis 滑動視窗）
    BOT_RATE_LIMIT_PER_MINUTE: int = 5

    # 應用程式設定（安全預設：DEBUG 預設關閉，開發環境在 .env 設 DEBUG=true）
    DEBUG: bool = False
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS 和允許的主機設定
    ALLOWED_HOSTS: str = "*"  # 開發環境允許所有主機，生產環境應該限制
    CORS_ORIGINS: str = "*"  # 開發環境允許所有來源，生產環境應該限制

    # 檔案上傳設定
    UPLOAD_DIR: str = "uploads"
    GENERATE_THUMBNAILS: bool = True

    model_config = ConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
