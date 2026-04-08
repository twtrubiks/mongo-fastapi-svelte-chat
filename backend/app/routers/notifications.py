from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_active_user
from app.core.fastapi_integration import NotificationServiceDep
from app.models.notification import (
    NotificationListResponse,
    NotificationStats,
    NotificationStatus,
    NotificationType,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    user: dict = Depends(get_current_active_user),
    skip: int = Query(0, ge=0, description="跳過筆數"),
    limit: int = Query(20, ge=1, le=100, description="每頁數量"),
    status: NotificationStatus | None = Query(None, description="過濾狀態"),
    type: NotificationType | None = Query(None, description="過濾類型"),
    notification_service: NotificationService = NotificationServiceDep,
):
    """獲取用戶的通知列表"""
    # 獲取通知列表
    notification_list_response = await notification_service.get_user_notifications(
        user_id=user["_id"],
        status=status,
        notification_type=type,
        skip=skip,
        limit=limit,
    )

    return notification_list_response


@router.get("/unread", response_model=NotificationListResponse)
async def get_unread_notifications(
    user: dict = Depends(get_current_active_user),
    limit: int = Query(50, ge=1, le=100, description="最大數量"),
    notification_service: NotificationService = NotificationServiceDep,
):
    """獲取未讀通知"""
    notification_list_response = await notification_service.get_user_notifications(
        user_id=user["_id"],
        status=NotificationStatus.UNREAD,
        skip=0,
        limit=limit,
    )

    return notification_list_response


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    user: dict = Depends(get_current_active_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """獲取通知統計信息"""
    stats = await notification_service.get_notification_stats(user["_id"])
    return stats


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: dict = Depends(get_current_active_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """標記通知為已讀"""
    await notification_service.mark_as_read(
        notification_id=notification_id, user_id=user["_id"]
    )
    return JSONResponse(
        content={"message": "通知已標記為已讀"}, status_code=status.HTTP_200_OK
    )


@router.post("/read-all")
async def mark_all_notifications_read(
    user: dict = Depends(get_current_active_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """標記所有通知為已讀"""
    count = await notification_service.mark_all_as_read(user["_id"])

    return JSONResponse(
        content={"message": f"已標記 {count} 個通知為已讀", "count": count},
        status_code=status.HTTP_200_OK,
    )


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: dict = Depends(get_current_active_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """刪除通知"""
    await notification_service.delete_notification(
        notification_id=notification_id, user_id=user["_id"]
    )
    return JSONResponse(
        content={"message": "通知已刪除"}, status_code=status.HTTP_200_OK
    )


@router.delete("/")
async def clear_all_notifications(
    user: dict = Depends(get_current_active_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """清空所有通知"""
    count = await notification_service.clear_user_notifications(user["_id"])

    return JSONResponse(
        content={"message": f"已清空 {count} 個通知", "count": count},
        status_code=status.HTTP_200_OK,
    )
