"""訊息相關的 API 端點（重構版）"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_active_user
from app.core.fastapi_integration import MessageServiceDep
from app.models.message import (
    MessageCreate,
    MessageResponse,
    MessageSearchQuery,
    MessageUpdate,
)
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["訊息"])


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message: MessageCreate,
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    創建新訊息

    Args:
        message: 訊息創建資料
        current_user: 當前使用者
        message_service: 訊息服務實例

    Returns:
        MessageResponse: 新創建的訊息資料
    """
    try:
        user_id = current_user["_id"]
        created_message = await message_service.create_message(user_id, message)
        return created_message
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        import traceback

        logger.error(f"Exception in create_message: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="創建訊息時發生錯誤",
        ) from e


@router.get("/room/{room_id}", response_model=list[MessageResponse])
async def get_room_messages(
    room_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    獲取聊天室訊息列表

    Args:
        room_id: 聊天室 ID
        skip: 跳過的訊息數量
        limit: 返回的訊息數量上限
        current_user: 當前使用者
        message_service: 訊息服務實例

    Returns:
        List[MessageResponse]: 訊息列表
    """
    try:
        messages = await message_service.get_room_messages(
            room_id, skip=skip, limit=limit
        )
        return messages
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取訊息列表時發生錯誤",
        ) from e


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    獲取特定訊息資料

    Args:
        message_id: 訊息 ID
        current_user: 當前使用者
        message_service: 訊息服務實例

    Returns:
        MessageResponse: 訊息資料
    """
    try:
        message = await message_service.get_message_by_id(message_id)

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="訊息不存在"
            )

        return message
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取訊息資料時發生錯誤",
        ) from e


@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    message_update: MessageUpdate,
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    更新訊息資料

    Args:
        message_id: 訊息 ID
        message_update: 更新資料
        current_user: 當前使用者
        message_service: 訊息服務實例

    Returns:
        MessageResponse: 更新後的訊息資料
    """
    try:
        current_user_id = current_user["_id"]
        updated_message = await message_service.update_message(
            message_id, current_user_id, message_update
        )

        if not updated_message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="訊息不存在"
            )

        return updated_message
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新訊息時發生錯誤",
        ) from e


@router.delete("/{message_id}")
async def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    刪除訊息

    Args:
        message_id: 訊息 ID
        current_user: 當前使用者
        message_service: 訊息服務實例

    Returns:
        dict: 刪除結果
    """
    try:
        current_user_id = current_user["_id"]
        success = await message_service.delete_message(message_id, current_user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="訊息不存在或無權限刪除"
            )

        return {"message": "訊息刪除成功"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刪除訊息時發生錯誤",
        ) from e


@router.post("/room/{room_id}/search", response_model=list[MessageResponse])
async def search_room_messages(
    room_id: str,
    query: MessageSearchQuery,
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    搜尋聊天室內的訊息

    Args:
        room_id: 聊天室 ID
        query: 搜尋查詢參數
        current_user: 當前使用者
        message_service: 訊息服務實例

    Returns:
        List[MessageResponse]: 符合搜尋條件的訊息列表
    """
    try:
        search_result = await message_service.search_messages(room_id, query)
        return search_result.messages
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"搜尋訊息時發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="搜尋訊息時發生錯誤",
        ) from e
