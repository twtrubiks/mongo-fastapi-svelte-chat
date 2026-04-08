"""訊息相關的 API 端點（重構版）"""

from fastapi import APIRouter, Depends, Query, status

from app.auth.dependencies import get_current_active_user, require_room_membership
from app.core.fastapi_integration import MessageServiceDep
from app.models.message import (
    MessageCreate,
    MessageResponse,
    MessageSearchQuery,
    MessageUpdate,
)
from app.services.message_service import MessageService

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
    user_id = current_user["_id"]
    created_message = await message_service.create_message(user_id, message)
    return created_message


@router.get("/room/{room_id}", response_model=list[MessageResponse])
async def get_room_messages(
    room_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _current_user: dict = Depends(require_room_membership),
    message_service: MessageService = MessageServiceDep,
):
    """獲取聊天室訊息列表（需成員資格）"""
    messages = await message_service.get_room_messages(room_id, skip=skip, limit=limit)
    return messages


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    _current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    獲取特定訊息資料

    Args:
        message_id: 訊息 ID
        message_service: 訊息服務實例

    Returns:
        MessageResponse: 訊息資料
    """
    return await message_service.get_message_by_id(message_id)


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
    current_user_id = current_user["_id"]
    return await message_service.update_message(
        message_id, current_user_id, message_update
    )


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
    current_user_id = current_user["_id"]
    await message_service.delete_message(message_id, current_user_id)
    return {"message": "訊息刪除成功"}


@router.post("/room/{room_id}/search", response_model=list[MessageResponse])
async def search_room_messages(
    room_id: str,
    query: MessageSearchQuery,
    _current_user: dict = Depends(require_room_membership),
    message_service: MessageService = MessageServiceDep,
):
    """搜尋聊天室內的訊息（需成員資格）"""
    search_result = await message_service.search_messages(room_id, query)
    return search_result.messages
