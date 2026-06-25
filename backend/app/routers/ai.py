"""AI 助理狀態 API 端點"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_active_user
from app.core.bot import BOT_USERNAME
from app.core.fastapi_integration import AIServiceDep
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI"])


class AIStatusResponse(BaseModel):
    """AI 助理狀態回應（供前端在成員列表顯示上線狀態）"""

    enabled: bool
    bot_username: str


@router.get("/status", response_model=AIStatusResponse)
async def get_ai_status(
    current_user: dict = Depends(get_current_active_user),
    ai_service: AIService = AIServiceDep,
) -> AIStatusResponse:
    """回傳 AI 助理是否可用（@bot / summary 功能是否就緒）。

    可用 = 當前供應商（settings.AI_PROVIDER）已配置 API key，
    純設定判斷，不呼叫外部 AI API。
    """
    return AIStatusResponse(
        enabled=ai_service.is_available(),
        bot_username=BOT_USERNAME,
    )
