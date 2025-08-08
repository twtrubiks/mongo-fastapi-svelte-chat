from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user
from app.core.fastapi_integration import NotificationServiceDep
from app.models.notification import (
    NotificationListResponse,
    NotificationStats,
    NotificationStatus,
    NotificationType,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="頁碼"),
    limit: int = Query(20, ge=1, le=100, description="每頁數量"),
    status: NotificationStatus | None = Query(None, description="過濾狀態"),
    type: NotificationType | None = Query(None, description="過濾類型"),
    notification_service: NotificationService = NotificationServiceDep,
):
    """獲取用戶的通知列表"""
    try:
        # 計算跳過的項目數
        (page - 1) * limit

        # 獲取通知列表
        notification_list_response = await notification_service.get_user_notifications(
            user_id=user["_id"],
            status=status,
            notification_type=type,
            page=page,
            page_size=limit,
        )

        return notification_list_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取通知列表失敗: {str(e)}",
        ) from e


@router.get("/unread", response_model=NotificationListResponse)
async def get_unread_notifications(
    user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100, description="最大數量"),
    notification_service: NotificationService = NotificationServiceDep,
):
    """獲取未讀通知"""
    try:
        notification_list_response = await notification_service.get_user_notifications(
            user_id=user["_id"],
            status=NotificationStatus.UNREAD,
            page=1,
            page_size=limit,
        )

        return notification_list_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取未讀通知失敗: {str(e)}",
        ) from e


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    user: dict = Depends(get_current_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """獲取通知統計信息"""
    try:
        stats = await notification_service.get_notification_stats(user["_id"])
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取通知統計失敗: {str(e)}",
        ) from e


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: dict = Depends(get_current_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """標記通知為已讀"""
    try:
        success = await notification_service.mark_as_read(
            notification_id=notification_id, user_id=user["_id"]
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在或無權限"
            )

        return JSONResponse(
            content={"message": "通知已標記為已讀"}, status_code=status.HTTP_200_OK
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"標記通知已讀失敗: {str(e)}",
        ) from e


@router.post("/read-all")
async def mark_all_notifications_read(
    user: dict = Depends(get_current_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """標記所有通知為已讀"""
    try:
        count = await notification_service.mark_all_as_read(user["_id"])

        return JSONResponse(
            content={"message": f"已標記 {count} 個通知為已讀", "count": count},
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"標記所有通知已讀失敗: {str(e)}",
        ) from e


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    user: dict = Depends(get_current_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """刪除通知"""
    try:
        success = await notification_service.delete_notification(
            notification_id=notification_id, user_id=user["_id"]
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="通知不存在或無權限"
            )

        return JSONResponse(
            content={"message": "通知已刪除"}, status_code=status.HTTP_200_OK
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刪除通知失敗: {str(e)}",
        ) from e


@router.delete("/")
async def clear_all_notifications(
    user: dict = Depends(get_current_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """清空所有通知"""
    try:
        count = await notification_service.clear_user_notifications(user["_id"])

        return JSONResponse(
            content={"message": f"已清空 {count} 個通知", "count": count},
            status_code=status.HTTP_200_OK,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空通知失敗: {str(e)}",
        ) from e


@router.post("/test")
async def create_test_notification(
    user: dict = Depends(get_current_user),
    notification_service: NotificationService = NotificationServiceDep,
):
    """創建測試通知（開發用）"""
    try:
        notification = await notification_service.create_notification(
            user_id=user["_id"],
            title="測試通知",
            content="這是一個測試通知，用於驗證通知系統功能",
            notification_type=NotificationType.SYSTEM,
            metadata={"test": True},
        )

        return JSONResponse(
            content={"message": "測試通知已創建", "notification_id": notification.id},
            status_code=status.HTTP_201_CREATED,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"創建測試通知失敗: {str(e)}",
        ) from e
