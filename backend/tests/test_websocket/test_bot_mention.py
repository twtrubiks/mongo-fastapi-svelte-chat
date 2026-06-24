"""@bot AI 助理觸發（A0 非 streaming）測試

涵蓋 is_bot_trigger 觸發判斷與 handle_bot_mention 各情境，全部不打外部 API。
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.bot import is_bot_trigger
from app.models.message import MessageType
from app.websocket.handlers import handle_bot_mention


class TestIsBotTrigger:
    """is_bot_trigger 觸發判斷"""

    @pytest.mark.parametrize(
        "content,expected",
        [
            ("@bot 你好", "你好"),
            ("@BOT  在嗎", "在嗎"),  # 大小寫不敏感 + 多空白
            ("@bot", ""),  # 只 @bot 沒問題
            ("  @bot   多空白  ", "多空白"),
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

    async def test_happy_path_lands_as_bot(self, allowed_limiter):
        """正常流程：呼叫 AI → bot 身分落地（skip_membership_check=True）→ 廣播、不發通知"""
        mock_ai_service = Mock()
        mock_ai_service.reply = AsyncMock(return_value="這是 bot 回覆")
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
            mock_cm.broadcast_message = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user1", "room1", "你好")

            # 呼叫 AI（去除前綴後的問題）
            mock_ai_service.reply.assert_awaited_once_with("你好")

            # 以 bot 身分落地，且跳過成員檢查
            mock_msg_service.create_message.assert_awaited_once()
            call = mock_msg_service.create_message.call_args
            assert call.args[0] == "bot123"
            assert call.kwargs["skip_membership_check"] is True

            # 廣播一則 bot 訊息，且不回報錯誤
            mock_cm.broadcast_message.assert_awaited_once()
            mock_cm.send_personal_message.assert_not_called()

    async def test_ai_failure_reports_error(self, allowed_limiter):
        """AI 呼叫失敗 → 回報錯誤、不建立訊息"""
        mock_ai_service = Mock()
        mock_ai_service.reply = AsyncMock(side_effect=RuntimeError("nvidia down"))
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
            mock_cm.broadcast_message = AsyncMock()
            mock_cm.send_personal_message = AsyncMock()
            await handle_bot_mention("user1", "room1", "你好")

            mock_msg_service.create_message.assert_not_called()
            mock_cm.broadcast_message.assert_not_called()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert "暫時無法回覆" in sent["message"]
