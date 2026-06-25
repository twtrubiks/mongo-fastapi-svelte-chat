"""AI 服務層 — 封裝 Pydantic AI agent（供應商可切換：NVIDIA NIM 或 Gemini）

商業邏輯（LLM 呼叫）集中於此，WebSocket handler 只負責觸發與廣播（遵守三層架構）。
所有 agent 共用同一個模型，依 settings.AI_PROVIDER 決定供應商，惰性建立（首次使用時才需要 API key）。
"""

import logging
from collections.abc import AsyncIterator

from httpx import AsyncClient
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from app.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# 生成參數：max_tokens 提高避免長回覆在生成階段被硬截（講到一半就停），
# timeout 同步放寬，預留較長回覆的生成時間，仍防止外部服務無限卡住 handler
BOT_TEMPERATURE = 0.6
BOT_MAX_TOKENS = 1024  # 約對應中文 400~700 字，足夠完整聊天回答
BOT_TIMEOUT_SECONDS = 60.0
BOT_SYSTEM_PROMPT = "你是聊天室助理，回答簡潔友善，使用繁體中文。"
SUMMARY_SYSTEM_PROMPT = (
    "你是聊天室摘要助理。請用繁體中文，以條列式簡潔摘要以下對話的重點，"
    "聚焦討論主題與結論，不要逐句覆述。"
)

# 共用模型與 agent（惰性建立，避免 import 時就要求 API key）
_model: Model | None = None
_chat_agent: Agent | None = None
_summary_agent: Agent | None = None


def _get_api_key() -> str | None:
    """回傳當前供應商的 API key（未配置時為 None）。"""
    if settings.AI_PROVIDER == "gemini":
        return settings.GOOGLE_API_KEY
    return settings.NVIDIA_API_KEY


def _build_gemini_model() -> Model:
    """建立 Gemini（Google 原生 SDK）模型。

    timeout 須透過自訂 httpx client 設定（ModelSettings.timeout 對 Google 不生效）。
    """
    return GoogleModel(
        settings.GEMINI_MODEL,
        provider=GoogleProvider(
            api_key=settings.GOOGLE_API_KEY,
            http_client=AsyncClient(timeout=BOT_TIMEOUT_SECONDS),
        ),
        settings=ModelSettings(
            temperature=BOT_TEMPERATURE,
            max_tokens=BOT_MAX_TOKENS,
        ),
    )


def _build_nvidia_model() -> Model:
    """建立 NVIDIA NIM（OpenAI 相容端點）模型。"""
    return OpenAIChatModel(
        settings.NVIDIA_MODEL,
        provider=OpenAIProvider(
            base_url=settings.NVIDIA_BASE_URL,
            api_key=settings.NVIDIA_API_KEY,
        ),
        settings=ModelSettings(
            temperature=BOT_TEMPERATURE,
            max_tokens=BOT_MAX_TOKENS,
            timeout=BOT_TIMEOUT_SECONDS,
        ),
    )


def _get_model() -> Model:
    """惰性建立共用模型（依 settings.AI_PROVIDER 切換供應商，所有 agent 共用）。"""
    global _model
    if _model is None:
        if settings.AI_PROVIDER == "gemini":
            _model = _build_gemini_model()
        else:
            _model = _build_nvidia_model()
    return _model


def _get_chat_agent() -> Agent:
    """惰性建立 @bot 對話 agent。"""
    global _chat_agent
    if _chat_agent is None:
        _chat_agent = Agent(_get_model(), system_prompt=BOT_SYSTEM_PROMPT)
    return _chat_agent


def _get_summary_agent() -> Agent:
    """惰性建立 /summary 摘要 agent。"""
    global _summary_agent
    if _summary_agent is None:
        _summary_agent = Agent(_get_model(), system_prompt=SUMMARY_SYSTEM_PROMPT)
    return _summary_agent


class AIService:
    """聊天室 AI 助理服務（@bot streaming + /summary 摘要）。"""

    async def stream_reply(self, question: str) -> AsyncIterator[str]:
        """逐段 yield 文字增量；商業邏輯留在 service，handler 只負責廣播。

        Args:
            question: 使用者問題（已去除 @bot 前綴）

        Yields:
            str: 文字增量（delta）

        Raises:
            AppError: 當當前供應商的 API key 未配置時（首次迭代時拋出）
        """
        if not _get_api_key():
            raise AppError(f"AI 助理尚未配置（{settings.AI_PROVIDER} 缺少 API key）")

        agent = _get_chat_agent()
        async with agent.run_stream(question) as result:
            async for delta in result.stream_text(delta=True):
                yield delta

    async def summarize(self, transcript: str) -> str:
        """對近期對話 transcript 產生摘要（one-shot，非 streaming）。

        Args:
            transcript: 「使用者: 內容」逐行組成的對話文字

        Returns:
            str: 摘要內容

        Raises:
            AppError: 當當前供應商的 API key 未配置時
        """
        if not _get_api_key():
            raise AppError(f"AI 助理尚未配置（{settings.AI_PROVIDER} 缺少 API key）")

        agent = _get_summary_agent()
        result = await agent.run(transcript)
        return result.output
