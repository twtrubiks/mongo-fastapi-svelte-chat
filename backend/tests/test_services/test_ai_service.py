"""AI 服務層測試 — 供應商切換（NVIDIA NIM / Gemini）與未配置時的錯誤處理。

只驗證模型建立分派與 API key 選取，全部不打外部 API。
"""

import pytest

from app.core.exceptions import AppError
from app.services import ai_service
from app.services.ai_service import AIService, _get_api_key, _get_model


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
