"""WebSocket Ticket API 端點"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_active_user
from app.utils.ws_ticket import create_ws_ticket

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class WsTicketRequest(BaseModel):
    """WebSocket ticket 請求"""

    room_id: str


class WsTicketResponse(BaseModel):
    """WebSocket ticket 回應"""

    ticket: str


@router.post("/ticket", response_model=WsTicketResponse)
async def create_websocket_ticket(
    request: WsTicketRequest,
    current_user: dict = Depends(get_current_active_user),
) -> WsTicketResponse:
    """
    產生一次性 WebSocket 連線 ticket

    前端透過 BFF 呼叫此端點取得短效 ticket（TTL 30 秒），
    再使用 ticket 連線 WebSocket，避免在 URL 中傳遞 JWT token。
    """
    user_id = current_user["_id"]
    ticket = await create_ws_ticket(user_id, request.room_id)
    return WsTicketResponse(ticket=ticket)
