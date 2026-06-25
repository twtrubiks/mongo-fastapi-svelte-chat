"""AI 服務層測試 — 供應商切換、未配置錯誤處理，以及 stream_reply / summarize 行為。

行為測試以 TestModel / FunctionModel override agent，全程不打外部 API。
"""

import pytest
from pydantic_ai.messages import UserPromptPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel

from app.core.exceptions import AppError
from app.services import ai_service
from app.services.ai_service import (
    AIService,
    _build_chat_prompt,
    _get_api_key,
    _get_chat_agent,
    _get_model,
    _get_summary_agent,
)


@pytest.fixture(autouse=True)
def _reset_ai_globals():
    """每個測試前後重置模組級單例，避免供應商切換互相污染。"""
    ai_service._model = None
    ai_service._chat_agent = None
    ai_service._summary_agent = None
    yield
    ai_service._model = None
    ai_service._chat_agent = None
    ai_service._summary_agent = None


class TestGetApiKey:
    """_get_api_key 依供應商回傳對應 key"""

    def test_nvidia_returns_nvidia_key(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "nvidia")
        monkeypatch.setattr(ai_service.settings, "NVIDIA_API_KEY", "nv-key")
        monkeypatch.setattr(ai_service.settings, "GOOGLE_API_KEY", "g-key")
        assert _get_api_key() == "nv-key"

    def test_gemini_returns_google_key(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "gemini")
        monkeypatch.setattr(ai_service.settings, "NVIDIA_API_KEY", "nv-key")
        monkeypatch.setattr(ai_service.settings, "GOOGLE_API_KEY", "g-key")
        assert _get_api_key() == "g-key"


class TestGetModel:
    """_get_model 依 AI_PROVIDER 建立對應供應商的模型（不打 API）"""

    def test_nvidia_builds_openai_model(self, monkeypatch):
        from pydantic_ai.models.openai import OpenAIChatModel

        monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "nvidia")
        monkeypatch.setattr(ai_service.settings, "NVIDIA_API_KEY", "nv-key")
        assert isinstance(_get_model(), OpenAIChatModel)

    def test_gemini_builds_google_model(self, monkeypatch):
        from pydantic_ai.models.google import GoogleModel

        monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "gemini")
        monkeypatch.setattr(ai_service.settings, "GOOGLE_API_KEY", "g-key")
        assert isinstance(_get_model(), GoogleModel)

    def test_model_is_cached(self, monkeypatch):
        """惰性單例：重複呼叫回傳同一實例"""
        monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "nvidia")
        monkeypatch.setattr(ai_service.settings, "NVIDIA_API_KEY", "nv-key")
        assert _get_model() is _get_model()


class TestNotConfigured:
    """未配置當前供應商的 API key 時拋 AppError"""

    async def test_stream_reply_raises_when_no_key(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "gemini")
        monkeypatch.setattr(ai_service.settings, "GOOGLE_API_KEY", None)
        with pytest.raises(AppError, match="尚未配置"):
            async for _ in AIService().stream_reply("你好"):
                pass

    async def test_summarize_raises_when_no_key(self, monkeypatch):
        monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "nvidia")
        monkeypatch.setattr(ai_service.settings, "NVIDIA_API_KEY", None)
        with pytest.raises(AppError, match="尚未配置"):
            await AIService().summarize("alice: hi")


@pytest.fixture
def configured_nvidia(monkeypatch):
    """配置 NVIDIA 假 key 讓 agent 可惰性建立；搭配 agent.override 實際不打 API。"""
    monkeypatch.setattr(ai_service.settings, "AI_PROVIDER", "nvidia")
    monkeypatch.setattr(ai_service.settings, "NVIDIA_API_KEY", "test-key")


class TestStreamReplyBehavior:
    """stream_reply 串流輸出（以 FunctionModel / TestModel override agent，不打 API）。

    註：stream_text(delta=True) 內建 debounce，測試無真實延遲時多個增量會被合併，
    故驗證「拼接後內容正確」而非逐段序列——分段是 pydantic-ai 的串流行為，非 service 契約。
    """

    async def test_streams_full_reply(self, configured_nvidia):
        """FunctionModel 完全控制輸出內容 → service 不增不減地完整串流出來。"""

        async def stream_fn(messages, info):
            yield "你好"
            yield "，"
            yield "世界"

        agent = _get_chat_agent()
        with agent.override(model=FunctionModel(stream_function=stream_fn)):
            deltas = [delta async for delta in AIService().stream_reply("hi")]

        assert deltas  # 至少產出一段
        assert all(isinstance(delta, str) for delta in deltas)
        assert "".join(deltas) == "你好，世界"

    async def test_streams_with_test_model(self, configured_nvidia):
        """與標準 TestModel 整合：custom_output_text 經串流後完整還原。"""
        agent = _get_chat_agent()
        with agent.override(model=TestModel(custom_output_text="這是一段測試回覆")):
            deltas = [delta async for delta in AIService().stream_reply("hi")]

        assert "".join(deltas) == "這是一段測試回覆"

    async def test_history_reaches_agent_prompt(self, configured_nvidia):
        """帶 history 時，含歷史與新問題的組合 prompt 確實送進 pydantic-ai agent。

        用 FunctionModel 攔截 agent 實際收到的 messages，驗證 history 不只是被
        傳進 stream_reply（那由 handler 測涵蓋），而是真的進到送往模型的 prompt。
        """
        captured: dict[str, str] = {}

        async def stream_fn(messages, info):
            prompts = [
                part.content
                for m in messages
                for part in m.parts
                if isinstance(part, UserPromptPart)
            ]
            captured["prompt"] = "\n".join(str(p) for p in prompts)
            yield "好的"

        agent = _get_chat_agent()
        history = "Bob: 什麼是 Docker?\nAI 助理: 容器化技術"
        with agent.override(model=FunctionModel(stream_function=stream_fn)):
            deltas = [
                delta
                async for delta in AIService().stream_reply(
                    "那它跟 VM 差在哪?", history
                )
            ]

        assert "".join(deltas) == "好的"
        # 歷史與新問題都進到送往 agent 的 prompt
        assert "什麼是 Docker?" in captured["prompt"]
        assert "那它跟 VM 差在哪?" in captured["prompt"]


class TestSummarizeBehavior:
    """summarize one-shot 輸出（以 TestModel override agent，不打 API）"""

    async def test_returns_model_output(self, configured_nvidia):
        """summarize 應回傳 agent 的最終輸出文字。"""
        agent = _get_summary_agent()
        with agent.override(model=TestModel(custom_output_text="• 重點一\n• 重點二")):
            result = await AIService().summarize("alice: 你好\nbob: 嗨")

        assert result == "• 重點一\n• 重點二"


class TestBuildChatPrompt:
    """_build_chat_prompt 純函數：對話歷史併入問題（不打 API）"""

    def test_no_history_returns_question(self):
        """無歷史（None 或空字串）時原樣回傳問題"""
        assert _build_chat_prompt("你好", None) == "你好"
        assert _build_chat_prompt("你好", "") == "你好"

    def test_with_history_embeds_both_in_order(self):
        """有歷史時，歷史與當前問題都併入，且問題接在歷史之後（接續脈絡）"""
        history = "Bob: 什麼是 Docker?\nAI 助理: 容器化技術"
        prompt = _build_chat_prompt("那它跟 VM 差在哪?", history)
        assert history in prompt
        assert "那它跟 VM 差在哪?" in prompt
        assert prompt.index(history) < prompt.index("那它跟 VM 差在哪?")
