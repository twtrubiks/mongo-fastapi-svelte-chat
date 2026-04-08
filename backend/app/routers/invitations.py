"""邀請和加入申請相關的 API 端點"""

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_active_user
from app.core.fastapi_integration import InvitationServiceDep
from app.models.enums import JoinRequestStatus
from app.models.invitation import (
    InvitationCreate,
    InvitationResponse,
    InvitationValidateRequest,
    JoinRequestCreate,
    JoinRequestResponse,
    JoinRequestReview,
)
from app.services.invitation_service import InvitationService

router = APIRouter(prefix="/invitations", tags=["邀請和申請"])

# 邀請相關 API


@router.post("/rooms/{room_id}/invitations", response_model=InvitationResponse)
async def create_room_invitation(
    room_id: str,
    invitation_data: InvitationCreate,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    創建房間邀請鏈接

    Args:
        room_id: 房間 ID
        invitation_data: 邀請設定
        current_user: 當前使用者
        invitation_service: 邀請服務實例

    Returns:
        InvitationResponse: 創建的邀請資訊
    """
    # 確保房間 ID 一致
    invitation_data.room_id = room_id
    user_id = current_user["_id"]

    invitation = await invitation_service.create_invitation(
        user_id=user_id, invitation_data=invitation_data
    )

    return invitation


@router.get("/rooms/{room_id}/invitations", response_model=list[InvitationResponse])
async def get_room_invitations(
    room_id: str,
    active_only: bool = Query(True, description="是否只返回有效的邀請"),
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    獲取房間的邀請列表

    Args:
        room_id: 房間 ID
        active_only: 是否只返回有效的邀請
        current_user: 當前使用者
        invitation_service: 邀請服務實例

    Returns:
        List[InvitationResponse]: 邀請列表
    """
    user_id = current_user["_id"]
    invitations = await invitation_service.get_room_invitations(
        room_id=room_id, user_id=user_id, active_only=active_only
    )

    return invitations


@router.post("/validate")
async def validate_invitation(
    request_data: InvitationValidateRequest,
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    驗證邀請碼是否有效

    Args:
        request_data: 驗證邀請碼請求
        invitation_service: 邀請服務實例

    Returns:
        dict: 驗證結果和房間資訊
    """
    invitation = await invitation_service.validate_invitation(request_data.invite_code)

    return {
        "valid": True,
        "room_id": invitation.room_id,
        "room_name": invitation.room_name,
        "inviter_name": invitation.inviter_name,
    }


@router.delete("/{invite_code}")
async def revoke_invitation(
    invite_code: str,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    撤銷邀請

    Args:
        invite_code: 邀請碼
        current_user: 當前使用者
        invitation_service: 邀請服務實例

    Returns:
        dict: 操作結果
    """
    user_id = current_user["_id"]
    await invitation_service.revoke_invitation(invite_code, user_id)
    return {"message": "邀請已撤銷"}


# 加入申請相關 API


@router.post("/rooms/{room_id}/join-requests", response_model=JoinRequestResponse)
async def create_join_request(
    room_id: str,
    request_data: JoinRequestCreate,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    提交加入房間申請

    Args:
        room_id: 房間 ID
        request_data: 申請資料
        current_user: 當前使用者
        invitation_service: 邀請服務實例

    Returns:
        JoinRequestResponse: 創建的申請
    """
    # 確保房間 ID 一致
    request_data.room_id = room_id
    user_id = current_user["_id"]

    join_request = await invitation_service.create_join_request(
        user_id=user_id, request_data=request_data
    )

    return join_request


@router.get("/rooms/{room_id}/join-requests", response_model=list[JoinRequestResponse])
async def get_room_join_requests(
    room_id: str,
    status: JoinRequestStatus | None = Query(None, description="篩選狀態"),
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    獲取房間的加入申請列表

    Args:
        room_id: 房間 ID
        status: 篩選狀態
        current_user: 當前使用者
        invitation_service: 邀請服務實例

    Returns:
        List[JoinRequestResponse]: 申請列表
    """
    user_id = current_user["_id"]
    requests = await invitation_service.get_room_join_requests(
        room_id=room_id, user_id=user_id, status=status
    )

    return requests


@router.put("/join-requests/{request_id}/review")
async def review_join_request(
    request_id: str,
    review: JoinRequestReview,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    審核加入申請

    Args:
        request_id: 申請 ID
        review: 審核結果
        current_user: 當前使用者
        invitation_service: 邀請服務實例

    Returns:
        dict: 操作結果
    """
    user_id = current_user["_id"]
    await invitation_service.review_join_request(
        request_id=request_id, user_id=user_id, review=review
    )
    return {"message": f"申請已{review.status.value}"}


@router.get("/my/join-requests", response_model=list[JoinRequestResponse])
async def get_my_join_requests(
    status: JoinRequestStatus | None = Query(None, description="篩選狀態"),
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = InvitationServiceDep,
):
    """
    獲取我的加入申請列表

    Args:
        status: 篩選狀態
        current_user: 當前使用者
        invitation_service: 邀請服務實例

    Returns:
        List[JoinRequestResponse]: 申請列表
    """
    user_id = current_user["_id"]
    requests = await invitation_service.get_user_join_requests(
        user_id=user_id, status=status
    )

    return requests
