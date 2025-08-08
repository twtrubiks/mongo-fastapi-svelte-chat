"""測試配置模組"""

import os

import pytest

from app.config import settings


@pytest.mark.unit
class TestConfig:
    """測試配置類別"""

    # 測試資料庫設定
    TEST_DATABASE_NAME = "test_chatroom"
    TEST_MONGODB_URL = "mongodb://root:password@localhost:27017"

    # 測試使用者設定
    TEST_USER_DATA = {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "Test User",
        "password": "testpass123",
    }

    # JWT 設定
    JWT_SECRET = "test-secret-key-very-long-and-secure"
    JWT_ALGORITHM = "HS256"

    # Redis 測試設定
    TEST_REDIS_URL = "redis://localhost:6379/1"  # 使用不同的資料庫編號避免衝突

    @classmethod
    def setup_test_environment(cls):
        """設置測試環境變數"""
        os.environ["MONGODB_DATABASE"] = cls.TEST_DATABASE_NAME
        os.environ["MONGODB_URL"] = cls.TEST_MONGODB_URL
        os.environ["JWT_SECRET"] = cls.JWT_SECRET
        os.environ["JWT_ALGORITHM"] = cls.JWT_ALGORITHM
        os.environ["REDIS_URL"] = cls.TEST_REDIS_URL
        os.environ["DEBUG"] = "True"  # 開啟 DEBUG 模式以放寬 rate limit

        # 確保設定更新
        settings.MONGODB_DATABASE = cls.TEST_DATABASE_NAME
        settings.MONGODB_URL = cls.TEST_MONGODB_URL
        settings.REDIS_URL = cls.TEST_REDIS_URL
        settings.DEBUG = True  # 確保 DEBUG 模式啟用


# 在導入時立即設置測試環境
TestConfig.setup_test_environment()
