"""訊息 Repository 測試"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError

from app.models.message import (
    MessageInDB,
    MessageSearchQuery,
    MessageStatus,
    MessageType,
    MessageUpdate,
    ReplyToMessage,
)
from app.repositories.message_repository import MessageRepository


@pytest.mark.unit
class TestMessageRepository:
    """訊息 Repository 整合測試類別"""

    @pytest.mark.asyncio
    async def test_create_message(self, db_manager):
        """測試創建訊息"""
        repo = MessageRepository(db_manager.database)

        # 創建訊息資料
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="測試訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 執行創建
        result = await repo.create(message_data)

        # 驗證結果
        assert result is not None
        assert result.id is not None
        assert result.content == "測試訊息"
        assert result.message_type == MessageType.TEXT
        assert result.status == MessageStatus.SENT
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_by_id(self, db_manager):
        """測試根據 ID 獲取訊息"""
        repo = MessageRepository(db_manager.database)

        # 先創建一個訊息
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="測試訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_message = await repo.create(message_data)
        assert created_message is not None

        # 根據 ID 獲取訊息
        retrieved_message = await repo.get_by_id(created_message.id)

        # 驗證結果
        assert retrieved_message is not None
        assert retrieved_message.id == created_message.id
        assert retrieved_message.content == "測試訊息"
        assert retrieved_message.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db_manager):
        """測試獲取不存在的訊息"""
        repo = MessageRepository(db_manager.database)

        # 嘗試獲取不存在的訊息
        non_existent_id = str(ObjectId())
        result = await repo.get_by_id(non_existent_id)

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_invalid_id(self, db_manager):
        """測試使用無效 ID 獲取訊息"""
        repo = MessageRepository(db_manager.database)

        # 使用無效的 ID
        result = await repo.get_by_id("invalid_id")

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_room_id(self, db_manager):
        """測試根據房間 ID 獲取訊息列表"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())

        # 創建多個訊息
        for i in range(5):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=str(ObjectId()),
                username=f"user{i}",
                content=f"測試訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await repo.create(message_data)

        # 獲取房間訊息
        result = await repo.get_room_messages(room_id)

        # 驗證結果
        assert result is not None
        assert len(result) == 5

        # 驗證訊息內容（不依賴特定順序）
        usernames = [msg.username for msg in result]
        contents = [msg.content for msg in result]

        # 確保所有預期的使用者名稱都存在
        expected_usernames = [f"user{i}" for i in range(5)]
        assert set(usernames) == set(expected_usernames)

        # 確保所有預期的內容都存在
        expected_contents = [f"測試訊息 {i}" for i in range(5)]
        assert set(contents) == set(expected_contents)

    @pytest.mark.asyncio
    async def test_find_by_room_id_with_pagination(self, db_manager):
        """測試帶分頁的房間訊息查詢"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())

        # 創建 10 個訊息
        for i in range(10):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=str(ObjectId()),
                username=f"user{i}",
                content=f"測試訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await repo.create(message_data)

        # 獲取第一頁（每頁 5 條）
        result = await repo.get_room_messages(room_id, skip=0, limit=5)

        # 驗證第一頁結果
        assert len(result) == 5

        # 獲取第二頁
        result2 = await repo.get_room_messages(room_id, skip=5, limit=5)

        # 驗證第二頁結果
        assert len(result2) == 5

    @pytest.mark.asyncio
    async def test_update_message(self, db_manager):
        """測試更新訊息"""
        repo = MessageRepository(db_manager.database)

        # 先創建一個訊息
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="原始內容",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_message = await repo.create(message_data)
        assert created_message is not None

        # 更新訊息
        update_data = MessageUpdate(content="更新後的內容")
        updated_message = await repo.update(created_message.id, update_data)

        # 驗證結果
        assert updated_message is not None
        assert updated_message.id == created_message.id
        assert updated_message.content == "更新後的內容"
        assert updated_message.edited is True
        assert updated_message.edited_at is not None
        assert updated_message.updated_at >= created_message.updated_at

    @pytest.mark.asyncio
    async def test_update_nonexistent_message(self, db_manager):
        """測試更新不存在的訊息"""
        repo = MessageRepository(db_manager.database)

        # 嘗試更新不存在的訊息
        non_existent_id = str(ObjectId())
        update_data = MessageUpdate(content="更新內容")
        result = await repo.update(non_existent_id, update_data)

        # 驗證結果
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_message(self, db_manager):
        """測試刪除訊息（軟刪除）"""
        repo = MessageRepository(db_manager.database)

        # 先創建一個訊息
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="要刪除的訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        created_message = await repo.create(message_data)
        assert created_message is not None

        # 刪除訊息
        result = await repo.delete(created_message.id)

        # 驗證刪除成功
        assert result is True

        # 驗證訊息被軟刪除
        deleted_message = await repo.get_by_id(created_message.id)
        assert deleted_message is not None
        assert deleted_message.status == MessageStatus.DELETED
        assert deleted_message.content == "此訊息已被刪除"

    @pytest.mark.asyncio
    async def test_delete_nonexistent_message(self, db_manager):
        """測試刪除不存在的訊息"""
        repo = MessageRepository(db_manager.database)

        # 嘗試刪除不存在的訊息
        non_existent_id = str(ObjectId())
        result = await repo.delete(non_existent_id)

        # 驗證結果
        assert result is False

    @pytest.mark.asyncio
    async def test_get_with_reply(self, db_manager):
        """測試獲取帶回覆資訊的訊息"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())

        # 創建原始訊息
        original_message_data = MessageInDB(
            room_id=room_id,
            user_id=user_id,
            username="testuser",
            content="原始訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        original_message = await repo.create(original_message_data)
        assert original_message is not None

        # 創建回覆訊息
        reply_message_data = MessageInDB(
            room_id=room_id,
            user_id=user_id,
            username="testuser",
            content="回覆訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            reply_to=original_message.id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        reply_message = await repo.create(reply_message_data)
        assert reply_message is not None

        # 獲取帶回覆資訊的訊息
        message_with_reply = await repo.get_with_reply(reply_message.id)

        # 驗證結果
        assert message_with_reply is not None
        assert message_with_reply.id == reply_message.id
        assert message_with_reply.content == "回覆訊息"
        assert message_with_reply.reply_to == original_message.id

        # 如果有回覆資訊，應該包含原始訊息的部分資訊
        if (
            hasattr(message_with_reply, "reply_to_message")
            and message_with_reply.reply_to_message
        ):
            assert message_with_reply.reply_to_message.content == "原始訊息"

    @pytest.mark.asyncio
    async def test_error_handling(self, db_manager):
        """測試錯誤處理"""
        repo = MessageRepository(db_manager.database)

        # 測試無效的 ObjectId 字串
        result = await repo.get_by_id("invalid_object_id")
        assert result is None

        # 測試空字串 ID
        result = await repo.get_by_id("")
        assert result is None

        # 測試 None ID
        result = await repo.get_by_id(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_search_messages(self, db_manager):
        """測試搜尋訊息功能"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())

        # 創建測試訊息
        test_messages = [
            ("Python 程式設計", MessageType.TEXT),
            ("JavaScript 開發", MessageType.TEXT),
            ("資料庫查詢", MessageType.TEXT),
            ("API 設計", MessageType.SYSTEM),
        ]

        for content, msg_type in test_messages:
            message_data = MessageInDB(
                room_id=room_id,
                user_id=user_id,
                username="testuser",
                content=content,
                message_type=msg_type,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await repo.create(message_data)

        # 測試關鍵字搜尋
        search_query = MessageSearchQuery(keyword="程式", page=1, page_size=10)
        result = await repo.search_messages(room_id, search_query)

        assert result.total == 1
        assert len(result.messages) == 1
        assert "程式設計" in result.messages[0].content

        # 測試類型篩選
        search_query = MessageSearchQuery(
            message_type=MessageType.SYSTEM, page=1, page_size=10
        )
        result = await repo.search_messages(room_id, search_query)

        assert result.total == 1
        assert result.messages[0].message_type == MessageType.SYSTEM

    @pytest.mark.asyncio
    async def test_create_message_with_invalid_reply(self, db_manager):
        """測試創建帶無效回覆的訊息"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        other_room_id = str(ObjectId())
        user_id = str(ObjectId())

        # 創建原始訊息（在不同房間）
        original_message_data = MessageInDB(
            room_id=other_room_id,
            user_id=user_id,
            username="testuser",
            content="其他房間的訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        original_message = await repo.create(original_message_data)
        assert original_message is not None

        # 嘗試在不同房間回覆該訊息
        reply_message_data = MessageInDB(
            room_id=room_id,  # 不同的房間
            user_id=user_id,
            username="testuser",
            content="無效回覆",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            reply_to=original_message.id,  # 回覆其他房間的訊息
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Repository 不負責跨房間回覆驗證（已收斂至 Service 層），訊息應正常建立
        result = await repo.create(reply_message_data)
        assert result is not None


async def _insert_with_created_at(collection, room_id: str, minutes: list[int]):
    """依序插入訊息（_id 遞增），內容為 m0、m1…，created_at 為基準時間 + 各自分鐘數"""
    base = datetime(2026, 1, 1)
    await collection.insert_many(
        [
            {
                "_id": ObjectId(),
                **MessageInDB(
                    room_id=room_id,
                    user_id=str(ObjectId()),
                    username="testuser",
                    content=f"m{i}",
                    created_at=base + timedelta(minutes=minute),
                    updated_at=base + timedelta(minutes=minute),
                ).model_dump(exclude={"id"}),
            }
            for i, minute in enumerate(minutes)
        ]
    )


@pytest.mark.unit
class TestMessageRepositoryContracts:
    """建立狀態、排序（刻意讓 created_at 與 _id 順序不一致）、分頁旗標與批次刪除"""

    @pytest.mark.asyncio
    async def test_create_always_persists_sent_status(self, db_manager):
        repo = MessageRepository(db_manager.database)
        message = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="新訊息",
            status=MessageStatus.DELETED,
        )

        created = await repo.create(message)

        raw = await repo.collection.find_one({"_id": ObjectId(created.id)})
        assert created.status == raw["status"] == MessageStatus.SENT
        assert set(raw) == set(MessageInDB.model_fields) - {"id"} | {"_id"}

    @pytest.mark.asyncio
    async def test_room_messages_ordered_by_created_at(self, db_manager):
        """最新的一頁、由舊到新排列"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        await _insert_with_created_at(repo.collection, room_id, [1, 2, 0])

        messages = await repo.get_room_messages(room_id)
        latest_two = await repo.get_room_messages(room_id, limit=2)

        assert [m.content for m in messages] == ["m2", "m0", "m1"]
        assert [m.content for m in latest_two] == ["m0", "m1"]

    @pytest.mark.asyncio
    async def test_search_newest_first(self, db_manager):
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        await _insert_with_created_at(repo.collection, room_id, [1, 2, 0])

        result = await repo.search_messages(room_id, MessageSearchQuery(keyword="m"))

        assert [m.content for m in result.messages] == ["m1", "m0", "m2"]

    @pytest.mark.asyncio
    async def test_search_pagination_flags(self, db_manager):
        """4 筆、每頁 2 筆：第 1 頁只有下一頁、第 2 頁（恰好最後一頁）只有上一頁"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        await _insert_with_created_at(repo.collection, room_id, [3, 2, 1, 0])

        pages = [
            await repo.search_messages(
                room_id, MessageSearchQuery(page=page, page_size=2)
            )
            for page in (1, 2)
        ]

        assert [
            (p.total, p.has_next, p.has_prev, [m.content for m in p.messages])
            for p in pages
        ] == [
            (4, True, False, ["m0", "m1"]),
            (4, False, True, ["m2", "m3"]),
        ]

    @pytest.mark.asyncio
    async def test_delete_by_room_id_returns_deleted_count(self, db_manager):
        repo = MessageRepository(db_manager.database)
        room_id, other_room_id = str(ObjectId()), str(ObjectId())
        await _insert_with_created_at(repo.collection, room_id, [0, 1, 2])
        await _insert_with_created_at(repo.collection, other_room_id, [0])

        deleted = await repo.delete_by_room_id(room_id)

        assert deleted == 3
        assert await repo.collection.count_documents({"room_id": room_id}) == 0
        assert await repo.collection.count_documents({"room_id": other_room_id}) == 1


@pytest.mark.unit
class TestMessageRepositoryQueries:
    """序號計數器、斷線補發、單邊日期搜尋與引用預覽"""

    @pytest.mark.asyncio
    async def test_next_room_seq_counts_per_room(self, db_manager):
        repo = MessageRepository(db_manager.database)
        room_id, other_room_id = str(ObjectId()), str(ObjectId())

        seqs = [await repo.next_room_seq(room_id) for _ in range(3)]
        other = await repo.next_room_seq(other_room_id)

        assert (seqs, other) == ([1, 2, 3], 1)
        # 計數器文件的位置是上線資料的一部分，改了既有房間的序號會從 1 重來
        counters = await db_manager.database["counters"].find().to_list()
        assert sorted(counters, key=lambda c: c["seq"]) == [
            {"_id": f"room_seq:{other_room_id}", "seq": 1},
            {"_id": f"room_seq:{room_id}", "seq": 3},
        ]

    @pytest.mark.asyncio
    async def test_get_after_seq_skips_deleted(self, db_manager):
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        await _insert_with_created_at(repo.collection, room_id, [0, 1, 2, 3])
        docs = await repo.collection.find({"room_id": room_id}).sort("_id").to_list()
        for seq, doc in enumerate(docs, start=1):
            await repo.collection.update_one(
                {"_id": doc["_id"]}, {"$set": {"seq": seq}}
            )
        await repo.delete(str(docs[2]["_id"]))

        after_first = await repo.get_after_seq(room_id, 1)

        assert [(m.seq, m.content) for m in after_first] == [(2, "m1"), (4, "m3")]
        assert await repo.count_after_seq(room_id, 1) == 2

    @pytest.mark.parametrize(
        ("bounds", "expected"),
        [
            ({"start_date": datetime(2026, 1, 1, 0, 1)}, ["m2", "m1"]),
            ({"end_date": datetime(2026, 1, 1, 0, 1)}, ["m1", "m0"]),
            (
                {
                    "start_date": datetime(2026, 1, 1, 0, 1),
                    "end_date": datetime(2026, 1, 1, 0, 1),
                },
                ["m1"],
            ),
        ],
        ids=["start-only", "end-only", "both"],
    )
    @pytest.mark.asyncio
    async def test_search_by_date_range(self, db_manager, bounds, expected):
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        await _insert_with_created_at(repo.collection, room_id, [0, 1, 2])

        result = await repo.search_messages(room_id, MessageSearchQuery(**bounds))

        assert [m.content for m in result.messages] == expected

    @pytest.mark.asyncio
    async def test_get_reply_previews(self, db_manager):
        """去重、略過無效與不存在的 id，一次撈回所有被回覆訊息"""
        repo = MessageRepository(db_manager.database)
        room_id = str(ObjectId())
        await _insert_with_created_at(repo.collection, room_id, [0, 1, 2])
        docs = await repo.collection.find({"room_id": room_id}).sort("_id").to_list()
        first, second = str(docs[0]["_id"]), str(docs[1]["_id"])

        previews = await repo.get_reply_previews(
            [first, second, first, "", "not-an-id", str(ObjectId())]
        )

        assert previews == {
            message_id: ReplyToMessage(
                id=message_id,
                content=doc["content"],
                username="testuser",
                created_at=doc["created_at"],
            )
            for message_id, doc in ((first, docs[0]), (second, docs[1]))
        }

    @pytest.mark.parametrize(
        "reply_ids", [[], ["", "not-an-id"]], ids=["empty", "all-invalid"]
    )
    @pytest.mark.asyncio
    async def test_get_reply_previews_without_valid_ids(self, db_manager, reply_ids):
        repo = MessageRepository(db_manager.database)

        assert await repo.get_reply_previews(reply_ids) == {}


@pytest.mark.unit
class TestMessageRepositoryErrorPropagation:
    """驗證 DB 異常正確傳播而非被吞掉"""

    @pytest.mark.asyncio
    async def test_find_propagates_db_error(self, db_manager):
        """測試查詢時 DB 異常正確傳播"""
        repo = MessageRepository(db_manager.database)
        with patch.object(
            repo.collection, "find_one", side_effect=PyMongoError("connection lost")
        ):
            with pytest.raises(PyMongoError):
                await repo.get_by_id(str(ObjectId()))

    @pytest.mark.asyncio
    async def test_insert_propagates_db_error(self, db_manager):
        """測試寫入時 DB 異常正確傳播"""
        repo = MessageRepository(db_manager.database)
        with patch.object(
            repo.collection, "insert_one", side_effect=PyMongoError("disk full")
        ):
            with pytest.raises(PyMongoError):
                message_data = MessageInDB(
                    room_id=str(ObjectId()),
                    user_id=str(ObjectId()),
                    username="testuser",
                    content="test message",
                    message_type=MessageType.TEXT,
                    status=MessageStatus.SENT,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                await repo.create(message_data)

    @pytest.mark.asyncio
    async def test_count_propagates_db_error(self, db_manager):
        """測試 count 時 DB 異常正確傳播（之前會回傳 0 假裝沒資料）"""
        repo = MessageRepository(db_manager.database)
        with patch.object(
            repo.collection,
            "count_documents",
            side_effect=PyMongoError("timeout"),
        ):
            with pytest.raises(PyMongoError):
                search_query = MessageSearchQuery(keyword="test")
                await repo.search_messages(str(ObjectId()), search_query)
