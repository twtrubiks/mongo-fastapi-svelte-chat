"""密碼處理測試"""

import pytest

from app.auth.password import get_password_hash, verify_password


@pytest.mark.unit
class TestPasswordHandler:
    @pytest.mark.asyncio
    async def test_password_hash_and_verify(self):
        """測試密碼雜湊和驗證"""
        plain_password = "testpass123"

        # 雜湊密碼
        hashed = await get_password_hash(plain_password)

        # 驗證正確密碼
        assert await verify_password(plain_password, hashed) is True

        # 驗證錯誤密碼
        assert await verify_password("wrongpassword", hashed) is False

    @pytest.mark.asyncio
    async def test_hash_not_equal_to_plain(self):
        """測試雜湊不等於明文"""
        plain_password = "testpass123"
        hashed = await get_password_hash(plain_password)

        assert hashed != plain_password

    @pytest.mark.asyncio
    async def test_same_password_different_hash(self):
        """測試相同密碼產生不同雜湊"""
        plain_password = "testpass123"

        hash1 = await get_password_hash(plain_password)
        hash2 = await get_password_hash(plain_password)

        # 每次雜湊應該不同（因為有 salt）
        assert hash1 != hash2

        # 但都應該能驗證
        assert await verify_password(plain_password, hash1) is True
        assert await verify_password(plain_password, hash2) is True
