"""新的測試設定檔 - 簡化版"""

import logging
import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# 必須在 import app 模組之前設定 JWT_SECRET，
# 否則 Settings() 初始化時會因缺少必填欄位而報錯
os.environ.setdefault("JWT_SECRET", "test-secret-key-very-long-and-secure")

from app.database.mongodb import close_database, init_database  # noqa: E402
from app.database.redis_conn import close_redis, init_redis  # noqa: E402
from app.main import app  # noqa: E402

# 導入需要 Mock 的類別
from app.repositories.message_repository import MessageRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.services.message_service import MessageService
from app.services.notification_service import NotificationService
from app.services.room_service import RoomService
from app.services.user_service import UserService
from tests.test_config import TestConfig
from tests.test_database import MongoDBTestManager

logger = logging.getLogger(__name__)


@pytest.fixture
async def db_manager() -> AsyncGenerator[MongoDBTestManager]:
    """測試資料庫管理器"""
    manager = MongoDBTestManager()
    await manager.connect(TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME)
    await manager.clean_database()

    yield manager

    await manager.clean_database()
    await manager.disconnect()


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient]:
    """異步測試客戶端"""
    with patch(
        "app.middleware.rate_limiting.RateLimitingMiddleware._should_skip_rate_limiting",
        return_value=True,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client


@pytest.fixture
def test_user():
    """建立測試使用者"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "full_name": "Test User",
    }


@pytest.fixture(scope="session", autouse=True)
async def test_app_setup():
    """測試應用環境設置 - 整個測試 session 只設置一次"""
    await init_database(TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME)

    try:
        await init_redis()
    except Exception as e:
        logger.warning(f"Failed to initialize Redis in tests: {e}")

    yield

    try:
        await close_redis()
    except Exception as e:
        logger.warning(f"Failed to close Redis in tests: {e}")

    await close_database()


@pytest.fixture
async def isolated_db_manager() -> AsyncGenerator[MongoDBTestManager]:
    """隔離的資料庫管理器 - 每個測試都有乾淨的資料庫"""
    manager = MongoDBTestManager()
    await manager.connect(TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME)
    await manager.clean_database()

    yield manager

    await manager.clean_database()
    await manager.disconnect()


@pytest.fixture
async def auth_headers(async_client, test_user):
    """獲取認證標頭"""
    # 註冊使用者
    response = await async_client.post("/api/auth/register", json=test_user)
    if response.status_code == 201:
        # 註冊成功，使用註冊回應
        login_data = {
            "username": test_user["username"],
            "password": test_user["password"],
        }
        login_response = await async_client.post(
            "/api/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}

    return None


@pytest.fixture
async def auth_tokens(async_client, test_user):
    """獲取認證 token 組合（含 access_token 和 refresh_token）"""
    await async_client.post("/api/auth/register", json=test_user)
    login_response = await async_client.post(
        "/api/auth/login",
        data={
            "username": test_user["username"],
            "password": test_user["password"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if login_response.status_code == 200:
        data = login_response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "headers": {"Authorization": f"Bearer {data['access_token']}"},
        }

    return None


# ==================== Mock Repository Fixtures ====================


@pytest.fixture
def mock_message_repository():
    """Mock 訊息 Repository"""
    mock_repo = Mock(spec=MessageRepository)
    # 配置常用的 async 方法
    mock_repo.create = AsyncMock()
    mock_repo.get_by_id = AsyncMock()
    mock_repo.get_with_reply = AsyncMock()
    mock_repo.update = AsyncMock()
    mock_repo.delete = AsyncMock()
    # 加入 db 屬性
    mock_repo.db = Mock()
    return mock_repo


@pytest.fixture
def mock_room_repository():
    """Mock 房間 Repository"""
    mock_repo = Mock(spec=RoomRepository)
    # 配置常用的 async 方法
    mock_repo.get_by_id = AsyncMock()
    mock_repo.is_member = AsyncMock()
    mock_repo.create = AsyncMock()
    mock_repo.update = AsyncMock()
    mock_repo.delete = AsyncMock()
    mock_repo.add_member = AsyncMock()
    mock_repo.remove_member = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_user_repository():
    """Mock 使用者 Repository"""
    mock_repo = Mock(spec=UserRepository)
    # 配置常用的 async 方法
    mock_repo.get_by_id = AsyncMock()
    mock_repo.get_by_ids = AsyncMock()
    mock_repo.get_by_username = AsyncMock()
    mock_repo.get_by_email = AsyncMock()
    mock_repo.create = AsyncMock()
    mock_repo.update = AsyncMock()
    mock_repo.delete = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_notification_repository():
    """Mock 通知 Repository"""
    mock_repo = Mock(spec=NotificationRepository)
    # 配置常用的 async 方法
    mock_repo.create = AsyncMock()
    mock_repo.get_by_id = AsyncMock()
    mock_repo.get_by_user = AsyncMock()
    mock_repo.mark_as_read = AsyncMock()
    mock_repo.mark_all_as_read = AsyncMock()
    mock_repo.get_unread_count = AsyncMock()
    mock_repo.delete = AsyncMock()
    mock_repo.delete_by_id = AsyncMock()
    return mock_repo


# ==================== Mock Service Fixtures ====================


@pytest.fixture
def message_service_with_mocks(
    mock_message_repository, mock_room_repository, mock_user_repository
):
    """使用 Mock Repository 的訊息服務"""
    return MessageService(
        mock_message_repository, mock_room_repository, mock_user_repository
    )


@pytest.fixture
def room_service_with_mocks(
    mock_room_repository, mock_user_repository, mock_message_repository
):
    """使用 Mock Repository 的房間服務"""
    return RoomService(
        mock_room_repository, mock_user_repository, mock_message_repository
    )


@pytest.fixture
def user_service_with_mocks(mock_user_repository):
    """使用 Mock Repository 的使用者服務"""
    return UserService(mock_user_repository)


@pytest.fixture
def notification_service_with_mocks(mock_notification_repository):
    """使用 Mock Repository 的通知服務"""
    return NotificationService(mock_notification_repository)


# ==================== Real Service Fixtures (for integration tests) ====================


@pytest.fixture
async def message_service(db_manager: MongoDBTestManager):
    """使用真實資料庫的訊息服務（整合測試用）"""
    message_repo = MessageRepository(db_manager.database)
    room_repo = RoomRepository(db_manager.database)
    user_repo = UserRepository(db_manager.database)
    return MessageService(message_repo, room_repo, user_repo)
