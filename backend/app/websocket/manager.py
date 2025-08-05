"""WebSocket 連線管理器"""
from typing import Dict, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
import json
import asyncio
import logging
from app.utils.json_encoder import safe_json_dumps

UTC = timezone.utc

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket 連線管理器"""
    
    def __init__(self):
        # 儲存所有活躍的 WebSocket 連線
        # 格式: {user_id: {room_id: websocket}}
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        
        # 儲存房間中的使用者
        # 格式: {room_id: {user_id}}
        self.room_users: Dict[str, Set[str]] = {}
        
        # 儲存使用者資訊
        # 格式: {user_id: user_info}
        self.user_info: Dict[str, Dict] = {}
        
        # 連線鎖，確保線程安全
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str, room_id: str, user_info: Dict):
        """
        建立 WebSocket 連線
        
        Args:
            websocket: WebSocket 連線物件
            user_id: 使用者 ID
            room_id: 房間 ID
            user_info: 使用者資訊
        """
        await websocket.accept()
        
        async with self._lock:
            # 初始化使用者連線字典
            if user_id not in self.active_connections:
                self.active_connections[user_id] = {}
            
            # 檢查是否已有相同使用者在同一房間的連線
            if room_id in self.active_connections[user_id]:
                old_websocket = self.active_connections[user_id][room_id]
                try:
                    await old_websocket.close()
                except Exception as e:
                    logger.error(f"Error closing old connection for user {user_id}: {e}")
            
            # 儲存連線
            self.active_connections[user_id][room_id] = websocket
            
            # 初始化房間使用者集合
            if room_id not in self.room_users:
                self.room_users[room_id] = set()
            
            # 添加使用者到房間
            self.room_users[room_id].add(user_id)
            
            # 儲存使用者資訊
            self.user_info[user_id] = user_info
            
            logger.info(f"User {user_id} connected to room {room_id}")
            
            # 向房間廣播使用者上線訊息
            await self.broadcast_to_room(room_id, {
                "type": "user_joined",
                "user": user_info,
                "timestamp": datetime.now(UTC).isoformat(),
                "room_id": room_id
            }, exclude_user=user_id)
            
            # 向當前使用者發送房間使用者列表
            await self.send_personal_message(user_id, room_id, {
                "type": "room_users",
                "users": [self.user_info[uid] for uid in self.room_users[room_id] if uid in self.user_info],
                "timestamp": datetime.now(UTC).isoformat(),
                "room_id": room_id
            })

    async def disconnect(self, user_id: str, room_id: str):
        """
        斷開 WebSocket 連線
        
        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
        """
        async with self._lock:
            # 移除連線
            if user_id in self.active_connections:
                if room_id in self.active_connections[user_id]:
                    del self.active_connections[user_id][room_id]
                
                # 如果使用者沒有其他房間連線，移除使用者
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    if user_id in self.user_info:
                        del self.user_info[user_id]
            
            # 從房間中移除使用者
            if room_id in self.room_users:
                self.room_users[room_id].discard(user_id)
                
                # 如果房間沒有使用者，移除房間
                if not self.room_users[room_id]:
                    del self.room_users[room_id]
            
            logger.info(f"User {user_id} disconnected from room {room_id}")
            
            # 向房間廣播使用者離線訊息
            if room_id in self.room_users and user_id in self.user_info:
                await self.broadcast_to_room(room_id, {
                    "type": "user_left",
                    "user": self.user_info[user_id],
                    "timestamp": datetime.now(UTC).isoformat(),
                    "room_id": room_id
                })

    async def send_personal_message(self, user_id: str, room_id: str, message: dict):
        """
        發送私人訊息給特定使用者
        
        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
            message: 訊息內容
        """
        if (user_id in self.active_connections and 
            room_id in self.active_connections[user_id]):
            
            websocket = self.active_connections[user_id][room_id]
            try:
                await websocket.send_text(safe_json_dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {user_id}: {e}")
                # 連線已斷開，清理連線
                await self.disconnect(user_id, room_id)

    async def broadcast_to_room(self, room_id: str, message: dict, exclude_user: Optional[str] = None):
        """
        向房間內所有使用者廣播訊息
        
        Args:
            room_id: 房間 ID
            message: 訊息內容
            exclude_user: 排除的使用者 ID
        """
        if room_id not in self.room_users:
            return
        
        # 複製使用者列表以避免在迭代時修改
        users_to_notify = list(self.room_users[room_id])
        
        for user_id in users_to_notify:
            if exclude_user and user_id == exclude_user:
                continue
                
            if (user_id in self.active_connections and 
                room_id in self.active_connections[user_id]):
                
                websocket = self.active_connections[user_id][room_id]
                try:
                    await websocket.send_text(safe_json_dumps(message))
                except Exception as e:
                    logger.error(f"Error broadcasting to {user_id}: {e}")
                    # 連線已斷開，清理連線
                    await self.disconnect(user_id, room_id)

    async def broadcast_message(self, room_id: str, message: dict, sender_id: Optional[str]):
        """
        廣播聊天訊息
        
        Args:
            room_id: 房間 ID
            message: 訊息內容
            sender_id: 發送者 ID，如果為 None 則不排除任何用戶
        """
        # 添加訊息元數據
        message_data = {
            "type": "message",
            "payload": message,
            "sender": self.user_info.get(sender_id, {}) if sender_id else {},
            "timestamp": datetime.now(UTC).isoformat(),
            "room_id": room_id
        }
        
        await self.broadcast_to_room(room_id, message_data, exclude_user=sender_id)

    def get_room_users(self, room_id: str) -> List[Dict]:
        """
        獲取房間內的使用者列表
        
        Args:
            room_id: 房間 ID
            
        Returns:
            List[Dict]: 使用者資訊列表
        """
        if room_id not in self.room_users:
            return []
        
        return [self.user_info[user_id] for user_id in self.room_users[room_id] 
                if user_id in self.user_info]

    def get_user_rooms(self, user_id: str) -> List[str]:
        """
        獲取使用者參與的房間列表
        
        Args:
            user_id: 使用者 ID
            
        Returns:
            List[str]: 房間 ID 列表
        """
        if user_id not in self.active_connections:
            return []
        
        return list(self.active_connections[user_id].keys())

    def is_user_in_room(self, user_id: str, room_id: str) -> bool:
        """
        檢查使用者是否在房間中
        
        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
            
        Returns:
            bool: 是否在房間中
        """
        return (room_id in self.room_users and 
                user_id in self.room_users[room_id])

    async def handle_ping(self, user_id: str, room_id: str):
        """
        處理 ping 訊息
        
        Args:
            user_id: 使用者 ID
            room_id: 房間 ID
        """
        await self.send_personal_message(user_id, room_id, {
            "type": "pong",
            "timestamp": datetime.now(UTC).isoformat()
        })

    async def send_notification(self, user_id: str, notification_data: dict):
        """
        發送通知給指定使用者
        
        Args:
            user_id: 使用者 ID
            notification_data: 通知資料
        """
        # 發送通知給使用者在所有房間的連線
        if user_id in self.active_connections:
            # 創建副本以避免迭代時字典大小變化的錯誤
            room_ids = list(self.active_connections[user_id].keys())
            
            if room_ids:
                # 如果用戶有活躍連接，發送到任意一個房間即可（避免重複通知）
                room_id = room_ids[0]
                try:
                    notification_message = {
                        "type": "notification",
                        "data": notification_data,
                        "timestamp": datetime.now(UTC).isoformat()
                    }
                    await self.send_personal_message(user_id, room_id, notification_message)
                    logger.debug(f"Notification sent to {user_id} via room {room_id}")
                except Exception as e:
                    logger.error(f"Error sending notification to {user_id} in room {room_id}: {e}")
                    
                    # 如果第一個房間發送失敗，嘗試其他房間
                    for room_id in room_ids[1:]:
                        try:
                            await self.send_personal_message(user_id, room_id, notification_message)
                            logger.debug(f"Notification sent to {user_id} via fallback room {room_id}")
                            break
                        except Exception as e:
                            logger.error(f"Error sending notification to {user_id} in fallback room {room_id}: {e}")
                            continue
            else:
                logger.debug(f"User {user_id} has no active connections for notification")
        else:
            # 將警告降級為 debug，因為用戶離線是正常情況
            logger.debug(f"User {user_id} not found in active connections for notification (user is offline)")

# 全域連線管理器實例
connection_manager = ConnectionManager()