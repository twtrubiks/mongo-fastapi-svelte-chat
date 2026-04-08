from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.exceptions import AppError
from app.core.fastapi_integration import get_health_check_info
from app.database.indexes import ensure_indexes
from app.database.mongodb import close_database, get_database, init_database
from app.database.redis_conn import close_redis, init_redis
from app.middleware.error_handler import GlobalErrorHandler
from app.middleware.rate_limiting import RateLimitingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routers import (
    auth,
    files,
    invitations,
    messages,
    notifications,
    rooms,
    ws_ticket,
)
from app.security_config import load_security_config
from app.websocket import routes as websocket_routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # 啟動時初始化
    await init_database(settings.MONGODB_URL, settings.MONGODB_DATABASE)
    await init_redis()
    # 建立 MongoDB 索引（冪等，已存在會跳過）
    db = await get_database()
    await ensure_indexes(db)
    yield
    # 關閉時清理
    await close_database()
    await close_redis()


app = FastAPI(
    title="即時聊天室 API",
    description="使用 FastAPI + MongoDB + WebSocket 的即時聊天室",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# 首先設定 CORS - 必須在其他中間件之前
# 動態設置 CORS origins
cors_origins = []
if settings.DEBUG:
    # 開發環境：允許所有來源
    cors_origins = ["*"]
else:
    # 生產環境：使用配置的來源
    if settings.CORS_ORIGINS == "*":
        cors_origins = ["*"]
    else:
        cors_origins = settings.CORS_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 設定信任的主機
if not settings.DEBUG:
    # 生產環境才限制主機
    allowed_hosts = (
        settings.ALLOWED_HOSTS.split(",") if settings.ALLOWED_HOSTS != "*" else None
    )
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# 載入安全配置
security_config = load_security_config()
# 根據 DEBUG 模式調整配置
security_config.development_mode = settings.DEBUG

# 添加安全標頭中間件 (應該在錯誤處理之前)
security_middleware = SecurityHeadersMiddleware(
    enable_hsts=security_config.enable_hsts and not settings.DEBUG,
    hsts_max_age=security_config.hsts_max_age,
    enable_csp=security_config.enable_csp,
    custom_headers=security_config.get_security_headers(),
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Any:
    return await security_middleware(request, call_next)


# 添加 Rate Limiting 中間件 (在錯誤處理之前)
app.add_middleware(RateLimitingMiddleware, settings=settings)

# 添加全域錯誤處理中間件 (最先執行)
app.add_middleware(GlobalErrorHandler, debug=settings.DEBUG)


# 註冊業務異常處理器（AppError 子類別 → 對應 HTTP 狀態碼 + {"detail": "..."} 格式）
# 基礎設施異常（PyMongoError、RedisError 等）由 GlobalErrorHandler middleware 處理
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=exc.headers,
    )


# 註冊 API 路由
app.include_router(auth.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(invitations.router, prefix="/api")
app.include_router(ws_ticket.router, prefix="/api")

# 註冊 WebSocket 路由
app.include_router(websocket_routes.router)


@app.get("/")
async def read_root() -> dict[str, str]:
    return {"message": "即時聊天室 API", "status": "running", "version": "1.0.0"}


@app.get("/health")
async def health_check() -> dict[str, Any]:
    health_info = await get_health_check_info()
    return {
        "service": "chatroom-api",
        "version": "1.0.0",
        "infrastructure": health_info,
    }
