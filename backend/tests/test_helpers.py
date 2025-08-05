"""測試輔助函數"""
import asyncio
from typing import Dict, Any, Tuple
from datetime import datetime, UTC
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase
from app.auth.jwt_handler import create_access_token
from tests.test_database import MongoDBTestManager
from tests.test_config import TestConfig
import pytest


class DataTestHelper:
    """測試輔助類別"""
    
    def __init__(self, db_manager: MongoDBTestManager):
        self.db_manager = db_manager
    
    async def create_test_user(self, username: str = None, email: str = None) -> Tuple[str, Dict[str, Any]]:
        """創建測試使用者"""
        user_id = ObjectId()
        user_data = {
            "_id": user_id,
            "username": username or TestConfig.TEST_USER_DATA["username"],
            "email": email or TestConfig.TEST_USER_DATA["email"],
            "full_name": TestConfig.TEST_USER_DATA["full_name"],
            "hashed_password": "hashed_password",
            "is_active": True,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
        
        database = await self.db_manager.get_database()
        await database.users.insert_one(user_data)
        
        return str(user_id), user_data
    
    async def create_test_room(self, user_id: str, name: str = "測試房間") -> Tuple[str, Dict[str, Any]]:
        """創建測試房間"""
        room_id = ObjectId()
        room_data = {
            "_id": room_id,
            "name": name,
            "description": "測試用房間",
            "owner_id": user_id,
            "members": [user_id],
            "is_private": False,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
        
        database = await self.db_manager.get_database()
        await database.rooms.insert_one(room_data)
        
        return str(room_id), room_data
    
    async def create_test_message(self, user_id: str, room_id: str, content: str = "測試訊息") -> Tuple[str, Dict[str, Any]]:
        """創建測試訊息"""
        message_id = ObjectId()
        message_data = {
            "_id": message_id,
            "room_id": room_id,
            "user_id": user_id,
            "username": TestConfig.TEST_USER_DATA["username"],
            "content": content,
            "message_type": "text",
            "status": "sent",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC)
        }
        
        database = await self.db_manager.get_database()
        await database.messages.insert_one(message_data)
        
        return str(message_id), message_data
    
    def create_auth_headers(self, user_id: str, username: str = None) -> Dict[str, str]:
        """創建認證標頭"""
        token = create_access_token(data={
            "sub": username or TestConfig.TEST_USER_DATA["username"],
            "user_id": user_id
        })
        return {"Authorization": f"Bearer {token}"}
    
    async def setup_test_data(self) -> Dict[str, Any]:
        """設置完整的測試資料"""
        # 創建測試使用者
        user_id, user_data = await self.create_test_user()
        
        # 創建測試房間
        room_id, room_data = await self.create_test_room(user_id)
        
        # 創建認證標頭
        auth_headers = self.create_auth_headers(user_id)
        
        return {
            "user_id": user_id,
            "user_data": user_data,
            "room_id": room_id,
            "room_data": room_data,
            "auth_headers": auth_headers
        }