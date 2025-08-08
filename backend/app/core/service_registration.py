"""服務註冊配置"""

import logging

from app.cache.cache_manager import CacheManager
from app.core.container import DIContainer
from app.database.mongodb import get_database
from app.database.redis_conn import get_redis
from app.repositories.message_repository import MessageRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.services.invitation_service import InvitationService
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService
from app.services.room_service import RoomService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


async def configure_services(container: DIContainer) -> None:
    """
    配置依賴注入容器

    Args:
        container: DI 容器實例
    """
    logger.info("Configuring dependency injection services...")

    # 註冊 Repository 工廠函數
    container.register_singleton(UserRepository, factory=create_user_repository)

    container.register_singleton(RoomRepository, factory=create_room_repository)

    container.register_singleton(MessageRepository, factory=create_message_repository)

    container.register_singleton(
        NotificationRepository, factory=create_notification_repository
    )

    # 註冊 Service 工廠函數
    container.register_singleton(UserService, factory=create_user_service)

    container.register_singleton(RoomService, factory=create_room_service)

    container.register_singleton(MessageService, factory=create_message_service)

    container.register_singleton(
        NotificationService, factory=create_notification_service
    )

    container.register_singleton(InvitationService, factory=create_invitation_service)

    # 註冊快取管理器
    container.register_singleton(CacheManager, factory=create_cache_manager)

    logger.info("Dependency injection services configured successfully")


# Repository 工廠函數
async def create_user_repository() -> UserRepository:
    """創建 UserRepository 實例"""
    db = await get_database()
    return UserRepository(db)


async def create_room_repository() -> RoomRepository:
    """創建 RoomRepository 實例"""
    db = await get_database()
    return RoomRepository(db)


async def create_message_repository() -> MessageRepository:
    """創建 MessageRepository 實例"""
    db = await get_database()
    return MessageRepository(db)


async def create_notification_repository() -> NotificationRepository:
    """創建 NotificationRepository 實例"""
    db = await get_database()
    return NotificationRepository(db)


# Service 工廠函數
async def create_user_service() -> UserService:
    """創建 UserService 實例"""
    # 取得資料庫並創建 repositories
    db = await get_database()
    user_repo = UserRepository(db)
    room_repo = RoomRepository(db)
    message_repo = MessageRepository(db)
    return UserService(user_repo, room_repo, message_repo)


async def create_room_service() -> RoomService:
    """創建 RoomService 實例"""
    # 取得資料庫並創建 repositories
    db = await get_database()
    room_repo = RoomRepository(db)
    user_repo = UserRepository(db)
    message_repo = MessageRepository(db)
    return RoomService(room_repo, user_repo, message_repo)


async def create_message_service() -> MessageService:
    """創建 MessageService 實例"""
    # 取得資料庫並創建 repositories
    db = await get_database()
    message_repo = MessageRepository(db)
    room_repo = RoomRepository(db)
    return MessageService(message_repo, room_repo)


async def create_notification_service() -> NotificationService:
    """創建 NotificationService 實例"""
    # 取得資料庫並創建 repositories
    db = await get_database()
    notification_repo = NotificationRepository(db)
    return NotificationService(notification_repo)


async def create_invitation_service() -> InvitationService:
    """創建 InvitationService 實例"""
    # 取得資料庫並創建 repositories
    db = await get_database()
    room_repo = RoomRepository(db)
    user_repo = UserRepository(db)
    return InvitationService(db, room_repo, user_repo)


async def create_cache_manager() -> CacheManager:
    """創建 CacheManager 實例"""
    redis_client = await get_redis()
    return CacheManager(redis_client)


# 便利函數：為測試環境配置模擬服務
async def configure_test_services(container: DIContainer) -> None:
    """
    為測試環境配置依賴注入容器

    Args:
        container: DI 容器實例
    """
    from unittest.mock import AsyncMock

    logger.info("Configuring test dependency injection services...")

    # 註冊模擬的 Repository
    container.register_singleton(
        UserRepository, instance=AsyncMock(spec=UserRepository)
    )
    container.register_singleton(
        RoomRepository, instance=AsyncMock(spec=RoomRepository)
    )
    container.register_singleton(
        MessageRepository, instance=AsyncMock(spec=MessageRepository)
    )
    container.register_singleton(
        NotificationRepository, instance=AsyncMock(spec=NotificationRepository)
    )

    # 註冊模擬的 Service
    container.register_singleton(UserService, instance=AsyncMock(spec=UserService))
    container.register_singleton(RoomService, instance=AsyncMock(spec=RoomService))
    container.register_singleton(
        MessageService, instance=AsyncMock(spec=MessageService)
    )
    container.register_singleton(
        NotificationService, instance=AsyncMock(spec=NotificationService)
    )
    container.register_singleton(
        InvitationService, instance=AsyncMock(spec=InvitationService)
    )

    logger.info("Test dependency injection services configured successfully")


# 服務健康檢查
async def health_check_services(container: DIContainer) -> dict:
    """
    檢查所有服務的健康狀態

    Args:
        container: DI 容器實例

    Returns:
        dict: 健康檢查結果
    """
    health_status = {"status": "healthy", "services": {}, "errors": []}

    try:
        # 檢查 Repository 層
        repositories = [
            (UserRepository, "user_repository"),
            (RoomRepository, "room_repository"),
            (MessageRepository, "message_repository"),
            (NotificationRepository, "notification_repository"),
        ]

        for repo_type, name in repositories:
            try:
                await container.get(repo_type)
                health_status["services"][name] = "healthy"
                logger.debug(f"Repository {name} is healthy")
            except Exception as e:
                health_status["services"][name] = "unhealthy"
                health_status["errors"].append(f"{name}: {str(e)}")
                health_status["status"] = "unhealthy"
                logger.error(f"Repository {name} health check failed: {e}")

        # 檢查 Service 層
        services = [
            (UserService, "user_service"),
            (RoomService, "room_service"),
            (MessageService, "message_service"),
            (NotificationService, "notification_service"),
            (InvitationService, "invitation_service"),
        ]

        for service_type, name in services:
            try:
                await container.get(service_type)
                health_status["services"][name] = "healthy"
                logger.debug(f"Service {name} is healthy")
            except Exception as e:
                health_status["services"][name] = "unhealthy"
                health_status["errors"].append(f"{name}: {str(e)}")
                health_status["status"] = "unhealthy"
                logger.error(f"Service {name} health check failed: {e}")

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["errors"].append(f"General health check error: {str(e)}")
        logger.error(f"General health check failed: {e}")

    return health_status
