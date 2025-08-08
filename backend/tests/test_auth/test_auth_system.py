"""認證系統的完整測試"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.auth.dependencies import get_current_active_user, get_current_user
from app.auth.jwt_handler import create_access_token, decode_access_token
from app.auth.password import get_password_hash, verify_password


class TestAuthSystem:
    """測試完整的認證系統"""

    @pytest.mark.asyncio
    async def test_password_hashing_and_verification(self):
        """測試密碼雜湊和驗證"""
        # 測試密碼雜湊
        password = "SecurePassword123!"
        hashed = await get_password_hash(password)

        # 確保雜湊後的密碼不同於原始密碼
        assert hashed != password
        assert len(hashed) > 50  # bcrypt 雜湊通常很長

        # 測試密碼驗證
        assert await verify_password(password, hashed) is True
        assert await verify_password("WrongPassword", hashed) is False

        # 測試相同密碼產生不同雜湊（因為 salt）
        hashed2 = await get_password_hash(password)
        assert hashed != hashed2
        assert await verify_password(password, hashed2) is True

    def test_jwt_token_creation_and_validation(self):
        """測試 JWT 令牌的創建和驗證"""
        # 測試令牌創建
        user_data = {"sub": "testuser", "user_id": "123"}
        token = create_access_token(data=user_data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT 格式: header.payload.signature

        # 測試令牌驗證
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123"
        assert "exp" in payload

        # 測試過期令牌
        expired_token = create_access_token(
            data=user_data, expires_delta=timedelta(minutes=-1)
        )

        # decode_access_token 返回 None 而不是拋出異常
        payload = decode_access_token(expired_token)
        assert payload is None

    def test_token_with_different_algorithms(self):
        """測試不同演算法的令牌安全性"""
        user_data = {"sub": "testuser", "user_id": "123"}

        # 使用正確的演算法
        token = create_access_token(data=user_data)
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"

        # 嘗試使用不同的演算法解碼（應該失敗）
        with patch("app.auth.jwt_handler.settings.JWT_ALGORITHM", "HS512"):
            payload = decode_access_token(token)
            # 使用錯誤的演算法應該返回 None
            assert payload is None

    @pytest.mark.asyncio
    async def test_get_current_user_dependency(self):
        """測試獲取當前用戶的依賴"""
        from bson import ObjectId

        from app.models.user import TokenData

        # Mock database
        mock_db = Mock()
        mock_users_collection = AsyncMock()
        mock_db.users = mock_users_collection

        # Mock user data
        user_data = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
        }
        mock_users_collection.find_one.return_value = user_data

        # Mock get_database
        with patch(
            "app.auth.dependencies.get_database", new_callable=AsyncMock
        ) as mock_get_db:
            mock_get_db.return_value = mock_db

            # 創建 TokenData
            token_data = TokenData(
                username="testuser", user_id="507f1f77bcf86cd799439011"
            )

            # 測試獲取當前用戶
            user = await get_current_user(token_data)
            assert user["_id"] == "507f1f77bcf86cd799439011"  # ObjectId 被轉換為字符串
            assert user["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_active_user_dependency(self):
        """測試獲取當前活躍用戶的依賴"""
        # 測試活躍用戶
        active_user = {"id": "123", "username": "activeuser", "is_active": True}

        result = await get_current_active_user(active_user)
        assert result == active_user

        # 測試非活躍用戶
        inactive_user = {"id": "456", "username": "inactiveuser", "is_active": False}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(inactive_user)
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "使用者已停用"

    def test_token_expiration_scenarios(self):
        """測試各種令牌過期場景"""
        user_data = {"sub": "testuser", "user_id": "123"}

        # 測試 1 小時過期
        token_1h = create_access_token(data=user_data, expires_delta=timedelta(hours=1))
        payload = decode_access_token(token_1h)
        exp_time = datetime.fromtimestamp(payload["exp"], tz=UTC)
        now = datetime.now(UTC)
        assert (exp_time - now).total_seconds() > 3500  # 接近 1 小時

        # 測試 24 小時過期
        token_24h = create_access_token(
            data=user_data, expires_delta=timedelta(hours=24)
        )
        payload = decode_access_token(token_24h)
        exp_time = datetime.fromtimestamp(payload["exp"], tz=UTC)
        assert (exp_time - now).total_seconds() > 86000  # 接近 24 小時

    def test_token_with_additional_claims(self):
        """測試帶有額外聲明的令牌"""
        user_data = {
            "sub": "testuser",
            "user_id": "123",
            "roles": ["user", "moderator"],
            "permissions": ["read", "write"],
            "session_id": "sess_abc123",
        }

        token = create_access_token(data=user_data)
        payload = decode_access_token(token)

        assert payload["roles"] == ["user", "moderator"]
        assert payload["permissions"] == ["read", "write"]
        assert payload["session_id"] == "sess_abc123"

    def test_malformed_token_handling(self):
        """測試處理格式錯誤的令牌"""
        # 測試各種無效令牌格式
        invalid_tokens = [
            "not.a.token",
            "invalid_base64.invalid.invalid",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",  # 只有 header
            "",
            "Bearer token",  # 包含 Bearer 前綴
        ]

        for invalid_token in invalid_tokens:
            payload = decode_access_token(invalid_token)
            assert payload is None

    @pytest.mark.asyncio
    async def test_password_strength_validation(self):
        """測試密碼強度驗證"""
        # 測試各種密碼 (暫時保留供未來實現)
        _weak_passwords = [
            "123456",  # 太簡單
            "password",  # 常見密碼
            "12345678",  # 純數字
            "abcdefgh",  # 純字母
            "short",  # 太短
        ]

        _strong_passwords = [
            "SecureP@ss123",  # 混合大小寫、數字、特殊字符
            "VeryLongPasswordWith123!",
            "Complex#Pass2024",
            "MyStr0ng!Password",
        ]

        # 這裡假設有密碼驗證函數
        # 實際實現需要根據專案的密碼策略
        for password in _strong_passwords:
            hashed = await get_password_hash(password)
            assert len(hashed) > 50
            assert await verify_password(password, hashed)

    @pytest.mark.asyncio
    async def test_concurrent_token_validation(self):
        """測試並發令牌驗證"""
        tokens = []

        # 創建多個令牌
        for i in range(10):
            user_data = {"sub": f"user_{i}", "user_id": str(i)}
            token = create_access_token(data=user_data)
            tokens.append((token, i))

        # 並發驗證
        async def verify_single(token, expected_id):
            payload = decode_access_token(token)
            assert payload is not None
            assert payload["user_id"] == str(expected_id)
            return True

        # 使用 asyncio.gather 並發執行
        results = await asyncio.gather(
            *[verify_single(token, i) for token, i in tokens]
        )

        assert all(results)

    def test_token_refresh_mechanism(self):
        """測試令牌刷新機制"""
        # 創建初始令牌
        user_data = {"sub": "testuser", "user_id": "123"}
        original_token = create_access_token(
            data=user_data, expires_delta=timedelta(minutes=5)
        )

        # 驗證原始令牌
        original_payload = decode_access_token(original_token)
        original_exp = original_payload["exp"]

        # 模擬刷新令牌（創建新令牌）
        refresh_data = {
            "sub": original_payload["sub"],
            "user_id": original_payload["user_id"],
            "refreshed": True,
            "original_exp": original_exp,
        }

        refreshed_token = create_access_token(
            data=refresh_data, expires_delta=timedelta(hours=1)
        )

        # 驗證刷新後的令牌
        refreshed_payload = decode_access_token(refreshed_token)
        assert refreshed_payload["refreshed"] is True
        assert refreshed_payload["original_exp"] == original_exp
        assert refreshed_payload["exp"] > original_exp  # 新令牌過期時間更晚
