"""Settings 預設值與 .env 載入規則

沒有任何環境變數 / .env 時的預設值，就是未設定部署的實際行為，因此整表比對。
tests/test_config.py 在 import 時會寫入 MONGODB_* / REDIS_URL / DEBUG 等環境變數，
每個測試都先清掉所有 Settings 欄位對應的變數。
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

EXPECTED_DEFAULTS = {
    "MONGODB_URL": "mongodb://localhost:27017",
    "MONGODB_DATABASE": "chatroom",
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_MINUTES": 480,
    "JWT_REFRESH_EXPIRE_DAYS": 7,
    "REDIS_URL": "redis://localhost:6379/0",
    "REDIS_PASSWORD": None,
    "REDIS_MAX_CONNECTIONS": 20,
    "USER_CACHE_TTL": 300,
    "RATE_LIMIT_REQUESTS_PER_MINUTE": 60,
    "RATE_LIMIT_REQUESTS_PER_HOUR": 1000,
    "RATE_LIMIT_BURST_SIZE": 10,
    "TRUSTED_PROXIES": "127.0.0.1,::1",
    "AI_PROVIDER": "nvidia",
    "NVIDIA_API_KEY": None,
    "NVIDIA_BASE_URL": "https://integrate.api.nvidia.com/v1",
    "NVIDIA_MODEL": "nvidia/nemotron-3-super-120b-a12b",
    "GOOGLE_API_KEY": None,
    "GEMINI_MODEL": "gemini-2.5-flash",
    "BOT_RATE_LIMIT_PER_MINUTE": 5,
    "DEBUG": False,
    "FRONTEND_URL": "http://localhost:5173",
    "ALLOWED_HOSTS": "*",
    "CORS_ORIGINS": "*",
    "UPLOAD_DIR": "uploads",
    "GENERATE_THUMBNAILS": True,
    "SECURITY_ENABLE_HSTS": True,
    "SECURITY_HSTS_MAX_AGE": 31536000,
    "SECURITY_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURITY_HSTS_PRELOAD": True,
    "SECURITY_ENABLE_CSP": True,
    "SECURITY_CSP_REPORT_ONLY": False,
    "SECURITY_CSP_REPORT_URI": None,
    "SECURITY_ENABLE_HEADERS": True,
    "SECURITY_HIDE_SERVER": True,
    "SECURITY_SERVER_HEADER": "FastAPI",
    "SECURITY_DEVELOPMENT_MODE": False,
}


@pytest.fixture
def bare_env(monkeypatch, tmp_path):
    """清空所有設定相關的環境變數，並切到沒有 .env 的空目錄"""
    for name in Settings.model_fields:
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.chdir(tmp_path)
    return monkeypatch


@pytest.mark.unit
class TestSettingsDefaults:
    def test_defaults_without_env(self, bare_env):
        settings = Settings(_env_file=None, JWT_SECRET="only-required-field")

        assert settings.model_dump() == {
            **EXPECTED_DEFAULTS,
            "JWT_SECRET": "only-required-field",
        }

    def test_jwt_secret_has_no_default(self, bare_env):
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)

        assert [error["loc"] for error in exc_info.value.errors()] == [("JWT_SECRET",)]


@pytest.mark.unit
class TestSettingsSources:
    def test_dotenv_in_working_directory_is_loaded(self, bare_env, tmp_path):
        (tmp_path / ".env").write_text(
            "JWT_SECRET=secret-from-dotenv\nMONGODB_DATABASE=db_from_dotenv\n"
        )

        settings = Settings()

        assert settings.JWT_SECRET == "secret-from-dotenv"
        assert settings.MONGODB_DATABASE == "db_from_dotenv"

    def test_variable_names_are_case_sensitive(self, bare_env, tmp_path):
        """只有全大寫的欄位名稱生效；小寫同名變數（如其他工具設的 debug）一律忽略"""
        (tmp_path / ".env").write_text(
            "JWT_SECRET=secret-from-dotenv\nmongodb_database=lowercase_db\n"
        )
        bare_env.setenv("debug", "true")
        bare_env.setenv("cors_origins", "https://lowercase.example")

        settings = Settings()

        assert settings.MONGODB_DATABASE == "chatroom"
        assert settings.DEBUG is False
        assert settings.CORS_ORIGINS == "*"
