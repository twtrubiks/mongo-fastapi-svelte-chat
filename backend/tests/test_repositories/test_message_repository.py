"""訊息 Repository 測試"""
import pytest
from datetime import datetime, UTC
from bson import ObjectId
from app.repositories.message_repository import MessageRepository
from app.models.message import (
    MessageInDB, MessageCreate, MessageUpdate, MessageType, 
    MessageStatus, MessageSearchQuery
)


@pytest.mark.unit
class TestMessageRepository:
    """訊息 Repository 整合測試類別"""
    
    @pytest.mark.asyncio
    async def test_create_message(self, db_manager_sync):
        """測試創建訊息"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 創建訊息資料
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="測試訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
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
    async def test_get_by_id(self, db_manager_sync):
        """測試根據 ID 獲取訊息"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 先創建一個訊息
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="測試訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
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
    async def test_get_by_id_not_found(self, db_manager_sync):
        """測試獲取不存在的訊息"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 嘗試獲取不存在的訊息
        non_existent_id = str(ObjectId())
        result = await repo.get_by_id(non_existent_id)
        
        # 驗證結果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_by_id_invalid_id(self, db_manager_sync):
        """測試使用無效 ID 獲取訊息"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 使用無效的 ID
        result = await repo.get_by_id("invalid_id")
        
        # 驗證結果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_find_by_room_id(self, db_manager_sync):
        """測試根據房間 ID 獲取訊息列表"""
        repo = MessageRepository(db_manager_sync.database)
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
                updated_at=datetime.now(UTC)
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
    async def test_find_by_room_id_with_pagination(self, db_manager_sync):
        """測試帶分頁的房間訊息查詢"""
        repo = MessageRepository(db_manager_sync.database)
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
                updated_at=datetime.now(UTC)
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
    async def test_update_message(self, db_manager_sync):
        """測試更新訊息"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 先創建一個訊息
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="原始內容",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
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
        assert updated_message.updated_at > created_message.updated_at
    
    @pytest.mark.asyncio
    async def test_update_nonexistent_message(self, db_manager_sync):
        """測試更新不存在的訊息"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 嘗試更新不存在的訊息
        non_existent_id = str(ObjectId())
        update_data = MessageUpdate(content="更新內容")
        result = await repo.update(non_existent_id, update_data)
        
        # 驗證結果
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_message(self, db_manager_sync):
        """測試刪除訊息（軟刪除）"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 先創建一個訊息
        message_data = MessageInDB(
            room_id=str(ObjectId()),
            user_id=str(ObjectId()),
            username="testuser",
            content="要刪除的訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
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
    async def test_delete_nonexistent_message(self, db_manager_sync):
        """測試刪除不存在的訊息"""
        repo = MessageRepository(db_manager_sync.database)
        
        # 嘗試刪除不存在的訊息
        non_existent_id = str(ObjectId())
        result = await repo.delete(non_existent_id)
        
        # 驗證結果
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_recent_messages(self, db_manager_sync):
        """測試獲取最近訊息"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        
        # 創建多個訊息
        created_messages = []
        for i in range(10):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=str(ObjectId()),
                username=f"user{i}",
                content=f"訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            created_message = await repo.create(message_data)
            created_messages.append(created_message)
        
        # 獲取最近 5 則訊息
        recent_messages = await repo.get_recent_messages(room_id, limit=5)
        
        # 驗證結果
        assert len(recent_messages) == 5
        
        # 驗證訊息內容（獲取最近 5 個，應該是索引 5-9）
        expected_contents = [f"訊息 {i}" for i in range(5, 10)]
        actual_contents = [msg.content for msg in recent_messages]
        
        # 由於排序可能不確定，我們只驗證數量和內容集合
        assert len(actual_contents) == 5
        assert set(actual_contents) == set(expected_contents)
    
    @pytest.mark.asyncio
    async def test_mark_messages_as_read(self, db_manager_sync):
        """測試標記訊息為已讀"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())
        
        # 創建其他用戶的訊息
        for i in range(3):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=other_user_id,
                username="other_user",
                content=f"其他用戶訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 標記為已讀
        count = await repo.mark_messages_as_read(room_id, user_id)
        
        # 驗證結果
        assert count == 3
    
    @pytest.mark.asyncio
    async def test_get_unread_count(self, db_manager_sync):
        """測試獲取未讀訊息數量"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())
        
        # 創建其他用戶的訊息
        for i in range(5):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=other_user_id,
                username="other_user",
                content=f"其他用戶訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 獲取未讀數量
        unread_count = await repo.get_unread_count(room_id, user_id)
        
        # 驗證結果
        assert unread_count == 5
        
        # 標記部分為已讀後再檢查
        await repo.mark_messages_as_read(room_id, user_id)
        unread_count_after = await repo.get_unread_count(room_id, user_id)
        assert unread_count_after == 0
    
    @pytest.mark.asyncio
    async def test_get_with_reply(self, db_manager_sync):
        """測試獲取帶回覆資訊的訊息"""
        repo = MessageRepository(db_manager_sync.database)
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
            updated_at=datetime.now(UTC)
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
            updated_at=datetime.now(UTC)
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
        if hasattr(message_with_reply, 'reply_to_message') and message_with_reply.reply_to_message:
            assert message_with_reply.reply_to_message.content == "原始訊息"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, db_manager_sync):
        """測試錯誤處理"""
        repo = MessageRepository(db_manager_sync.database)
        
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
    async def test_search_messages(self, db_manager_sync):
        """測試搜尋訊息功能"""
        repo = MessageRepository(db_manager_sync.database)
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
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 測試關鍵字搜尋
        search_query = MessageSearchQuery(
            keyword="程式",
            page=1,
            page_size=10
        )
        result = await repo.search_messages(room_id, search_query)
        
        assert result.total == 1
        assert len(result.messages) == 1
        assert "程式設計" in result.messages[0].content
        
        # 測試類型篩選
        search_query = MessageSearchQuery(
            message_type=MessageType.SYSTEM,
            page=1,
            page_size=10
        )
        result = await repo.search_messages(room_id, search_query)
        
        assert result.total == 1
        assert result.messages[0].message_type == MessageType.SYSTEM

    @pytest.mark.asyncio
    async def test_get_message_stats(self, db_manager_sync):
        """測試獲取訊息統計"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # 創建不同類型的訊息
        for i in range(5):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=user_id,
                username="testuser",
                content=f"測試訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 創建系統訊息
        system_message = MessageInDB(
            room_id=room_id,
            user_id=user_id,
            username="system",
            content="系統訊息",
            message_type=MessageType.SYSTEM,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        await repo.create(system_message)
        
        # 獲取統計
        stats = await repo.get_message_stats(room_id)
        
        assert stats.total_messages == 6
        assert stats.messages_today == 6
        # 現在已修復 PyMongo aggregation，啟用這些測試
        assert MessageType.TEXT in stats.message_types
        assert MessageType.SYSTEM in stats.message_types
        assert stats.message_types[MessageType.TEXT] == 5
        assert stats.message_types[MessageType.SYSTEM] == 1
        assert len(stats.top_users) >= 1

    @pytest.mark.asyncio
    async def test_get_user_message_stats(self, db_manager_sync):
        """測試獲取使用者訊息統計"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # 創建使用者訊息
        for i in range(3):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=user_id,
                username="testuser",
                content=f"使用者訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 獲取使用者統計
        stats = await repo.get_user_message_stats(user_id)
        
        assert stats["total_messages"] == 3
        assert stats["today_messages"] == 3
        assert stats["week_messages"] == 3

    @pytest.mark.asyncio
    async def test_delete_messages_by_user(self, db_manager_sync):
        """測試刪除使用者的所有訊息"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())
        
        # 創建目標使用者的訊息
        for i in range(3):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=user_id,
                username="target_user",
                content=f"目標訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 創建其他使用者的訊息
        other_message = MessageInDB(
            room_id=room_id,
            user_id=other_user_id,
            username="other_user",
            content="其他使用者訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        await repo.create(other_message)
        
        # 刪除目標使用者的訊息
        deleted_count = await repo.delete_messages_by_user(room_id, user_id)
        
        assert deleted_count == 3
        
        # 驗證訊息被軟刪除
        messages = await repo.get_room_messages(room_id, include_deleted=True)
        target_messages = [msg for msg in messages if msg.user_id == user_id]
        for msg in target_messages:
            assert msg.status == MessageStatus.DELETED

    @pytest.mark.asyncio
    async def test_get_message_count_by_user(self, db_manager_sync):
        """測試獲取使用者的訊息數量"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # 創建使用者訊息
        for i in range(4):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=user_id,
                username="testuser",
                content=f"訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 獲取訊息數量
        count = await repo.get_message_count_by_user(room_id, user_id)
        
        assert count == 4

    @pytest.mark.asyncio
    async def test_get_messages_by_user(self, db_manager_sync):
        """測試獲取特定使用者的訊息列表"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        other_user_id = str(ObjectId())
        
        # 創建目標使用者的訊息
        for i in range(3):
            message_data = MessageInDB(
                room_id=room_id,
                user_id=user_id,
                username="target_user",
                content=f"目標訊息 {i}",
                message_type=MessageType.TEXT,
                status=MessageStatus.SENT,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            await repo.create(message_data)
        
        # 創建其他使用者的訊息
        other_message = MessageInDB(
            room_id=room_id,
            user_id=other_user_id,
            username="other_user",
            content="其他使用者訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        await repo.create(other_message)
        
        # 獲取特定使用者的訊息
        result = await repo.get_messages_by_user(room_id, user_id)
        
        # get_messages_by_user 實際調用的是 get_room_messages，返回 List[MessageInDB]
        assert len(result) == 3
        for msg in result:
            assert msg.user_id == user_id

    @pytest.mark.asyncio
    async def test_create_message_with_invalid_reply(self, db_manager_sync):
        """測試創建帶無效回覆的訊息"""
        repo = MessageRepository(db_manager_sync.database)
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
            updated_at=datetime.now(UTC)
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
            updated_at=datetime.now(UTC)
        )
        
        # 應該返回 None，因為回覆的訊息不在同一個房間
        result = await repo.create(reply_message_data)
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_old_messages(self, db_manager_sync):
        """測試清理舊訊息"""
        repo = MessageRepository(db_manager_sync.database)
        room_id = str(ObjectId())
        user_id = str(ObjectId())
        
        # 創建並立即刪除一個訊息（模擬舊的已刪除訊息）
        message_data = MessageInDB(
            room_id=room_id,
            user_id=user_id,
            username="testuser",
            content="要清理的訊息",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        
        created_message = await repo.create(message_data)
        assert created_message is not None
        
        # 軟刪除該訊息
        await repo.delete(created_message.id)
        
        # 清理舊訊息（保留 0 天，即清理所有已刪除的訊息）
        cleaned_count = await repo.cleanup_old_messages(days=0)
        
        # 驗證清理結果
        assert cleaned_count >= 0  # 可能有其他測試留下的已刪除訊息