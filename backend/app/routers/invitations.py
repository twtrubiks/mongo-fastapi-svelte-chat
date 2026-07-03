"""邀請碼驗證 API 端點"""

from fastapi import APIRouter

from app.core.fastapi_integration import RoomServiceDep
from app.models.invitation import InvitationValidateRequest
from app.services.room_service import RoomService

router = APIRouter(prefix="/invitations", tags=["邀請碼"])


@router.post("/validate")
async def validate_invitation(
    request_data: InvitationValidateRequest,
    room_service: RoomService = RoomServiceDep,
):
    """
    驗證邀請碼是否有效

    Args:
        request_data: 驗證邀請碼請求
        room_service: 房間服務實例

    Returns:
        dict: 驗證結果和房間資訊
    """
    result = await room_service.validate_invite_code(request_data.invite_code)

    return {"valid": True, **result}
