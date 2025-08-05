from typing import Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.config import settings
from app.database.mongodb import init_database, close_database
from app.database.redis_conn import init_redis, close_redis, get_redis
from app.routers import auth, rooms, messages, notifications
from app.routers import files, invitations
from app.websocket import routes as websocket_routes
from app.core.fastapi_integration import (
    setup_dependency_injection,
    cleanup_dependency_injection,
    request_scope_middleware,
    get_health_check_info
)
from app.middleware.error_handler import GlobalErrorHandler
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.rate_limiting import RateLimitingMiddleware
from app.security_config import load_security_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時初始化
    await init_database(settings.MONGODB_URL, settings.MONGODB_DATABASE)
    await init_redis()
    await setup_dependency_injection(app)
    yield
    # 關閉時清理
    await cleanup_dependency_injection(app)
    await close_database()
    await close_redis()

app = FastAPI(
    title="即時聊天室 API",
    description="使用 FastAPI + MongoDB + WebSocket 的即時聊天室",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.DEBUG
)

# 首先設定 CORS - 必須在其他中間件之前
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 設定信任的主機
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1"]
    )

# 載入安全配置
security_config = load_security_config()
# 根據 DEBUG 模式調整配置
security_config.development_mode = settings.DEBUG

# 添加安全標頭中間件 (應該在錯誤處理之前)
security_middleware = SecurityHeadersMiddleware(
    enable_hsts=security_config.enable_hsts and not settings.DEBUG,
    hsts_max_age=security_config.hsts_max_age,
    enable_csp=security_config.enable_csp,
    custom_headers=security_config.get_security_headers()
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    return await security_middleware(request, call_next)

# 添加 Rate Limiting 中間件 (在錯誤處理之前)
app.add_middleware(RateLimitingMiddleware, settings=settings)

# 添加全域錯誤處理中間件 (最先執行)
app.add_middleware(GlobalErrorHandler, debug=settings.DEBUG)

# 添加請求作用域中介軟體
app.middleware("http")(request_scope_middleware)

# 註冊 API 路由
app.include_router(auth.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(invitations.router, prefix="/api")

# 註冊 WebSocket 路由
app.include_router(websocket_routes.router)

@app.get("/")
async def read_root():
    return {
        "message": "即時聊天室 API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check(request: Request):
    health_info = await get_health_check_info(request)
    return {
        "service": "chatroom-api",
        "version": "1.0.0",
        "dependency_injection": health_info
    }