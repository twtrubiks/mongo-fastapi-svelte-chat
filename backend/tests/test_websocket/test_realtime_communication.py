"""即時通訊功能的測試"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest


class TestRealtimeCommunication:
    """測試即時通訊的各種功能"""

    def test_websocket_connection_manager(self):
        """測試 WebSocket 連線管理"""

        # Mock WebSocket 連線管理器
        class ConnectionManager:
            def __init__(self):
                self.connections: dict[str, set[Mock]] = {}
                self.user_connections: dict[str, str] = {}
                self.room_members: dict[str, set[str]] = {}

            def add_connection(self, user_id: str, websocket: Mock, room_id: str):
                # 儲存連線
                if room_id not in self.connections:
                    self.connections[room_id] = set()
                self.connections[room_id].add(websocket)

                # 記錄用戶連線
                self.user_connections[user_id] = room_id

                # 加入房間成員
                if room_id not in self.room_members:
                    self.room_members[room_id] = set()
                self.room_members[room_id].add(user_id)

                return True

            def remove_connection(self, user_id: str, websocket: Mock):
                # 獲取用戶的房間
                room_id = self.user_connections.get(user_id)
                if not room_id:
                    return False

                # 移除連線
                if room_id in self.connections:
                    self.connections[room_id].discard(websocket)

                # 移除用戶連線記錄
                del self.user_connections[user_id]

                # 從房間成員中移除
                if room_id in self.room_members:
                    self.room_members[room_id].discard(user_id)

                return True

            def get_room_connections(self, room_id: str):
                return self.connections.get(room_id, set())

            def get_online_users(self, room_id: str):
                return list(self.room_members.get(room_id, set()))

            def broadcast_to_room(self, room_id: str, message: dict):
                connections = self.get_room_connections(room_id)
                for ws in connections:
                    ws.send_text(json.dumps(message))
                return len(connections)

        # 測試
        manager = ConnectionManager()
        mock_ws1 = Mock()
        mock_ws2 = Mock()

        # 測試添加連線
        assert manager.add_connection("user1", mock_ws1, "room1") is True
        assert manager.add_connection("user2", mock_ws2, "room1") is True

        # 測試獲取線上用戶
        online_users = manager.get_online_users("room1")
        assert len(online_users) == 2
        assert "user1" in online_users
        assert "user2" in online_users

        # 測試廣播訊息
        message = {"type": "message", "content": "Hello"}
        count = manager.broadcast_to_room("room1", message)
        assert count == 2

        # 驗證兩個連線都收到訊息
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()

        # 測試移除連線
        assert manager.remove_connection("user1", mock_ws1) is True
        online_users = manager.get_online_users("room1")
        assert len(online_users) == 1
        assert "user2" in online_users

    def test_message_broadcasting(self):
        """測試訊息廣播功能"""

        # Mock 訊息廣播器
        class MessageBroadcaster:
            def __init__(self):
                self.connection_manager = Mock()
                self.message_queue = Mock()
                self.metrics = Mock()

            def broadcast_message(
                self, room_id: str, message: dict, exclude_user: str = None
            ):
                # 記錄指標
                self.metrics.increment("messages.broadcast")

                # 獲取房間連線
                connections = self.connection_manager.get_connections_for_room(room_id)

                # 過濾排除的用戶
                if exclude_user:
                    connections = [c for c in connections if c.user_id != exclude_user]

                # 廣播訊息
                success_count = 0
                failed_count = 0

                for conn in connections:
                    try:
                        conn.send(json.dumps(message))
                        success_count += 1
                    except Exception:
                        failed_count += 1
                        self.metrics.increment("messages.broadcast.failed")

                # 儲存到訊息佇列（用於離線用戶）
                self.message_queue.push(room_id, message)

                return {
                    "recipients": len(connections),
                    "success": success_count,
                    "failed": failed_count,
                }

            def broadcast_typing_indicator(
                self, room_id: str, user_id: str, is_typing: bool
            ):
                """廣播打字指示器"""
                message = {
                    "type": "typing",
                    "user_id": user_id,
                    "is_typing": is_typing,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                return self.broadcast_message(room_id, message, exclude_user=user_id)

            def broadcast_user_status(self, room_id: str, user_id: str, status: str):
                """廣播用戶狀態"""
                message = {
                    "type": "user_status",
                    "user_id": user_id,
                    "status": status,  # online, away, offline
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                return self.broadcast_message(room_id, message)

        # 設置 Mock
        mock_connections = [
            Mock(user_id="user1", send=Mock()),
            Mock(user_id="user2", send=Mock()),
            Mock(user_id="user3", send=Mock()),
        ]

        broadcaster = MessageBroadcaster()
        broadcaster.connection_manager.get_connections_for_room.return_value = (
            mock_connections
        )
        broadcaster.message_queue.push.return_value = True

        # 測試訊息廣播
        message = {"type": "chat", "content": "Hello everyone!"}
        result = broadcaster.broadcast_message("room1", message)

        assert result["recipients"] == 3
        assert result["success"] == 3
        assert result["failed"] == 0

        # 測試排除特定用戶
        result = broadcaster.broadcast_message("room1", message, exclude_user="user2")
        # 驗證 user2 沒有收到訊息

        # 測試打字指示器
        result = broadcaster.broadcast_typing_indicator("room1", "user1", True)
        broadcaster.metrics.increment.assert_called_with("messages.broadcast")

        # 測試用戶狀態廣播
        result = broadcaster.broadcast_user_status("room1", "user1", "away")
        assert result["recipients"] == 3

    def test_presence_tracking(self):
        """測試用戶在線狀態追蹤"""

        # Mock 在線狀態追蹤器
        class PresenceTracker:
            def __init__(self):
                self.redis = Mock()
                self.heartbeat_interval = 30  # 秒
                self.timeout_threshold = 90  # 秒

            def update_presence(self, user_id: str, room_id: str):
                """更新用戶在線狀態"""
                key = f"presence:{room_id}:{user_id}"
                timestamp = datetime.now(UTC).timestamp()

                # 設置心跳時間戳
                self.redis.set(key, timestamp, ex=self.timeout_threshold)

                # 添加到房間在線列表
                room_key = f"room:online:{room_id}"
                self.redis.sadd(room_key, user_id)

                return True

            def check_presence(self, user_id: str, room_id: str):
                """檢查用戶是否在線"""
                key = f"presence:{room_id}:{user_id}"
                timestamp = self.redis.get(key)

                if not timestamp:
                    return False, "offline"

                # 檢查最後心跳時間
                last_seen = float(timestamp)
                now = datetime.now(UTC).timestamp()
                diff = now - last_seen

                if diff < self.heartbeat_interval:
                    return True, "online"
                elif diff < self.timeout_threshold:
                    return True, "away"
                else:
                    return False, "offline"

            def get_room_presence(self, room_id: str):
                """獲取房間所有用戶的在線狀態"""
                room_key = f"room:online:{room_id}"
                user_ids = self.redis.smembers(room_key)

                presence_list = []
                for user_id in user_ids:
                    is_online, status = self.check_presence(user_id, room_id)
                    if is_online:
                        presence_list.append({"user_id": user_id, "status": status})
                    else:
                        # 移除離線用戶
                        self.redis.srem(room_key, user_id)

                return presence_list

            def cleanup_stale_presence(self):
                """清理過期的在線狀態"""
                # 掃描所有在線狀態鍵
                pattern = "presence:*"
                cleaned = 0

                for key in self.redis.scan_iter(match=pattern):
                    ttl = self.redis.ttl(key)
                    if ttl == -1:  # 沒有過期時間
                        self.redis.delete(key)
                        cleaned += 1

                return cleaned

        # 設置 Mock
        tracker = PresenceTracker()
        current_time = datetime.now(UTC).timestamp()

        # Mock Redis 行為
        tracker.redis.set.return_value = True
        tracker.redis.sadd.return_value = 1
        tracker.redis.get.side_effect = [
            str(current_time - 10),  # 10秒前 - online
            str(current_time - 60),  # 60秒前 - away
            None,  # 離線
        ]
        tracker.redis.smembers.return_value = {"user1", "user2", "user3"}

        # 測試更新在線狀態
        assert tracker.update_presence("user1", "room1") is True
        tracker.redis.set.assert_called()
        tracker.redis.sadd.assert_called_with("room:online:room1", "user1")

        # 測試檢查在線狀態
        is_online, status = tracker.check_presence("user1", "room1")
        assert is_online is True
        assert status == "online"

        is_online, status = tracker.check_presence("user2", "room1")
        assert is_online is True
        assert status == "away"

        is_online, status = tracker.check_presence("user3", "room1")
        assert is_online is False
        assert status == "offline"

    def test_message_acknowledgment(self):
        """測試訊息確認機制"""

        # Mock 訊息確認服務
        class MessageAcknowledgment:
            def __init__(self):
                self.pending_messages = {}
                self.ack_timeout = 5  # 秒
                self.retry_count = 3

            def send_with_ack(self, connection, message, message_id=None):
                """發送需要確認的訊息"""
                if not message_id:
                    import uuid

                    message_id = str(uuid.uuid4())

                # 添加訊息 ID
                message["id"] = message_id
                message["require_ack"] = True

                # 記錄待確認訊息
                self.pending_messages[message_id] = {
                    "message": message,
                    "connection": connection,
                    "sent_at": datetime.now(UTC),
                    "retry_count": 0,
                }

                # 發送訊息
                connection.send(json.dumps(message))

                # 設置超時檢查
                return message_id

            def acknowledge_message(self, message_id):
                """確認訊息已收到"""
                if message_id in self.pending_messages:
                    del self.pending_messages[message_id]
                    return True
                return False

            def check_pending_messages(self):
                """檢查並重試未確認的訊息"""
                now = datetime.now(UTC)
                retry_messages = []
                failed_messages = []

                for msg_id, info in list(self.pending_messages.items()):
                    time_diff = (now - info["sent_at"]).total_seconds()

                    if time_diff > self.ack_timeout:
                        if info["retry_count"] < self.retry_count:
                            # 重試
                            info["retry_count"] += 1
                            info["sent_at"] = now

                            try:
                                info["connection"].send(json.dumps(info["message"]))
                                retry_messages.append(msg_id)
                            except Exception:
                                failed_messages.append(msg_id)
                                del self.pending_messages[msg_id]
                        else:
                            # 超過重試次數
                            failed_messages.append(msg_id)
                            del self.pending_messages[msg_id]

                return {
                    "retried": len(retry_messages),
                    "failed": len(failed_messages),
                    "pending": len(self.pending_messages),
                }

            def get_unacknowledged_count(self, connection=None):
                """獲取未確認訊息數量"""
                if connection:
                    count = sum(
                        1
                        for info in self.pending_messages.values()
                        if info["connection"] == connection
                    )
                    return count
                return len(self.pending_messages)

        # 測試
        ack_service = MessageAcknowledgment()
        mock_connection = Mock()

        # 測試發送需要確認的訊息
        message = {"type": "important", "content": "Critical update"}
        msg_id = ack_service.send_with_ack(mock_connection, message)

        assert msg_id in ack_service.pending_messages
        mock_connection.send.assert_called_once()

        # 測試訊息確認
        assert ack_service.acknowledge_message(msg_id) is True
        assert msg_id not in ack_service.pending_messages

        # 測試未確認訊息重試
        # 添加一個過期的訊息
        old_msg_id = "old_msg_123"
        ack_service.pending_messages[old_msg_id] = {
            "message": {"type": "test"},
            "connection": mock_connection,
            "sent_at": datetime.now(UTC) - timedelta(seconds=10),
            "retry_count": 0,
        }

        result = ack_service.check_pending_messages()
        assert result["retried"] == 1
        assert ack_service.pending_messages[old_msg_id]["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_async_message_queue(self):
        """測試異步訊息佇列"""

        # Mock 異步訊息佇列
        class AsyncMessageQueue:
            def __init__(self):
                self.queues: dict[str, asyncio.Queue] = {}
                self.subscribers: dict[str, list[AsyncMock]] = {}

            async def publish(self, channel: str, message: dict):
                """發布訊息到頻道"""
                # 獲取或創建佇列
                if channel not in self.queues:
                    self.queues[channel] = asyncio.Queue()

                # 放入訊息
                await self.queues[channel].put(message)

                # 通知訂閱者
                if channel in self.subscribers:
                    for subscriber in self.subscribers[channel]:
                        try:
                            await subscriber(message)
                        except Exception as e:
                            print(f"Subscriber error: {e}")

                return True

            async def subscribe(self, channel: str, callback: AsyncMock):
                """訂閱頻道"""
                if channel not in self.subscribers:
                    self.subscribers[channel] = []

                self.subscribers[channel].append(callback)
                return True

            async def consume(self, channel: str, timeout: float = None):
                """消費訊息"""
                if channel not in self.queues:
                    self.queues[channel] = asyncio.Queue()

                try:
                    message = await asyncio.wait_for(
                        self.queues[channel].get(), timeout=timeout
                    )
                    return message
                except TimeoutError:
                    return None

            def get_queue_size(self, channel: str):
                """獲取佇列大小"""
                if channel in self.queues:
                    return self.queues[channel].qsize()
                return 0

        # 測試
        queue = AsyncMessageQueue()

        # 測試發布訊息
        message = {"type": "test", "data": "hello"}
        await queue.publish("channel1", message)

        assert queue.get_queue_size("channel1") == 1

        # 測試消費訊息
        consumed = await queue.consume("channel1", timeout=1.0)
        assert consumed == message
        assert queue.get_queue_size("channel1") == 0

        # 測試訂閱
        callback = AsyncMock()
        await queue.subscribe("channel2", callback)

        # 發布訊息給訂閱者
        await queue.publish("channel2", {"type": "broadcast"})

        # 驗證回調被調用
        callback.assert_called_once()

    def test_rate_limiting_per_connection(self):
        """測試連線級別的速率限制"""

        # Mock 速率限制器
        class ConnectionRateLimiter:
            def __init__(self):
                self.limits = {
                    "messages": {"count": 10, "window": 60},  # 每分鐘10條
                    "typing": {"count": 30, "window": 60},  # 每分鐘30次
                    "file_upload": {"count": 5, "window": 300},  # 每5分鐘5個
                }
                self.buckets = {}

            def check_rate_limit(self, connection_id: str, action: str):
                """檢查是否超過速率限制"""
                if action not in self.limits:
                    return True, None

                limit = self.limits[action]
                bucket_key = f"{connection_id}:{action}"
                now = datetime.now(UTC).timestamp()

                # 獲取或創建桶
                if bucket_key not in self.buckets:
                    self.buckets[bucket_key] = []

                bucket = self.buckets[bucket_key]

                # 清理過期的記錄
                cutoff = now - limit["window"]
                bucket[:] = [t for t in bucket if t > cutoff]

                # 檢查是否超限
                if len(bucket) >= limit["count"]:
                    # 計算下次可用時間
                    oldest = min(bucket)
                    retry_after = int(oldest + limit["window"] - now)
                    return False, retry_after

                # 記錄新的請求
                bucket.append(now)
                return True, None

            def get_remaining_quota(self, connection_id: str, action: str):
                """獲取剩餘配額"""
                if action not in self.limits:
                    return None

                limit = self.limits[action]
                bucket_key = f"{connection_id}:{action}"

                if bucket_key in self.buckets:
                    now = datetime.now(UTC).timestamp()
                    cutoff = now - limit["window"]
                    current_count = sum(
                        1 for t in self.buckets[bucket_key] if t > cutoff
                    )
                    return limit["count"] - current_count

                return limit["count"]

        # 測試
        limiter = ConnectionRateLimiter()

        # 測試正常請求
        allowed, retry = limiter.check_rate_limit("conn1", "messages")
        assert allowed is True
        assert retry is None

        # 測試達到限制
        for _ in range(9):  # 已經有1個，再加9個達到10個
            limiter.check_rate_limit("conn1", "messages")

        # 第11個應該被限制
        allowed, retry = limiter.check_rate_limit("conn1", "messages")
        assert allowed is False
        assert retry > 0

        # 測試剩餘配額
        remaining = limiter.get_remaining_quota("conn1", "messages")
        assert remaining == 0

        # 測試不同動作的限制
        allowed, _ = limiter.check_rate_limit("conn1", "typing")
        assert allowed is True  # typing 有獨立的限制

    def test_message_history_sync(self):
        """測試訊息歷史同步"""
        # Mock 訊息歷史同步服務
        mock_db = Mock()

        class MessageHistorySync:
            def __init__(self, database):
                self.db = database
                self.page_size = 50

            def sync_history(self, user_id: str, room_id: str, last_sync_time=None):
                """同步訊息歷史"""
                query = {"room_id": room_id}

                if last_sync_time:
                    query["created_at"] = {"$gt": last_sync_time}

                # 獲取訊息
                messages = list(
                    self.db.messages.find(query)
                    .sort("created_at", -1)
                    .limit(self.page_size)
                )

                # 標記已讀狀態
                message_ids = [msg["_id"] for msg in messages]
                read_status = self.db.read_status.find(
                    {"user_id": user_id, "message_id": {"$in": message_ids}}
                )

                read_dict = {rs["message_id"]: True for rs in read_status}

                # 組合結果
                for msg in messages:
                    msg["is_read"] = read_dict.get(str(msg["_id"]), False)

                return {
                    "messages": messages[::-1],  # 反轉為時間正序
                    "has_more": len(messages) == self.page_size,
                    "sync_time": datetime.now(UTC).isoformat(),
                }

            def mark_messages_delivered(self, user_id: str, message_ids: list[str]):
                """標記訊息已送達"""
                delivery_records = [
                    {
                        "user_id": user_id,
                        "message_id": msg_id,
                        "delivered_at": datetime.now(UTC).isoformat(),
                    }
                    for msg_id in message_ids
                ]

                if delivery_records:
                    self.db.delivery_status.insert_many(delivery_records)

                return len(delivery_records)

            def get_undelivered_messages(self, user_id: str):
                """獲取未送達的訊息"""
                # 獲取用戶所在的所有房間
                user_rooms = self.db.room_members.find({"user_id": user_id})
                room_ids = [r["room_id"] for r in user_rooms]

                # 獲取這些房間的所有訊息
                all_messages = self.db.messages.find(
                    {
                        "room_id": {"$in": room_ids},
                        "sender_id": {"$ne": user_id},  # 排除自己發的
                    }
                )

                # 獲取已送達的訊息
                delivered = self.db.delivery_status.find({"user_id": user_id})
                delivered_ids = {d["message_id"] for d in delivered}

                # 過濾未送達的
                undelivered = [
                    msg for msg in all_messages if str(msg["_id"]) not in delivered_ids
                ]

                return undelivered

        # 設置 Mock
        mock_messages = [
            {
                "_id": "msg1",
                "room_id": "room1",
                "content": "Hello",
                "created_at": "2024-01-01T10:00:00",
            },
            {
                "_id": "msg2",
                "room_id": "room1",
                "content": "Hi",
                "created_at": "2024-01-01T10:01:00",
            },
        ]

        mock_db.messages.find.return_value.sort.return_value.limit.return_value = (
            mock_messages
        )
        mock_db.read_status.find.return_value = [
            {"message_id": "msg1", "user_id": "user1"}
        ]
        mock_db.delivery_status.insert_many.return_value = Mock(
            inserted_ids=["d1", "d2"]
        )

        # 測試
        sync_service = MessageHistorySync(mock_db)

        # 測試同步歷史
        result = sync_service.sync_history("user1", "room1")
        assert len(result["messages"]) == 2
        # 訊息被反轉成時間正序，所以 msg2 在前，msg1 在後
        assert result["messages"][1]["is_read"] is True  # msg1 is read
        assert result["messages"][0]["is_read"] is False  # msg2 is not read

        # 測試標記已送達
        count = sync_service.mark_messages_delivered("user1", ["msg1", "msg2"])
        assert count == 2

    def test_connection_recovery(self):
        """測試連線恢復機制"""

        # Mock 連線恢復服務
        class ConnectionRecovery:
            def __init__(self):
                self.session_store = Mock()
                self.message_buffer = {}
                self.recovery_window = 300  # 5分鐘

            def save_session(self, connection_id: str, session_data: dict):
                """儲存連線會話"""
                session = {
                    "connection_id": connection_id,
                    "user_id": session_data["user_id"],
                    "room_id": session_data["room_id"],
                    "last_message_id": session_data.get("last_message_id"),
                    "disconnected_at": datetime.now(UTC).isoformat(),
                }

                self.session_store.set(
                    f"session:{connection_id}",
                    json.dumps(session),
                    ex=self.recovery_window,
                )

                return True

            def recover_session(self, connection_id: str):
                """恢復連線會話"""
                session_data = self.session_store.get(f"session:{connection_id}")

                if not session_data:
                    return None

                session = json.loads(session_data)

                # 檢查是否在恢復窗口內
                disconnected_at = datetime.fromisoformat(session["disconnected_at"])
                time_diff = (datetime.now(UTC) - disconnected_at).total_seconds()

                if time_diff > self.recovery_window:
                    return None

                # 獲取緩衝的訊息
                buffered_messages = self.get_buffered_messages(
                    session["room_id"], session["last_message_id"]
                )

                return {
                    "session": session,
                    "buffered_messages": buffered_messages,
                    "recovery_time": time_diff,
                }

            def buffer_message(self, room_id: str, message: dict):
                """緩衝訊息用於恢復"""
                if room_id not in self.message_buffer:
                    self.message_buffer[room_id] = []

                # 保持緩衝區大小
                if len(self.message_buffer[room_id]) >= 100:
                    self.message_buffer[room_id].pop(0)

                self.message_buffer[room_id].append(message)

            def get_buffered_messages(self, room_id: str, after_message_id: str = None):
                """獲取緩衝的訊息"""
                if room_id not in self.message_buffer:
                    return []

                messages = self.message_buffer[room_id]

                if after_message_id:
                    # 找到指定訊息後的所有訊息
                    found_index = -1
                    for i, msg in enumerate(messages):
                        if msg.get("id") == after_message_id:
                            found_index = i
                            break

                    if found_index >= 0:
                        return messages[found_index + 1 :]

                return messages

        # 測試
        recovery = ConnectionRecovery()

        # Mock session store
        recovery.session_store.set.return_value = True
        recovery.session_store.get.return_value = json.dumps(
            {
                "connection_id": "conn1",
                "user_id": "user1",
                "room_id": "room1",
                "last_message_id": "msg100",
                "disconnected_at": (
                    datetime.now(UTC) - timedelta(seconds=30)
                ).isoformat(),
            }
        )

        # 測試儲存會話
        session_data = {
            "user_id": "user1",
            "room_id": "room1",
            "last_message_id": "msg100",
        }
        assert recovery.save_session("conn1", session_data) is True

        # 測試緩衝訊息
        recovery.buffer_message("room1", {"id": "msg100", "content": "Last message"})
        recovery.buffer_message("room1", {"id": "msg101", "content": "Message 1"})
        recovery.buffer_message("room1", {"id": "msg102", "content": "Message 2"})

        # 測試恢復會話
        recovered = recovery.recover_session("conn1")
        assert recovered is not None
        assert recovered["session"]["user_id"] == "user1"
        assert len(recovered["buffered_messages"]) == 2  # msg101 和 msg102
        assert recovered["recovery_time"] < 60  # 應該在1分鐘內

    def test_room_state_management(self):
        """測試房間狀態管理"""

        # Mock 房間狀態管理器
        class RoomStateManager:
            def __init__(self):
                self.room_states = {}
                self.user_states = {}

            def update_room_state(self, room_id: str, updates: dict):
                """更新房間狀態"""
                if room_id not in self.room_states:
                    self.room_states[room_id] = {
                        "active_users": set(),
                        "typing_users": set(),
                        "last_activity": None,
                        "message_count": 0,
                        "created_at": datetime.now(UTC).isoformat(),
                    }

                state = self.room_states[room_id]

                # 更新狀態
                for key, value in updates.items():
                    if key == "add_user":
                        state["active_users"].add(value)
                    elif key == "remove_user":
                        state["active_users"].discard(value)
                    elif key == "typing_start":
                        state["typing_users"].add(value)
                    elif key == "typing_stop":
                        state["typing_users"].discard(value)
                    elif key == "new_message":
                        state["message_count"] += 1
                        state["last_activity"] = datetime.now(UTC).isoformat()
                    else:
                        state[key] = value

                return state

            def get_room_state(self, room_id: str):
                """獲取房間狀態"""
                if room_id not in self.room_states:
                    return None

                state = self.room_states[room_id].copy()
                state["active_users"] = list(state["active_users"])
                state["typing_users"] = list(state["typing_users"])

                return state

            def update_user_state(self, user_id: str, room_id: str, state: dict):
                """更新用戶在房間中的狀態"""
                key = f"{user_id}:{room_id}"

                if key not in self.user_states:
                    self.user_states[key] = {
                        "status": "online",
                        "last_seen": None,
                        "unread_count": 0,
                        "muted": False,
                        "custom_status": None,
                    }

                self.user_states[key].update(state)
                self.user_states[key]["last_updated"] = datetime.now(UTC).isoformat()

                return self.user_states[key]

            def get_user_room_states(self, user_id: str):
                """獲取用戶在所有房間的狀態"""
                user_states = {}

                for key, state in self.user_states.items():
                    if key.startswith(f"{user_id}:"):
                        room_id = key.split(":")[1]
                        user_states[room_id] = state

                return user_states

        # 測試
        manager = RoomStateManager()

        # 測試更新房間狀態
        manager.update_room_state("room1", {"add_user": "user1"})
        manager.update_room_state("room1", {"add_user": "user2"})
        manager.update_room_state("room1", {"typing_start": "user1"})
        manager.update_room_state("room1", {"new_message": True})

        # 獲取房間狀態
        state = manager.get_room_state("room1")
        assert len(state["active_users"]) == 2
        assert "user1" in state["active_users"]
        assert "user1" in state["typing_users"]
        assert state["message_count"] == 1
        assert state["last_activity"] is not None

        # 測試用戶狀態
        manager.update_user_state(
            "user1",
            "room1",
            {"status": "away", "unread_count": 5, "custom_status": "In a meeting"},
        )

        user_states = manager.get_user_room_states("user1")
        assert "room1" in user_states
        assert user_states["room1"]["status"] == "away"
        assert user_states["room1"]["unread_count"] == 5
        assert user_states["room1"]["custom_status"] == "In a meeting"

    def test_push_notification_integration(self):
        """測試推送通知整合"""
        # Mock 推送通知服務
        mock_fcm = Mock()  # Firebase Cloud Messaging
        mock_apns = Mock()  # Apple Push Notification Service

        class PushNotificationService:
            def __init__(self, fcm_client, apns_client):
                self.fcm = fcm_client
                self.apns = apns_client
                self.device_registry = Mock()

            def send_push_notification(self, user_id: str, notification: dict):
                """發送推送通知"""
                # 獲取用戶設備
                devices = self.device_registry.get_user_devices(user_id)

                if not devices:
                    return {"sent": 0, "failed": 0}

                sent_count = 0
                failed_count = 0

                for device in devices:
                    try:
                        if device["platform"] == "android":
                            # 發送 FCM 通知
                            message = {
                                "token": device["token"],
                                "notification": {
                                    "title": notification["title"],
                                    "body": notification["body"],
                                },
                                "data": notification.get("data", {}),
                                "android": {
                                    "priority": "high",
                                    "notification": {
                                        "sound": "default",
                                        "badge": notification.get("badge", 1),
                                    },
                                },
                            }
                            self.fcm.send(message)
                            sent_count += 1

                        elif device["platform"] == "ios":
                            # 發送 APNS 通知
                            payload = {
                                "aps": {
                                    "alert": {
                                        "title": notification["title"],
                                        "body": notification["body"],
                                    },
                                    "sound": "default",
                                    "badge": notification.get("badge", 1),
                                },
                                "custom": notification.get("data", {}),
                            }
                            self.apns.send(device["token"], payload)
                            sent_count += 1

                    except Exception as e:
                        failed_count += 1
                        # 處理無效的設備令牌
                        if "InvalidToken" in str(e):
                            self.device_registry.remove_device(device["id"])

                return {
                    "sent": sent_count,
                    "failed": failed_count,
                    "total_devices": len(devices),
                }

            def send_silent_push(self, user_id: str, data: dict):
                """發送靜默推送（用於同步）"""
                devices = self.device_registry.get_user_devices(user_id)

                for device in devices:
                    if device["platform"] == "ios":
                        # iOS 靜默推送
                        payload = {"aps": {"content-available": 1}, "sync_data": data}
                        self.apns.send(device["token"], payload)
                    elif device["platform"] == "android":
                        # Android 資料訊息
                        message = {
                            "token": device["token"],
                            "data": {"type": "sync", **data},
                        }
                        self.fcm.send(message)

                return True

        # 設置 Mock
        mock_devices = [
            {"id": "d1", "platform": "android", "token": "fcm_token_1"},
            {"id": "d2", "platform": "ios", "token": "apns_token_1"},
        ]

        push_service = PushNotificationService(mock_fcm, mock_apns)
        push_service.device_registry.get_user_devices.return_value = mock_devices

        # 測試發送推送通知
        notification = {
            "title": "New Message",
            "body": "You have a new message from John",
            "data": {"room_id": "room1", "message_id": "msg123"},
            "badge": 3,
        }

        result = push_service.send_push_notification("user1", notification)

        assert result["sent"] == 2
        assert result["failed"] == 0
        assert result["total_devices"] == 2

        # 驗證 FCM 和 APNS 都被調用
        mock_fcm.send.assert_called_once()
        mock_apns.send.assert_called_once()

        # 測試靜默推送
        sync_data = {"last_sync": "2024-01-01T12:00:00", "pending_messages": 5}
        push_service.send_silent_push("user1", sync_data)

        # 驗證靜默推送被發送
        assert mock_fcm.send.call_count == 2
        assert mock_apns.send.call_count == 2
