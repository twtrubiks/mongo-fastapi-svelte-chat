"""WebSocket 路由"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
from app.websocket.handlers import handle_websocket_connection
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str = Path(..., description="房間 ID")):
    """
    WebSocket 端點
    
    Args:
        websocket: WebSocket 連線物件
        room_id: 房間 ID
    
    連線 URL 格式: ws://localhost:8000/ws/{room_id}?token={jwt_token}
    """
    logger.info(f"WebSocket connection attempt for room {room_id}")
    
    try:
        await handle_websocket_connection(websocket, room_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for room {room_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket endpoint: {e}")
        try:
            await websocket.close(code=4000, reason="Internal server error")
        except:
            pass