"""FastAPI 依賴注入工廠函數"""

import logging

from fastapi import Depends

from app.database.mongodb import get_database
from app.database.redis_conn import get_redis
from app.repositories.invitation_repository import InvitationRepository
from app.repositories.join_request_repository import JoinRequestRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.services.file_service import FileService
from app.services.invitation_service import InvitationService
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService
from app.services.room_service import RoomService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


# --- Repository 工廠函數（供 auth dependency 等非 Service 場景使用）---


async def create_room_repository() -> RoomRepository:
    db = await get_database()
    return RoomRepository(db)


# --- Service 工廠函數 ---
# HTTP Router：透過 Depends() 注入（見下方 *Dep 別名）
# WebSocket handler：直接 await 呼叫（如 `svc = await create_message_service()`）
#   因為 FastAPI 的 Depends() 僅支援 HTTP path operation，
#   WebSocket endpoint 無法使用相同的 DI 機制，故以工廠函數統一建立邏輯。


async def create_user_service() -> UserService:
    db = await get_database()
    return UserService(UserRepository(db))


async def create_room_service() -> RoomService:
    from app.websocket.manager import connection_manager

    db = await get_database()
    return RoomService(
        RoomRepository(db),
        UserRepository(db),
        MessageRepository(db),
        connection_manager=connection_manager,
    )


async def create_message_service() -> MessageService:
    db = await get_database()
    return MessageService(MessageRepository(db), RoomRepository(db), UserRepository(db))


async def create_notification_service() -> NotificationService:
    from app.websocket.manager import connection_manager

    db = await get_database()
    return NotificationService(
        NotificationRepository(db), connection_manager=connection_manager
    )


async def create_invitation_service() -> InvitationService:
    db = await get_database()
    return InvitationService(
        InvitationRepository(db),
        JoinRequestRepository(db),
        RoomRepository(db),
        UserRepository(db),
    )


async def create_file_service() -> FileService:
    from app.utils.file_upload import get_file_upload_manager
    from app.utils.image_processor import get_image_processor

    return FileService(
        file_manager=get_file_upload_manager(),
        image_processor=get_image_processor(),
    )


# --- FastAPI Depends 別名（Router 直接使用，保持原有 import 介面）---

UserServiceDep = Depends(create_user_service)
RoomServiceDep = Depends(create_room_service)
MessageServiceDep = Depends(create_message_service)
NotificationServiceDep = Depends(create_notification_service)
InvitationServiceDep = Depends(create_invitation_service)
FileServiceDep = Depends(create_file_service)


# --- 健康檢查 ---


async def get_health_check_info() -> dict:
    """檢查基礎設施健康狀態（MongoDB + Redis）"""
    health = {"status": "healthy", "checks": {}, "errors": []}

    # 檢查 MongoDB
    try:
        db = await get_database()
        await db.command("ping")
        health["checks"]["mongodb"] = "connected"
    except Exception as e:  # intentional catch-all: 健康檢查需捕獲所有連線異常
        health["checks"]["mongodb"] = "disconnected"
        health["errors"].append(f"mongodb: {e}")
        health["status"] = "unhealthy"

    # 檢查 Redis
    try:
        client = await get_redis()
        await client.ping()
        health["checks"]["redis"] = "connected"
    except Exception as e:  # intentional catch-all: 健康檢查需捕獲所有連線異常
        health["checks"]["redis"] = "disconnected"
        health["errors"].append(f"redis: {e}")
        health["status"] = "unhealthy"

    return health
