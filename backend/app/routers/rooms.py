"""聊天室相關的 API 端點（重構版）"""

import logging

from fastapi import APIRouter, Body, Depends, Query, status

from app.auth.dependencies import get_current_active_user, require_room_membership
from app.core.fastapi_integration import MessageServiceDep, RoomServiceDep
from app.models.message import MessageCreate, MessageResponse
from app.models.room import (
    RoomCreate,
    RoomJoinRequest,
    RoomResponse,
    RoomSummary,
    RoomUpdate,
)
from app.services.message_service import MessageService
from app.services.room_service import RoomService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rooms", tags=["聊天室"])


@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room: RoomCreate,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """
    創建新聊天室

    Args:
        room: 聊天室創建資料
        current_user: 當前使用者
        room_service: 房間服務實例

    Returns:
        RoomResponse: 新創建的聊天室資料
    """
    owner_id = current_user["_id"]
    created_room = await room_service.create_room(owner_id, room)
    return created_room


@router.get("/", response_model=list[RoomSummary])
@router.get("", response_model=list[RoomSummary])  # 修復 URL 重定向問題
async def get_rooms(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    exclude_joined: bool = Query(False),
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """獲取聊天室列表"""
    user_id = current_user["_id"]
    rooms = await room_service.get_rooms(
        skip=skip,
        limit=limit,
        search=search,
        user_id=user_id,
        exclude_joined=exclude_joined,
    )
    return rooms


@router.get("/my", response_model=list[RoomSummary])
async def get_my_rooms(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """獲取當前使用者的聊天室列表"""
    user_id = current_user["_id"]
    rooms = await room_service.get_user_rooms(user_id, skip=skip, limit=limit)
    return rooms


@router.get("/{room_id}", response_model=RoomResponse | RoomSummary)
async def get_room(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """獲取特定聊天室資料（成員→完整詳情，非成員 PUBLIC→摘要，PRIVATE→404）"""
    return await room_service.get_room_for_user(room_id, current_user["_id"])


@router.put("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: str,
    room_update: RoomUpdate,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """
    更新聊天室資料

    Args:
        room_id: 聊天室 ID
        room_update: 更新資料
        current_user: 當前使用者
        room_service: 房間服務實例

    Returns:
        RoomResponse: 更新後的聊天室資料
    """
    current_user_id = current_user["_id"]
    return await room_service.update_room(room_id, current_user_id, room_update)


@router.delete("/{room_id}")
async def delete_room(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """
    刪除聊天室

    Args:
        room_id: 聊天室 ID
        current_user: 當前使用者
        room_service: 房間服務實例

    Returns:
        dict: 刪除結果
    """
    current_user_id = current_user["_id"]
    await room_service.delete_room(room_id, current_user_id)
    return {"message": "聊天室刪除成功"}


@router.post("/{room_id}/join")
async def join_room(
    room_id: str,
    join_request: RoomJoinRequest | None = Body(None),
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """
    加入聊天室（支援新的權限系統）

    Args:
        room_id: 聊天室 ID
        join_request: 加入請求（包含密碼或邀請碼）
        current_user: 當前使用者
        room_service: 房間服務實例

    Returns:
        dict: 加入結果
    """
    user_id = current_user["_id"]
    logger.info(
        f"Join room request for {room_id} by user {user_id}, join_request: {join_request}"
    )
    message = await room_service.join_room(room_id, user_id, join_request)
    return {"message": message}


@router.post("/{room_id}/leave")
async def leave_room(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep,
):
    """
    離開聊天室

    Args:
        room_id: 聊天室 ID
        current_user: 當前使用者
        room_service: 房間服務實例

    Returns:
        dict: 離開結果
    """
    user_id = current_user["_id"]
    message = await room_service.leave_room(room_id, user_id)
    return {"message": message}


@router.get("/{room_id}/members")
async def get_room_members(
    room_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _current_user: dict = Depends(require_room_membership),
    room_service: RoomService = RoomServiceDep,
):
    """獲取聊天室成員列表（需成員資格）"""
    members = await room_service.get_room_members(room_id, skip=skip, limit=limit)
    return members


@router.get("/{room_id}/messages", response_model=list[MessageResponse])
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


@router.post(
    "/{room_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_room_message(
    room_id: str,
    message: MessageCreate,
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep,
):
    """
    發送聊天室訊息

    Args:
        room_id: 聊天室 ID
        message: 訊息內容
        current_user: 當前使用者
        message_service: 訊息服務實例

    Returns:
        MessageResponse: 新創建的訊息
    """
    user_id = current_user["_id"]
    # 設置房間 ID
    message.room_id = room_id
    created_message = await message_service.create_message(user_id, message)
    return created_message
