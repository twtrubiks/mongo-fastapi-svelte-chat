"""邀請和加入申請相關的 API 端點"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_active_user
from app.core.fastapi_integration import get_invitation_service
from app.models.enums import JoinRequestStatus
from app.models.invitation import (
    InvitationCreate,
    InvitationResponse,
    JoinRequestCreate,
    JoinRequestResponse,
    JoinRequestReview,
)
from app.services.invitation_service import InvitationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/invitations", tags=["邀請和申請"])

# 邀請相關 API


@router.post("/rooms/{room_id}/invitations", response_model=InvitationResponse)
async def create_room_invitation(
    room_id: str,
    invitation_data: InvitationCreate,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = get_invitation_service(),
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
    try:
        # 確保房間 ID 一致
        invitation_data.room_id = room_id
        user_id = current_user["_id"]

        invitation = await invitation_service.create_invitation(
            user_id=user_id, invitation_data=invitation_data
        )

        return invitation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="創建邀請時發生錯誤",
        ) from e


@router.get("/rooms/{room_id}/invitations", response_model=list[InvitationResponse])
async def get_room_invitations(
    room_id: str,
    active_only: bool = Query(True, description="是否只返回有效的邀請"),
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = get_invitation_service(),
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
    try:
        user_id = current_user["_id"]
        invitations = await invitation_service.get_room_invitations(
            room_id=room_id, user_id=user_id, active_only=active_only
        )

        return invitations
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取邀請列表時發生錯誤",
        ) from e


@router.post("/validate")
async def validate_invitation(
    request_data: dict, invitation_service: InvitationService = get_invitation_service()
):
    """
    驗證邀請碼是否有效

    Args:
        request_data: 包含邀請碼的請求資料
        invitation_service: 邀請服務實例

    Returns:
        dict: 驗證結果和房間資訊
    """
    try:
        invite_code = request_data.get("invite_code")
        if not invite_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="缺少邀請碼"
            )

        invitation = await invitation_service.validate_invitation(invite_code)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="邀請碼無效或已過期"
            )

        return {
            "valid": True,
            "room_id": invitation.room_id,
            "room_name": invitation.room_name,
            "inviter_name": invitation.inviter_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        logger.error(f"Invitation validation error: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"驗證邀請碼時發生錯誤: {str(e)}",
        ) from e


@router.delete("/{invite_code}")
async def revoke_invitation(
    invite_code: str,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = get_invitation_service(),
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
    try:
        user_id = current_user["_id"]
        success = await invitation_service.revoke_invitation(invite_code, user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="撤銷邀請失敗"
            )

        return {"message": "邀請已撤銷"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="撤銷邀請時發生錯誤",
        ) from e


# 加入申請相關 API


@router.post("/rooms/{room_id}/join-requests", response_model=JoinRequestResponse)
async def create_join_request(
    room_id: str,
    request_data: JoinRequestCreate,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = get_invitation_service(),
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
    try:
        # 確保房間 ID 一致
        request_data.room_id = room_id
        user_id = current_user["_id"]

        join_request = await invitation_service.create_join_request(
            user_id=user_id, request_data=request_data
        )

        return join_request
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="提交申請時發生錯誤",
        ) from e


@router.get("/rooms/{room_id}/join-requests", response_model=list[JoinRequestResponse])
async def get_room_join_requests(
    room_id: str,
    status: JoinRequestStatus | None = Query(None, description="篩選狀態"),
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = get_invitation_service(),
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
    try:
        user_id = current_user["_id"]
        requests = await invitation_service.get_room_join_requests(
            room_id=room_id, user_id=user_id, status=status
        )

        return requests
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取申請列表時發生錯誤",
        ) from e


@router.put("/join-requests/{request_id}/review")
async def review_join_request(
    request_id: str,
    review: JoinRequestReview,
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = get_invitation_service(),
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
    try:
        user_id = current_user["_id"]
        success = await invitation_service.review_join_request(
            request_id=request_id, user_id=user_id, review=review
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="審核申請失敗"
            )

        return {"message": f"申請已{review.status.value}"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="審核申請時發生錯誤",
        ) from e


@router.get("/my/join-requests", response_model=list[JoinRequestResponse])
async def get_my_join_requests(
    status: JoinRequestStatus | None = Query(None, description="篩選狀態"),
    current_user: dict = Depends(get_current_active_user),
    invitation_service: InvitationService = get_invitation_service(),
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
    try:
        user_id = current_user["_id"]
        requests = await invitation_service.get_user_join_requests(
            user_id=user_id, status=status
        )

        return requests
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取申請列表時發生錯誤",
        ) from e
