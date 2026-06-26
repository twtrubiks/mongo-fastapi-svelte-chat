"""AI 助理觸發測試（@bot streaming + /summary 摘要）

涵蓋 is_bot_trigger / is_summary_command 觸發判斷，以及 handle_bot_mention /
handle_summary_command 各情境，全部不打外部 API。
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.bot import (
    BOT_HISTORY_MAX_ANSWER_CHARS,
    BOT_HISTORY_MAX_PAIRS,
    build_bot_history,
    is_bot_trigger,
    is_summary_command,
)
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


def _bot_reply_stub():
    """bot 落地後 get_message_by_id 回傳：含 reply_to_message 引用預覽（指回提問者）"""
    msg = _bot_message_stub()
    msg.reply_to = "trigger_msg_1"
    msg.reply_to_message = Mock(
        id="trigger_msg_1", content="@bot 你好", username="user1"
    )
    return msg


async def _async_gen(items):
    """把序列包成 async generator（模擬 stream_reply 逐段 yield）"""
    for item in items:
        yield item


async def _async_gen_partial_then_raise():
    """先 yield 半句再拋錯（模擬 streaming 中途逾時/斷線）"""
    yield "半"
    raise RuntimeError("nvidia down")


def _hist_msg(username, content, user_id="u1", mtype=MessageType.TEXT, created_at=None):
    """組一個 build_bot_history 用的訊息 stub（含 created_at 供時間窗判斷）"""
    return Mock(
        username=username,
        content=content,
        user_id=user_id,
        message_type=mtype,
        created_at=created_at or datetime.now(UTC),
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
            await handle_bot_mention("user1", "room1", "你好", "trigger_msg_1")
            mock_ai.assert_not_called()

    async def test_self_trigger_is_noop(self):
        """觸發者就是 bot 自身 → 防迴圈，不處理"""
        with (
            patch("app.websocket.handlers.get_bot_user_id", return_value="bot123"),
            patch("app.websocket.handlers.create_ai_service") as mock_ai,
        ):
            await handle_bot_mention("bot123", "room1", "你好", "trigger_msg_1")
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
            await handle_bot_mention("user1", "room1", "你好", "trigger_msg_1")

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
            await handle_bot_mention("user1", "room1", "", "trigger_msg_1")

            mock_ai.assert_not_called()
            sent = mock_cm.send_personal_message.call_args.args[2]
            assert "請在 @bot" in sent["message"]

    async def test_happy_path_streams_then_lands(self, allowed_limiter):
        """正常流程：streaming bot_typing 增量 → bot 身分落地（skip_membership_check=True）→ 廣播"""
        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(return_value=_async_gen(["你", "好"]))
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock(return_value=_bot_message_stub())
        mock_msg_service.get_room_messages_for_context = AsyncMock(return_value=[])
        mock_msg_service.get_message_by_id = AsyncMock(return_value=_bot_reply_stub())

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
            await handle_bot_mention("user1", "room1", "你好", "trigger_msg_1")

            # 以去除前綴後的問題開啟 streaming；無歷史往返時 history 為空字串
            mock_ai_service.stream_reply.assert_called_once_with("你好", "")

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
            # reply_to 指回觸發此次回覆的使用者訊息（DB 關聯，不影響畫面）
            assert call.args[1].reply_to == "trigger_msg_1"

            # 廣播最終訊息一次，且 payload 帶 reply_to_message 引用（指回提問者）
            mock_cm.broadcast_message.assert_awaited_once()
            broadcast_payload = mock_cm.broadcast_message.call_args.args[1]
            assert broadcast_payload["reply_to_message"]["username"] == "user1"
            assert broadcast_payload["reply_to_message"]["content"] == "@bot 你好"

    async def test_reply_preview_fetch_failure_still_broadcasts(self, allowed_limiter):
        """訊息已落地、補引用預覽失敗 → 降級用原訊息廣播（不帶引用），不誤報「儲存失敗」"""
        # create_message 回傳如實模擬 MessageResponse：無 reply_to_message 屬性
        # （明確設 None，避免純 Mock 自動生出 child Mock 騙過 getattr 判斷）
        landed = _bot_message_stub()
        landed.reply_to = "trigger_msg_1"
        landed.reply_to_message = None

        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(return_value=_async_gen(["你", "好"]))
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock(return_value=landed)
        mock_msg_service.get_room_messages_for_context = AsyncMock(return_value=[])
        # 補引用版本失敗（剛落地卻查不到／DB 異常）→ 不該擋廣播、不該報儲存失敗
        mock_msg_service.get_message_by_id = AsyncMock(
            side_effect=RuntimeError("db down")
        )

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
            await handle_bot_mention("user1", "room1", "你好", "trigger_msg_1")

            # 訊息已落地、補引用嘗試過但失敗：仍廣播最終訊息一次（不卡住）
            mock_msg_service.create_message.assert_awaited_once()
            mock_msg_service.get_message_by_id.assert_awaited_once()
            mock_cm.broadcast_message.assert_awaited_once()

            # 降級廣播：用原訊息、payload 不帶引用區塊
            broadcast_payload = mock_cm.broadcast_message.call_args.args[1]
            assert "reply_to_message" not in broadcast_payload

            # 不可誤報「儲存失敗」：沒有任何 bot_error 廣播
            error_types = [
                c.args[1].get("type")
                for c in mock_cm.broadcast_to_room.call_args_list
                if c.args[1].get("type") == "bot_error"
            ]
            assert error_types == []

    async def test_streaming_failure_broadcasts_bot_error(self, allowed_limiter):
        """streaming 中途失敗 → 廣播 bot_error 收掉預覽、不落地"""
        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(
            return_value=_async_gen_partial_then_raise()
        )
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock()
        mock_msg_service.get_room_messages_for_context = AsyncMock(return_value=[])

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
            await handle_bot_mention("user1", "room1", "你好", "trigger_msg_1")

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
            await handle_bot_mention("user2", "room1", "另一個問題", "trigger_msg_1")

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
        mock_msg_service.get_room_messages_for_context = AsyncMock(return_value=[])
        mock_msg_service.get_message_by_id = AsyncMock(return_value=_bot_reply_stub())

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
            await handle_bot_mention("user1", "room_lock_test", "你好", "trigger_msg_1")

            assert "room_lock_test" not in _bot_streaming_rooms

    async def test_passes_history_to_stream_reply(self, allowed_limiter):
        """撈到的近期 @bot 往返會組成歷史並傳入 stream_reply（多輪接續）"""
        mock_ai_service = Mock()
        mock_ai_service.stream_reply = Mock(return_value=_async_gen(["VM", "..."]))
        mock_msg_service = Mock()
        mock_msg_service.create_message = AsyncMock(return_value=_bot_message_stub())
        mock_msg_service.get_room_messages_for_context = AsyncMock(
            return_value=[
                _hist_msg("Bob", "@bot 什麼是 Docker?", user_id="u1"),
                _hist_msg("AI 助理", "Docker 是容器化技術", user_id="bot123"),
            ]
        )
        mock_msg_service.get_message_by_id = AsyncMock(return_value=_bot_reply_stub())

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
            await handle_bot_mention(
                "user1", "room1", "那它跟 VM 差在哪?", "trigger_msg_1"
            )

            # 撈到的 @bot 往返被組成歷史傳入 stream_reply 的第二參數
            mock_ai_service.stream_reply.assert_called_once()
            call = mock_ai_service.stream_reply.call_args
            assert call.args[0] == "那它跟 VM 差在哪?"
            history_arg = call.args[1]
            assert "什麼是 Docker?" in history_arg
            assert "Docker 是容器化技術" in history_arg


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
    """組一個 get_room_messages_for_context 回傳的訊息 stub"""
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
        mock_msg_service.get_room_messages_for_context = AsyncMock(return_value=[])

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
        mock_msg_service.get_room_messages_for_context = AsyncMock(
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


class TestBuildBotHistory:
    """build_bot_history 純函數：整房 @bot 往返組裝（不打 API）"""

    def test_pairs_question_and_answer(self):
        """使用者 @bot 提問 + bot 回答 → 配成一組，提問去除 @bot 前綴"""
        messages = [
            _hist_msg("Bob", "@bot 什麼是 Docker?", user_id="u1"),
            _hist_msg("AI 助理", "Docker 是容器化技術", user_id="bot123"),
        ]
        result = build_bot_history(messages, "bot123")
        assert "Bob: 什麼是 Docker?" in result
        assert "AI 助理: Docker 是容器化技術" in result

    def test_skips_chitchat(self):
        """一般閒聊（非 @bot）不入歷史"""
        messages = [
            _hist_msg("Alice", "今天天氣真好", user_id="u2"),
            _hist_msg("Bob", "@bot 什麼是 Docker?", user_id="u1"),
            _hist_msg("AI 助理", "Docker 是容器化技術", user_id="bot123"),
        ]
        result = build_bot_history(messages, "bot123")
        assert "今天天氣真好" not in result
        assert "什麼是 Docker?" in result

    def test_excludes_unanswered_current_question(self):
        """最後一個尚未回答的提問（即當前這次）不入歷史"""
        messages = [
            _hist_msg("Bob", "@bot 什麼是 Docker?", user_id="u1"),
            _hist_msg("AI 助理", "Docker 是容器化技術", user_id="bot123"),
            _hist_msg("Bob", "@bot 那它跟 VM 差在哪?", user_id="u1"),
        ]
        result = build_bot_history(messages, "bot123")
        assert "什麼是 Docker?" in result
        assert "VM 差在哪" not in result

    def test_empty_when_no_answered_pairs(self):
        """只有閒聊或未回答提問 → 回空字串"""
        messages = [
            _hist_msg("Alice", "閒聊", user_id="u2"),
            _hist_msg("Bob", "@bot 只問沒答", user_id="u1"),
        ]
        assert build_bot_history(messages, "bot123") == ""

    def test_window_excludes_old_pairs(self):
        """超過時間窗的往返視為舊對話，不帶入"""
        now = datetime.now(UTC)
        old = now - timedelta(minutes=30)
        messages = [
            _hist_msg("Bob", "@bot 舊問題", user_id="u1", created_at=old),
            _hist_msg("AI 助理", "舊回答", user_id="bot123", created_at=old),
        ]
        assert build_bot_history(messages, "bot123", now=now) == ""

    def test_keeps_only_recent_pairs(self):
        """超過則數上限時只保留最近數組"""
        messages = []
        for i in range(BOT_HISTORY_MAX_PAIRS + 3):
            messages.append(_hist_msg("Bob", f"@bot 問題{i}", user_id="u1"))
            messages.append(_hist_msg("AI 助理", f"回答{i}", user_id="bot123"))
        result = build_bot_history(messages, "bot123")
        assert result.count("AI 助理:") == BOT_HISTORY_MAX_PAIRS
        assert "問題0" not in result  # 最舊的被丟棄
        assert f"問題{BOT_HISTORY_MAX_PAIRS + 2}" in result  # 最新的保留

    def test_truncates_long_answer(self):
        """過長的 bot 歷史回答會被截斷以控制 token"""
        long_answer = "字" * 500
        messages = [
            _hist_msg("Bob", "@bot 問題", user_id="u1"),
            _hist_msg("AI 助理", long_answer, user_id="bot123"),
        ]
        result = build_bot_history(messages, "bot123")
        assert "字" * BOT_HISTORY_MAX_ANSWER_CHARS in result
        assert "字" * (BOT_HISTORY_MAX_ANSWER_CHARS + 1) not in result

    def test_skips_non_text_messages(self):
        """非文字訊息（如圖片）不參與配對"""
        messages = [
            _hist_msg("Bob", "@bot 問題", user_id="u1"),
            _hist_msg("AI 助理", "圖片", user_id="bot123", mtype=MessageType.IMAGE),
        ]
        assert build_bot_history(messages, "bot123") == ""
