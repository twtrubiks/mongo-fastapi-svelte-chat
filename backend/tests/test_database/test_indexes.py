"""MongoDB 索引建立測試

ensure_indexes 只在 app lifespan 執行，一般測試使用的資料庫並沒有這些索引。
這裡在獨立的資料庫上實際建立索引：比對完整索引規格，並透過各 repository
自己的 collection 驗證唯一性約束——確保索引建在 repository 實際讀寫的
collection 與欄位上。
"""

import pytest
from bson import ObjectId
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError

from app.database.indexes import ensure_indexes
from app.repositories.message_repository import MessageRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.room_repository import RoomRepository
from app.repositories.user_repository import UserRepository
from tests.test_config import TestConfig

INDEX_DB_NAME = f"{TestConfig.TEST_DATABASE_NAME}_indexes"

STRING_ONLY = {"$type": "string"}

# collection → {索引鍵: (unique, partialFilterExpression)}
EXPECTED_INDEXES = {
    "users": {
        (("username", 1),): (True, None),
        (("email", 1),): (True, None),
    },
    "messages": {
        (("room_id", 1), ("created_at", -1)): (False, None),
        (("room_id", 1), ("seq", -1)): (False, None),
        (("room_id", 1), ("client_id", 1)): (True, {"client_id": STRING_ONLY}),
    },
    "rooms": {
        (("name", 1),): (True, None),
        (("invite_code", 1),): (True, {"invite_code": STRING_ONLY}),
        (("members", 1),): (False, None),
        (("is_public", 1), ("created_at", -1)): (False, None),
    },
    "notifications": {
        (("user_id", 1), ("created_at", -1)): (False, None),
    },
}


@pytest.fixture
async def index_db():
    """建立索引後的獨立資料庫（測試前後皆清除）"""
    client = AsyncMongoClient(TestConfig.TEST_MONGODB_URL)
    await client.drop_database(INDEX_DB_NAME)
    db = client[INDEX_DB_NAME]
    await ensure_indexes(db)
    yield db
    await client.drop_database(INDEX_DB_NAME)
    await client.close()


def _index_spec(info: dict) -> dict:
    return {
        tuple((field, int(direction)) for field, direction in index["key"]): (
            index.get("unique", False),
            index.get("partialFilterExpression"),
        )
        for name, index in info.items()
        if name != "_id_"
    }


@pytest.mark.asyncio
@pytest.mark.integration
class TestEnsureIndexes:
    """測試 ensure_indexes 實際建立的索引"""

    async def test_index_specs(self, index_db):
        """各 collection 的索引鍵、唯一性與部分過濾條件完全符合預期"""
        for collection, expected in EXPECTED_INDEXES.items():
            info = await index_db[collection].index_information()
            assert _index_spec(info) == expected, collection

    async def test_idempotent(self, index_db):
        """重複執行不會報錯也不會多建索引"""
        await ensure_indexes(index_db)
        info = await index_db["rooms"].index_information()
        assert len(info) == len(EXPECTED_INDEXES["rooms"]) + 1  # 含 _id_

    async def test_repositories_use_indexed_collections(self, index_db):
        """repository 讀寫的 collection 就是建立索引的 collection"""
        assert UserRepository(index_db).collection.name == "users"
        assert MessageRepository(index_db).collection.name == "messages"
        assert RoomRepository(index_db).collection.name == "rooms"
        assert NotificationRepository(index_db).collection.name == "notifications"

    async def test_user_username_and_email_unique(self, index_db):
        users = UserRepository(index_db).collection
        await users.insert_one({"username": "alice", "email": "alice@example.com"})

        with pytest.raises(DuplicateKeyError):
            await users.insert_one({"username": "alice", "email": "other@example.com"})
        with pytest.raises(DuplicateKeyError):
            await users.insert_one({"username": "bob", "email": "alice@example.com"})

        await users.insert_one({"username": "bob", "email": "bob@example.com"})

    async def test_room_name_unique_and_invite_code_partial(self, index_db):
        rooms = RoomRepository(index_db).collection
        await rooms.insert_one({"name": "general", "invite_code": None})
        # 沒有邀請碼（null / 欄位缺）的房間可以有多間
        await rooms.insert_one({"name": "random", "invite_code": None})
        await rooms.insert_one({"name": "no-field"})

        with pytest.raises(DuplicateKeyError):
            await rooms.insert_one({"name": "general"})

        await rooms.insert_one({"name": "private-a", "invite_code": "code-123"})
        with pytest.raises(DuplicateKeyError):
            await rooms.insert_one({"name": "private-b", "invite_code": "code-123"})

    async def test_message_client_id_unique_per_room(self, index_db):
        messages = MessageRepository(index_db).collection
        room_a, room_b = str(ObjectId()), str(ObjectId())

        await messages.insert_one({"room_id": room_a, "client_id": "c-1"})
        # 同一 client_id 在不同房間不衝突
        await messages.insert_one({"room_id": room_b, "client_id": "c-1"})
        # 沒有 client_id 的訊息不受限
        await messages.insert_one({"room_id": room_a, "client_id": None})
        await messages.insert_one({"room_id": room_a})

        with pytest.raises(DuplicateKeyError):
            await messages.insert_one({"room_id": room_a, "client_id": "c-1"})
