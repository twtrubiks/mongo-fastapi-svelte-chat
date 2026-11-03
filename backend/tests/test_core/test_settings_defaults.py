"""Settings 預設值與 .env 載入規則

只鎖住「沒有任何環境變數 / .env 時必須是安全的」那些預設值（關閉 DEBUG、安全標頭全開）；
連線位址、逾時、額度、模型名稱等調整用的預設值不在這裡比對，改了不需要改測試。
tests/test_config.py 在 import 時會寫入 MONGODB_* / REDIS_URL / DEBUG 等環境變數，
每個測試都先清掉所有 Settings 欄位對應的變數。
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

# 未設定部署時的安全基線：任何一項預設變成關閉，都等於預設不安全
SECURE_DEFAULTS = {
    "DEBUG": False,
    "SECURITY_ENABLE_HSTS": True,
    "SECURITY_ENABLE_CSP": True,
    "SECURITY_CSP_REPORT_ONLY": False,
    "SECURITY_ENABLE_HEADERS": True,
    "SECURITY_HIDE_SERVER": True,
    "SECURITY_DEVELOPMENT_MODE": False,
}


def _default(name: str):
    return Settings.model_fields[name].default


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
    def test_secure_defaults_without_env(self, bare_env):
        settings = Settings(_env_file=None, JWT_SECRET="only-required-field")

        assert {name: getattr(settings, name) for name in SECURE_DEFAULTS} == (
            SECURE_DEFAULTS
        )

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

        assert settings.MONGODB_DATABASE == _default("MONGODB_DATABASE")
        assert settings.DEBUG is _default("DEBUG")
        assert settings.CORS_ORIGINS == _default("CORS_ORIGINS")
