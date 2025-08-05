"""聊天室相關的 API 端點（重構版）"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from app.models.room import RoomCreate, RoomResponse, RoomUpdate, RoomJoinRequest
from app.models.message import MessageResponse, MessageCreate
from app.auth.dependencies import get_current_active_user
from app.services.room_service import RoomService
from app.services.message_service import MessageService
from app.core.fastapi_integration import RoomServiceDep, MessageServiceDep
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rooms", tags=["聊天室"])

@router.post("/", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    room: RoomCreate,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
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
    try:
        owner_id = current_user["_id"]
        created_room = await room_service.create_room(owner_id, room)
        return created_room
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="創建聊天室時發生錯誤"
        )

@router.get("/", response_model=List[RoomResponse])
@router.get("", response_model=List[RoomResponse])  # 修復 URL 重定向問題
async def get_rooms(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),  # 調整預設 limit 為 50，與前端保持一致
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
):
    """
    獲取聊天室列表
    
    Args:
        skip: 跳過的聊天室數量
        limit: 返回的聊天室數量上限
        current_user: 當前使用者
        room_service: 房間服務實例
        
    Returns:
        List[RoomResponse]: 聊天室列表
    """
    try:
        user_id = current_user["_id"]
        rooms = await room_service.get_rooms(skip=skip, limit=limit, user_id=user_id)
        return rooms
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取聊天室列表時發生錯誤"
        )

@router.get("/my", response_model=List[RoomResponse])
async def get_my_rooms(
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
):
    """
    獲取當前使用者的聊天室列表
    
    Args:
        current_user: 當前使用者
        room_service: 房間服務實例
        
    Returns:
        List[RoomResponse]: 使用者的聊天室列表
    """
    try:
        user_id = current_user["_id"]
        rooms = await room_service.get_user_rooms(user_id)
        return rooms
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取使用者聊天室列表時發生錯誤"
        )

@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
):
    """
    獲取特定聊天室資料
    
    Args:
        room_id: 聊天室 ID
        current_user: 當前使用者
        room_service: 房間服務實例
        
    Returns:
        RoomResponse: 聊天室資料
    """
    try:
        room = await room_service.get_room_by_id(room_id)
        
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
        
        return room
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取聊天室資料時發生錯誤"
        )

@router.put("/{room_id}", response_model=RoomResponse)
async def update_room(
    room_id: str,
    room_update: RoomUpdate,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
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
    try:
        current_user_id = current_user["_id"]
        updated_room = await room_service.update_room(room_id, current_user_id, room_update)
        
        if not updated_room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
        
        return updated_room
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新聊天室時發生錯誤"
        )

@router.delete("/{room_id}")
async def delete_room(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
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
    try:
        current_user_id = current_user["_id"]
        success = await room_service.delete_room(room_id, current_user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在或無權限刪除"
            )
        
        return {"message": "聊天室刪除成功"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="刪除聊天室時發生錯誤"
        )

@router.post("/{room_id}/join")
async def join_room(
    room_id: str,
    join_request: Optional[RoomJoinRequest] = Body(None),
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
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
    try:
        user_id = current_user["_id"]
        logger.info(f"Join room request for {room_id} by user {user_id}, join_request: {join_request}")
        result = await room_service.join_room(room_id, user_id, join_request)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message", "無法加入聊天室")
            )
        
        return {"message": result.get("message", "成功加入聊天室")}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="加入聊天室時發生錯誤"
        )

@router.post("/{room_id}/leave")
async def leave_room(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
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
    try:
        user_id = current_user["_id"]
        success = await room_service.leave_room(room_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無法離開聊天室"
            )
        
        return {"message": "成功離開聊天室"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="離開聊天室時發生錯誤"
        )

@router.get("/{room_id}/members")
async def get_room_members(
    room_id: str,
    current_user: dict = Depends(get_current_active_user),
    room_service: RoomService = RoomServiceDep
):
    """
    獲取聊天室成員列表
    
    Args:
        room_id: 聊天室 ID
        current_user: 當前使用者
        room_service: 房間服務實例
        
    Returns:
        List[UserResponse]: 成員列表
    """
    try:
        members = await room_service.get_room_members(room_id)
        return members
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取成員列表時發生錯誤"
        )

@router.get("/{room_id}/messages", response_model=List[MessageResponse])
async def get_room_messages(
    room_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep
):
    """
    獲取聊天室訊息列表
    
    Args:
        room_id: 聊天室 ID
        limit: 返回的訊息數量上限
        current_user: 當前使用者
        message_service: 訊息服務實例
        
    Returns:
        List[MessageResponse]: 訊息列表
    """
    try:
        messages = await message_service.get_room_messages(room_id, limit=limit)
        return messages
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取訊息列表時發生錯誤"
        )

@router.post("/{room_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_room_message(
    room_id: str,
    message: MessageCreate,
    current_user: dict = Depends(get_current_active_user),
    message_service: MessageService = MessageServiceDep
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
    try:
        user_id = current_user["_id"]
        # 設置房間 ID
        message.room_id = room_id
        created_message = await message_service.create_message(user_id, message)
        return created_message
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="發送訊息時發生錯誤"
        )