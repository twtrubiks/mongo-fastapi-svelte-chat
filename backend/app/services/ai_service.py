"""AI 服務層 — 封裝 Pydantic AI agent（NVIDIA NIM，OpenAI 相容端點）

商業邏輯（LLM 呼叫）集中於此，WebSocket handler 只負責觸發與廣播（遵守三層架構）。
所有 agent 共用同一個 NVIDIA NIM 模型，惰性建立（首次使用時才需要 API key）。
"""

import logging

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

from app.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

# 生成參數（對齊 nvidia_nemotron_demo.py），timeout 防止外部服務卡住 handler
BOT_TEMPERATURE = 0.6
BOT_MAX_TOKENS = 512
BOT_TIMEOUT_SECONDS = 30.0
BOT_SYSTEM_PROMPT = "你是聊天室助理，回答簡潔友善，使用繁體中文。"

# 共用 agent（惰性建立，避免 import 時就要求 API key）
_chat_agent: Agent | None = None


def _get_chat_agent() -> Agent:
    """惰性建立共用的 chat agent。"""
    global _chat_agent
    if _chat_agent is None:
        model = OpenAIChatModel(
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
        _chat_agent = Agent(model, system_prompt=BOT_SYSTEM_PROMPT)
    return _chat_agent


class AIService:
    """聊天室 AI 助理服務（A0：非 streaming）。"""

    async def reply(self, question: str) -> str:
        """呼叫 LLM 取得完整回覆（非 streaming）。

        Args:
            question: 使用者問題（已去除 @bot 前綴）

        Returns:
            str: bot 回覆內容

        Raises:
            AppError: 當 NVIDIA_API_KEY 未配置時
        """
        if not settings.NVIDIA_API_KEY:
            raise AppError("AI 助理尚未配置（缺少 NVIDIA_API_KEY）")

        agent = _get_chat_agent()
        result = await agent.run(question)
        return result.output
