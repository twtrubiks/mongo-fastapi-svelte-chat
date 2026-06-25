"""AI 助理觸發測試（@bot streaming + /summary 摘要）

涵蓋 is_bot_trigger / is_summary_command 觸發判斷，以及 handle_bot_mention /
handle_summary_command 各情境，全部不打外部 API。
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.bot import is_bot_trigger, is_summary_command
from app.models.message import MessageType
from app.websocket.handlers import handle_bot_mention, handle_summary_command


class TestIsBotTrigger:
    """is_bot_trigger 觸發判斷"""

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("@bot 你好", "你好"),
            ("@BOT  在嗎", "在嗎"),  # 大小寫不敏感 + 多空白
            ("@bot", ""),  # 只 @bot 沒問題
            ("  @bot   多空白  ", "多空白"),
            ("＠bot 你好", "你好"),  # 全形＠（中文輸入法）也觸發
            ("＠ｂｏｔ 在嗎", "在嗎"),  # 全形＠＋全形字母
            ("@bother me", None),  # 不應誤判
            ("你好 @bot", None),  # 非開頭不觸發
            ("hello world", None),
        ],
    )
    def test_is_bot_trigger(self, content, expected):
        assert is_bot_trigger(content) == expected


def _bot_message_stub():
    """組一個 _format_message_payload 可用的 bot 訊息 stub"""
    return Mock(
        id="msg1",
        room_id="room1",
        user_id="bot123",
        content="這是 bot 回覆",
        message_type=MessageType.TEXT,
        status="sent",
        seq=1,
        client_id=None,
        created_at=datetime.now(UTC),
        metadata=None,
        username="AI 助理",
    )


async def _async_gen(items):
    """把序列包成 async generator（模擬 stream_reply 逐段 yield）"""
    for item in items:
        yield item


async def _async_gen_partial_then_raise():
    """先 yield 半句再拋錯（模擬 streaming 中途逾時/斷線）"""
    yield "半"
    raise RuntimeError("nvidia down")


class TestHandleBotMention:
    """handle_bot_mention 各情境"""

    @pytest.fixture
    def allowed_limiter(self):
        """限流通過的 SlidingWindowRateLimiter mock context"""
        limiter = Mock()
        limiter.is_allowed = AsyncMock(return_value=(True, 4, 60))
        return limiter

    async def test_not_seeded_is_noop(self):
        """bot 尚未種子化（get_bot_user_id 回 None）→ 不處理"""
        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value=None),
            patch("app.websocket.handlers.create_ai_service") as mock_ai,
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user1", "room1", "你好")
            mock_ai.assert_not_called()

    async def test_self_trigger_is_noop(self):
        """觸發者就是 bot 自身 → 防迴圈，不處理"""
        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.create_ai_service") as mock_ai,
        ):
            await handle_bot_mention("bot123", "room1", "你好")
            mock_ai.assert_not_called()

    async def test_rate_limited(self):
        """超過限流 → 回提示、不打 API、不建立訊息"""
        limiter = Mock()
        limiter.is_allowed = AsyncMock(return_value=(False, 0, 30))
        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter", return_value=limiter
            ),
            patch("app.websocket.handlers.create_ai_service") as mock_ai,
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user1", "room1", "你好")

            mock_ai.assert_not_called()
            mock_cm.send_personal_message.assert_awaited_once()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert sent["type"] == "error"
            assert "太頻繁" in sent["message"]

    async def test_empty_question_hint(self, allowed_limiter):
        """空問題（只 @bot）→ 給提示、不打 API"""
        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter",
                return_value=allowed_limiter,
            ),
            patch("app.websocket.handlers.create_ai_service") as mock_ai,
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user1", "room1", "")

            mock_ai.assert_not_called()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert "請在 @bot" in sent["message"]

    async def test_happy_path_streams_then_lands(self, allowed_limiter):
        """正常流程：streaming bot_typing 增量 → bot 身分落地（skip_membership_check=True）→ 廣播"""
        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(return_value=_async_gen(["你", "好"]))
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock(return_value=_bot_message_stub())

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter",
                return_value=allowed_limiter,
            ),
            patch(
                "app.websocket.handlers.create_ai_service",
                new=AsyncMock(return_value=mock_ai_service),
            ),
            patch(
                "app.websocket.handlers.create_message_service",
                new=AsyncMock(return_value=mock_msg_service),
            ),
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.broadcast_to_room = AsyncMock()
            mock_cm.broadcast_message = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user1", "room1", "你好")

            # 以去除前綴後的問題開啟 streaming
            mock_ai_service.stream_reply.assert_called_once_with("你好")

            # 階段一：每個 delta 廣播一則 bot_typing
            assert mock_cm.broadcast_to_room.await_count == 2
            first = mock_cm.broadcast_to_room.call_args_list[0].args[1]
            assert first["type"] == "bot_typing"
            assert first["content"] == "你"
            assert first["user"]["id"] == "bot123"

            # 階段二：以 bot 身分落地、跳過成員檢查、內容為累積後的完整回覆
            mock_msg_service.create_message.assert_awaited_once()
            call = mock_msg_service.create_message.call_args
            assert call.args[0] == "bot123"
            assert call.kwargs["skip_membership_check"] is True
            assert call.args[1].content == "你好"

            # 廣播最終訊息一次
            mock_cm.broadcast_message.assert_awaited_once()

    async def test_streaming_failure_broadcasts_bot_error(self, allowed_limiter):
        """streaming 中途失敗 → 廣播 bot_error 收掉預覽、不落地"""
        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(
            return_value=_async_gen_partial_then_raise()
        )
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock()

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter",
                return_value=allowed_limiter,
            ),
            patch(
                "app.websocket.handlers.create_ai_service",
                new=AsyncMock(return_value=mock_ai_service),
            ),
            patch(
                "app.websocket.handlers.create_message_service",
                new=AsyncMock(return_value=mock_msg_service),
            ),
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.broadcast_to_room = AsyncMock()
            mock_cm.broadcast_message = AsyncMock()
            await handle_bot_mention("user1", "room1", "你好")

            # 失敗不落地、不廣播最終訊息
            mock_msg_service.create_message.assert_not_called()
            mock_cm.broadcast_message.assert_not_called()

            # 最後一則廣播為 bot_error（半句預覽 + 收尾錯誤）
            assert mock_cm.broadcast_to_room.await_count >= 1
            last = mock_cm.broadcast_to_room.call_args_list[-1].args[1]
            assert last["type"] == "bot_error"

    async def test_concurrent_same_room_blocked(self, allowed_limiter):
        """同房已有 streaming 進行中 → 第二次 @bot 被擋：回報觸發者、不打 API、不落地"""
        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(return_value=_async_gen(["你", "好"]))
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock()

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter",
                return_value=allowed_limiter,
            ),
            patch(
                "app.websocket.handlers.create_ai_service",
                new=AsyncMock(return_value=mock_ai_service),
            ),
            patch(
                "app.websocket.handlers.create_message_service",
                new=AsyncMock(return_value=mock_msg_service),
            ),
            # 預先把 room1 標記為 streaming 中（模擬另一個進行中的 @bot）
            patch("app.websocket.handlers._bot_streaming_rooms", {"room1"}),
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.broadcast_to_room = AsyncMock()
            mock_cm.broadcast_message = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user2", "room1", "另一個問題")

            # 不打 API、不 streaming、不落地
            mock_ai_service.stream_reply.assert_not_called()
            mock_cm.broadcast_to_room.assert_not_called()
            mock_msg_service.create_message.assert_not_called()
            mock_cm.broadcast_message.assert_not_called()

            # 對觸發者回報「正在回覆中」
            mock_cm.send_personal_message.assert_awaited_once()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert sent["type"] == "error"
            assert "正在回覆中" in sent["message"]

    async def test_lock_released_after_completion(self, allowed_limiter):
        """streaming 完成後釋放並發鎖（finally），房間不會永久卡死"""
        from app.websocket.handlers import _bot_streaming_rooms

        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(return_value=_async_gen(["你", "好"]))
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock(return_value=_bot_message_stub())

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter",
                return_value=allowed_limiter,
            ),
            patch(
                "app.websocket.handlers.create_ai_service",
                new=AsyncMock(return_value=mock_ai_service),
            ),
            patch(
                "app.websocket.handlers.create_message_service",
                new=AsyncMock(return_value=mock_msg_service),
            ),
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.broadcast_to_room = AsyncMock()
            mock_cm.broadcast_message = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user1", "room_lock_test", "你好")

            assert "room_lock_test" not in _bot_streaming_rooms


class TestIsSummaryCommand:
    """is_summary_command 指令判斷"""

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("/summary", True),
            ("  /SUMMARY  ", True),  # 大小寫不敏感 + 前後空白
            ("／summary", True),  # 全形／（中文輸入法）也觸發
            ("／ＳＵＭＭＡＲＹ", True),  # 全形斜線＋全形字母
            ("/summarytext", False),  # 完整比對，不前綴誤判
            ("/summary 最近", False),  # 不接受參數（完整比對）
            ("@bot hi", False),
            ("hello", False),
        ],
    )
    def test_is_summary_command(self, content, expected):
        assert is_summary_command(content) is expected


def _room_msg(username, content, user_id="u1", mtype=MessageType.TEXT):
    """組一個 get_room_messages 回傳的訊息 stub"""
    return Mock(username=username, content=content, user_id=user_id, message_type=mtype)


class TestHandleSummaryCommand:
    """handle_summary_command 各情境"""

    @pytest.fixture
    def allowed_limiter(self):
        limiter = Mock()
        limiter.is_allowed = AsyncMock(return_value=(True, 4, 60))
        return limiter

    async def test_not_seeded_reports_error(self):
        """bot 尚未種子化 → 回報觸發者、不撈訊息"""
        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value=None),
            patch("app.websocket.handlers.create_message_service") as mock_msvc,
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.send_personal_message = AsyncMock()
            await handle_summary_command("user1", "room1")
            mock_msvc.assert_not_called()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert "尚未就緒" in sent["message"]

    async def test_rate_limited(self):
        """超過限流 → 回提示、不撈訊息、不打 API"""
        limiter = Mock()
        limiter.is_allowed = AsyncMock(return_value=(False, 0, 30))
        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter", return_value=limiter
            ),
            patch("app.websocket.handlers.create_ai_service") as mock_ai,
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.send_personal_message = AsyncMock()
            await handle_summary_command("user1", "room1")
            mock_ai.assert_not_called()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert "太頻繁" in sent["message"]

    async def test_no_messages_reports_error(self, allowed_limiter):
        """沒有可摘要的訊息 → 回提示、不打 API"""
        mock_msg_service = Mock()
        mock_msg_service.get_room_messages = AsyncMock(return_value=[])

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter",
                return_value=allowed_limiter,
            ),
            patch(
                "app.websocket.handlers.create_message_service",
                new=AsyncMock(return_value=mock_msg_service),
            ),
            patch("app.websocket.handlers.create_ai_service") as mock_ai,
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.send_personal_message = AsyncMock()
            await handle_summary_command("user1", "room1")
            mock_ai.assert_not_called()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert "沒有可摘要" in sent["message"]

    async def test_happy_path_lands_summary(self, allowed_limiter):
        """正常流程：撈訊息 → 摘要（排除 bot 自己）→ bot 身分落地廣播"""
        mock_msg_service = Mock()
        mock_msg_service.get_room_messages = AsyncMock(
            return_value=[
                _room_msg("alice", "今天部署成功", user_id="u1"),
                _room_msg("bot", "（舊的 bot 訊息）", user_id="bot123"),
                _room_msg("bob", "太好了", user_id="u2"),
            ]
        )
        mock_msg_service.create_message = AsyncMock(return_value=_bot_message_stub())
        mock_ai_service = Mock()
        mock_ai_service.summarize = AsyncMock(return_value="- 部署成功\n- 大家滿意")

        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.get_redis", new=AsyncMock()),
            patch(
                "app.websocket.handlers.SlidingWindowRateLimiter",
                return_value=allowed_limiter,
            ),
            patch(
                "app.websocket.handlers.create_message_service",
                new=AsyncMock(return_value=mock_msg_service),
            ),
            patch(
                "app.websocket.handlers.create_ai_service",
                new=AsyncMock(return_value=mock_ai_service),
            ),
            patch("app.websocket.handlers.connection_manager") as mock_cm,
        ):
            mock_cm.broadcast_message = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            await handle_summary_command("user1", "room1")

            # transcript 排除 bot 自己的訊息，依時間順序組成
            mock_ai_service.summarize.assert_awaited_once_with(
                "alice: 今天部署成功\nbob: 太好了"
            )

            # 以 bot 身分落地、跳過成員檢查、內容含摘要標題
            mock_msg_service.create_message.assert_awaited_once()
            call = mock_msg_service.create_message.call_args
            assert call.args[0] == "bot123"
            assert call.kwargs["skip_membership_check"] is True
            assert call.args[1].content.startswith("📋 對話摘要")

            mock_cm.broadcast_message.assert_awaited_once()
            mock_cm.send_personal_message.assert_not_called()
