"""JWT 處理測試"""
import pytest
from datetime import timedelta
from app.auth.jwt_handler import create_access_token, decode_access_token, create_refresh_token

@pytest.mark.unit
class TestJWTHandler:
    def test_create_access_token_success(self):
        """測試成功創建 JWT token"""
        data = {"sub": "testuser", "user_id": "123456"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT token 應該有一定長度
        
    def test_decode_access_token_success(self):
        """測試成功解碼 JWT token"""
        data = {"sub": "testuser", "user_id": "123456"}
        token = create_access_token(data)
        
        payload = decode_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123456"
        assert "exp" in payload
        
    def test_decode_invalid_token(self):
        """測試解碼無效 token"""
        invalid_token = "invalid.token.here"
        
        result = decode_access_token(invalid_token)
        
        assert result is None
        
    def test_token_expiration(self):
        """測試 token 過期"""
        data = {"sub": "testuser", "user_id": "123456"}
        # 創建一個已過期的 token
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        result = decode_access_token(token)
        
        assert result is None
        
    def test_create_refresh_token(self):
        """測試創建 refresh token"""
        data = {"sub": "testuser", "user_id": "123456"}
        token = create_refresh_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 50
        
        # 解碼並驗證
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"
        assert payload["sub"] == "testuser"