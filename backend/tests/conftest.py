"""新的測試設定檔 - 簡化版"""
import pytest
import asyncio
import logging
from typing import AsyncGenerator
from unittest.mock import Mock, AsyncMock
from httpx import AsyncClient
from app.main import app
from tests.test_database import MongoDBTestManager
from tests.test_helpers import DataTestHelper
from tests.test_config import TestConfig
from app.database.mongodb import init_database, close_database
from app.database.redis_conn import init_redis, close_redis
from app.core.fastapi_integration import setup_dependency_injection, cleanup_dependency_injection

# 導入需要 Mock 的類別
from app.repositories.message_repository import MessageRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from app.repositories.notification_repository import NotificationRepository
from app.services.message_service import MessageService
from app.services.room_service import RoomService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """建立事件循環"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
async def db_manager() -> AsyncGenerator[MongoDBTestManager, None]:
    """測試資料庫管理器"""
    manager = MongoDBTestManager()
    await manager.connect(TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME)
    await manager.clean_database()
    
    yield manager
    
    await manager.clean_database()
    await manager.disconnect()


@pytest.fixture
def db_manager_sync(event_loop):
    """同步的資料庫管理器 fixture"""
    async def _get_db_manager():
        manager = MongoDBTestManager()
        await manager.connect(TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME)
        await manager.clean_database()
        
        yield manager
        
        await manager.clean_database()
        await manager.disconnect()
    
    manager_gen = _get_db_manager()
    manager = event_loop.run_until_complete(manager_gen.__anext__())
    yield manager
    try:
        event_loop.run_until_complete(manager_gen.__anext__())
    except StopAsyncIteration:
        pass


@pytest.fixture
async def test_helper(db_manager: MongoDBTestManager) -> DataTestHelper:
    """測試輔助工具"""
    return DataTestHelper(db_manager)


@pytest.fixture
async def test_client() -> AsyncClient:
    """測試客戶端"""
    # 在測試期間停用 rate limiting
    from unittest.mock import patch
    with patch('app.middleware.rate_limiting.RateLimitingMiddleware._should_skip_rate_limiting', return_value=True):
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client


@pytest.fixture
def async_client(event_loop):
    """異步測試客戶端"""
    # 在測試期間停用 rate limiting
    from unittest.mock import patch
    with patch('app.middleware.rate_limiting.RateLimitingMiddleware._should_skip_rate_limiting', return_value=True):
        async def _get_client():
            async with AsyncClient(app=app, base_url="http://test") as client:
                yield client
        
        client_gen = _get_client()
        client = event_loop.run_until_complete(client_gen.__anext__())
        yield client
        try:
            event_loop.run_until_complete(client_gen.__anext__())
        except StopAsyncIteration:
            pass


@pytest.fixture
async def test_data(test_helper: DataTestHelper) -> dict:
    """完整的測試資料"""
    return await test_helper.setup_test_data()


@pytest.fixture
def test_user():
    """建立測試使用者"""
    return {
        "username": "testuser",
        "email": "test@example.com", 
        "password": "testpass123",
        "full_name": "Test User"
    }


@pytest.fixture(scope="session", autouse=True)
def test_app_setup(event_loop):
    """測試應用環境設置 - 整個測試 session 只設置一次"""
    # 初始化測試資料庫、Redis 和依賴注入
    event_loop.run_until_complete(init_database(TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME))
    
    # 嘗試初始化 Redis，如果失敗則跳過
    try:
        event_loop.run_until_complete(init_redis())
    except Exception as e:
        logger.warning(f"Failed to initialize Redis in tests: {e}")
    
    event_loop.run_until_complete(setup_dependency_injection(app))
    
    yield
    
    # 清理
    event_loop.run_until_complete(cleanup_dependency_injection(app))
    
    # 嘗試關閉 Redis，如果失敗則忽略
    try:
        event_loop.run_until_complete(close_redis())
    except Exception as e:
        logger.warning(f"Failed to close Redis in tests: {e}")
    
    event_loop.run_until_complete(close_database())


@pytest.fixture
def isolated_db_manager(event_loop):
    """隔離的資料庫管理器 - 每個測試都有乾淨的資料庫"""
    async def _get_manager():
        manager = MongoDBTestManager()
        await manager.connect(TestConfig.TEST_MONGODB_URL, TestConfig.TEST_DATABASE_NAME)
        await manager.clean_database()
        
        yield manager
        
        await manager.clean_database()
        await manager.disconnect()
    
    manager_gen = _get_manager()
    manager = event_loop.run_until_complete(manager_gen.__anext__())
    yield manager
    try:
        event_loop.run_until_complete(manager_gen.__anext__())
    except StopAsyncIteration:
        pass


@pytest.fixture
async def auth_headers(async_client, test_user):
    """獲取認證標頭"""
    # 註冊使用者
    response = await async_client.post("/api/auth/register", json=test_user)
    if response.status_code == 201:
        # 註冊成功，使用註冊回應
        login_data = {
            "username": test_user["username"],
            "password": test_user["password"]
        }
        login_response = await async_client.post(
            "/api/auth/login",
            data=login_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            return {"Authorization": f"Bearer {token}"}
    
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
    mock_repo.find_by_room_id = AsyncMock()
    mock_repo.update = AsyncMock()
    mock_repo.delete = AsyncMock()
    mock_repo.get_recent_messages = AsyncMock()
    mock_repo.mark_messages_as_read = AsyncMock()
    mock_repo.get_unread_count = AsyncMock()
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
    mock_repo.is_owner = AsyncMock()
    mock_repo.create = AsyncMock()
    mock_repo.update = AsyncMock()
    mock_repo.delete = AsyncMock()
    mock_repo.add_member = AsyncMock()
    mock_repo.remove_member = AsyncMock()
    mock_repo.check_room_name_exists = AsyncMock()
    return mock_repo


@pytest.fixture
def mock_user_repository():
    """Mock 使用者 Repository"""
    mock_repo = Mock(spec=UserRepository)
    # 配置常用的 async 方法
    mock_repo.get_by_id = AsyncMock()
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
    mock_repo.create_from_data = AsyncMock()
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
def message_service_with_mocks(mock_message_repository, mock_room_repository):
    """使用 Mock Repository 的訊息服務"""
    return MessageService(mock_message_repository, mock_room_repository)


@pytest.fixture
def room_service_with_mocks(mock_room_repository, mock_user_repository, mock_message_repository):
    """使用 Mock Repository 的房間服務"""
    return RoomService(mock_room_repository, mock_user_repository, mock_message_repository)


@pytest.fixture
def user_service_with_mocks(mock_user_repository, mock_room_repository, mock_message_repository):
    """使用 Mock Repository 的使用者服務"""
    return UserService(mock_user_repository, mock_room_repository, mock_message_repository)


@pytest.fixture
def notification_service_with_mocks(mock_notification_repository):
    """使用 Mock Repository 的通知服務"""
    from app.services.notification_service import NotificationService
    return NotificationService(mock_notification_repository)


@pytest.fixture
def invitation_service_with_mocks(mock_room_repository, mock_user_repository):
    """使用 Mock Repository 的邀請服務"""
    from app.services.invitation_service import InvitationService
    from unittest.mock import Mock
    
    # 創建 Mock 資料庫
    mock_db = Mock()
    
    # 創建 Mock collections
    # 使用 Mock 而不是 AsyncMock，因為 find() 應該返回 cursor 而不是 coroutine
    mock_invitations_collection = Mock()
    mock_join_requests_collection = Mock()
    
    # 配置異步方法
    mock_invitations_collection.insert_one = AsyncMock()
    mock_invitations_collection.find_one = AsyncMock()
    mock_invitations_collection.update_one = AsyncMock()
    mock_invitations_collection.delete_one = AsyncMock()
    mock_invitations_collection.count_documents = AsyncMock()
    
    mock_join_requests_collection.insert_one = AsyncMock()
    mock_join_requests_collection.find_one = AsyncMock()
    mock_join_requests_collection.update_one = AsyncMock()
    mock_join_requests_collection.delete_one = AsyncMock()
    mock_join_requests_collection.count_documents = AsyncMock()
    
    # 配置資料庫的 __getitem__ 方法
    def get_collection(self, name):
        if name == "room_invitations":
            return mock_invitations_collection
        elif name == "join_requests":
            return mock_join_requests_collection
        else:
            return Mock()
    
    mock_db.__getitem__ = get_collection
    
    # 創建服務實例
    service = InvitationService(mock_db, mock_room_repository, mock_user_repository)
    
    return service, mock_room_repository, mock_user_repository, mock_invitations_collection, mock_join_requests_collection


# ==================== Real Service Fixtures (for integration tests) ====================

@pytest.fixture
async def message_service(db_manager: MongoDBTestManager):
    """使用真實資料庫的訊息服務（整合測試用）"""
    message_repo = MessageRepository(db_manager.database)
    room_repo = RoomRepository(db_manager.database)
    return MessageService(message_repo, room_repo)