"""
測試 FastAPI 依賴注入工廠函數
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.params import Depends as DependsClass

from app.core.fastapi_integration import (
    InvitationServiceDep,
    MessageServiceDep,
    NotificationServiceDep,
    RoomServiceDep,
    UserServiceDep,
    create_invitation_service,
    create_message_service,
    create_notification_service,
    create_room_service,
    create_user_service,
    get_health_check_info,
)
from app.services.invitation_service import InvitationService
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService
from app.services.room_service import RoomService
from app.services.user_service import UserService


class TestServiceFactories:
    """測試 Service 工廠函數"""

    @pytest.mark.asyncio
    async def test_create_user_service(self):
        """測試建立 UserService"""
        mock_db = AsyncMock()
        with patch("app.core.fastapi_integration.get_database", return_value=mock_db):
            service = await create_user_service()
            assert isinstance(service, UserService)

    @pytest.mark.asyncio
    async def test_create_room_service(self):
        """測試建立 RoomService"""
        mock_db = AsyncMock()
        with patch("app.core.fastapi_integration.get_database", return_value=mock_db):
            service = await create_room_service()
            assert isinstance(service, RoomService)

    @pytest.mark.asyncio
    async def test_create_message_service(self):
        """測試建立 MessageService"""
        mock_db = AsyncMock()
        with patch("app.core.fastapi_integration.get_database", return_value=mock_db):
            service = await create_message_service()
            assert isinstance(service, MessageService)

    @pytest.mark.asyncio
    async def test_create_notification_service(self):
        """測試建立 NotificationService"""
        mock_db = AsyncMock()
        with patch("app.core.fastapi_integration.get_database", return_value=mock_db):
            service = await create_notification_service()
            assert isinstance(service, NotificationService)

    @pytest.mark.asyncio
    async def test_create_invitation_service(self):
        """測試建立 InvitationService"""
        mock_db = AsyncMock()
        with patch("app.core.fastapi_integration.get_database", return_value=mock_db):
            service = await create_invitation_service()
            assert isinstance(service, InvitationService)


class TestDependsAliases:
    """測試 FastAPI Depends 別名"""

    def test_user_service_dep(self):
        assert isinstance(UserServiceDep, DependsClass)

    def test_room_service_dep(self):
        assert isinstance(RoomServiceDep, DependsClass)

    def test_message_service_dep(self):
        assert isinstance(MessageServiceDep, DependsClass)

    def test_notification_service_dep(self):
        assert isinstance(NotificationServiceDep, DependsClass)

    def test_invitation_service_dep(self):
        assert isinstance(InvitationServiceDep, DependsClass)


class TestHealthCheck:
    """測試健康檢查"""

    @pytest.mark.asyncio
    async def test_healthy(self):
        """MongoDB 和 Redis 都正常時回傳 healthy"""
        mock_db = AsyncMock()
        mock_db.command = AsyncMock()
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with (
            patch("app.core.fastapi_integration.get_database", return_value=mock_db),
            patch("app.core.fastapi_integration.get_redis", return_value=mock_redis),
        ):
            result = await get_health_check_info()
            assert result["status"] == "healthy"
            assert result["checks"]["mongodb"] == "connected"
            assert result["checks"]["redis"] == "connected"
            assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_mongodb_down(self):
        """MongoDB 連線失敗時回傳 unhealthy"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock()

        with (
            patch(
                "app.core.fastapi_integration.get_database",
                side_effect=Exception("Connection refused"),
            ),
            patch("app.core.fastapi_integration.get_redis", return_value=mock_redis),
        ):
            result = await get_health_check_info()
            assert result["status"] == "unhealthy"
            assert result["checks"]["mongodb"] == "disconnected"
            assert len(result["errors"]) == 1

    @pytest.mark.asyncio
    async def test_redis_down(self):
        """Redis 連線失敗時回傳 unhealthy"""
        mock_db = AsyncMock()
        mock_db.command = AsyncMock()

        with (
            patch("app.core.fastapi_integration.get_database", return_value=mock_db),
            patch(
                "app.core.fastapi_integration.get_redis",
                side_effect=Exception("Connection refused"),
            ),
        ):
            result = await get_health_check_info()
            assert result["status"] == "unhealthy"
            assert result["checks"]["mongodb"] == "connected"
            assert result["checks"]["redis"] == "disconnected"

    @pytest.mark.asyncio
    async def test_both_down(self):
        """MongoDB 和 Redis 都失敗時回傳 unhealthy"""
        with (
            patch(
                "app.core.fastapi_integration.get_database",
                side_effect=Exception("MongoDB down"),
            ),
            patch(
                "app.core.fastapi_integration.get_redis",
                side_effect=Exception("Redis down"),
            ),
        ):
            result = await get_health_check_info()
            assert result["status"] == "unhealthy"
            assert len(result["errors"]) == 2
