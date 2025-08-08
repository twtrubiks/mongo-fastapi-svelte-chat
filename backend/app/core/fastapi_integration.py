"""FastAPI 依賴注入整合"""

import logging
import uuid
from typing import TypeVar

from fastapi import Depends, HTTPException, Request, status

from app.core.container import get_container
from app.core.service_registration import configure_services
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

T = TypeVar("T")


def create_dependency_factory[T](service_type: type[T]):
    """
    創建 FastAPI 依賴注入工廠函數

    Args:
        service_type: 服務類型

    Returns:
        依賴注入函數
    """

    async def dependency_factory(request: Request = None) -> T:
        """依賴注入函數"""
        try:
            container = get_container()

            # 為每個請求生成唯一的作用域 ID
            scope_id = None
            if request:
                if not hasattr(request.state, "scope_id"):
                    request.state.scope_id = str(uuid.uuid4())
                scope_id = request.state.scope_id

            service = await container.get(service_type, scope_id=scope_id)
            return service

        except Exception as e:
            logger.error(f"Error resolving dependency {service_type.__name__}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: Unable to resolve {service_type.__name__}",
            ) from e

    return dependency_factory


# 創建依賴注入函數
def get_user_repository() -> UserRepository:
    """獲取 UserRepository 依賴"""
    return Depends(create_dependency_factory(UserRepository))


def get_room_repository() -> RoomRepository:
    """獲取 RoomRepository 依賴"""
    return Depends(create_dependency_factory(RoomRepository))


def get_message_repository() -> MessageRepository:
    """獲取 MessageRepository 依賴"""
    return Depends(create_dependency_factory(MessageRepository))


def get_notification_repository() -> NotificationRepository:
    """獲取 NotificationRepository 依賴"""
    return Depends(create_dependency_factory(NotificationRepository))


def get_user_service() -> UserService:
    """獲取 UserService 依賴"""
    return Depends(create_dependency_factory(UserService))


def get_room_service() -> RoomService:
    """獲取 RoomService 依賴"""
    return Depends(create_dependency_factory(RoomService))


def get_message_service() -> MessageService:
    """獲取 MessageService 依賴"""
    return Depends(create_dependency_factory(MessageService))


def get_notification_service() -> NotificationService:
    """獲取 NotificationService 依賴"""
    return Depends(create_dependency_factory(NotificationService))


def get_invitation_service() -> InvitationService:
    """獲取 InvitationService 依賴"""
    return Depends(create_dependency_factory(InvitationService))


# 便利的依賴注入別名
UserRepositoryDep = get_user_repository()
RoomRepositoryDep = get_room_repository()
MessageRepositoryDep = get_message_repository()
NotificationRepositoryDep = get_notification_repository()

UserServiceDep = get_user_service()
RoomServiceDep = get_room_service()
MessageServiceDep = get_message_service()
NotificationServiceDep = get_notification_service()
InvitationServiceDep = get_invitation_service()


async def setup_dependency_injection(app) -> None:
    """
    設置依賴注入系統

    Args:
        app: FastAPI 應用實例
    """
    logger.info("Setting up dependency injection system...")

    try:
        # 獲取容器並配置服務
        container = get_container()
        await configure_services(container)

        # 將容器添加到應用狀態中
        app.state.di_container = container

        logger.info("Dependency injection system setup completed")

    except Exception as e:
        logger.error(f"Failed to setup dependency injection: {e}")
        raise


async def cleanup_dependency_injection(app) -> None:
    """
    清理依賴注入系統

    Args:
        app: FastAPI 應用實例
    """
    logger.info("Cleaning up dependency injection system...")

    try:
        if hasattr(app.state, "di_container"):
            container = app.state.di_container
            container.clear_all_scopes()
            logger.info("Dependency injection system cleanup completed")

    except Exception as e:
        logger.error(f"Failed to cleanup dependency injection: {e}")


# 中介軟體：請求作用域管理
async def request_scope_middleware(request: Request, call_next):
    """
    請求作用域中介軟體

    為每個請求創建唯一的作用域，請求結束後自動清理
    """
    scope_id = str(uuid.uuid4())
    request.state.scope_id = scope_id

    try:
        response = await call_next(request)
        return response
    finally:
        # 清理請求作用域
        try:
            if hasattr(request.app.state, "di_container"):
                container = request.app.state.di_container
                container.clear_scope(scope_id)
        except Exception as e:
            logger.warning(f"Failed to clear request scope {scope_id}: {e}")


# 健康檢查端點用的依賴
async def get_health_check_info(request: Request) -> dict:
    """
    獲取健康檢查資訊

    Args:
        request: FastAPI 請求對象

    Returns:
        dict: 健康檢查資訊
    """
    try:
        if hasattr(request.app.state, "di_container"):
            container = request.app.state.di_container
            from app.core.service_registration import health_check_services

            return await health_check_services(container)
        else:
            return {
                "status": "unhealthy",
                "error": "Dependency injection container not found",
            }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
