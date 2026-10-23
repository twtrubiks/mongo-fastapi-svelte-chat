"""安全配置測試：SECURITY_* 的載入來源與實際產生的安全標頭"""

import pytest

from app.config import Settings
from app.security_config import SecurityConfig, load_security_config

SECURITY_KEYS = [
    "SECURITY_ENABLE_HSTS",
    "SECURITY_HSTS_MAX_AGE",
    "SECURITY_HSTS_INCLUDE_SUBDOMAINS",
    "SECURITY_HSTS_PRELOAD",
    "SECURITY_ENABLE_CSP",
    "SECURITY_CSP_REPORT_ONLY",
    "SECURITY_CSP_REPORT_URI",
    "SECURITY_ENABLE_HEADERS",
    "SECURITY_HIDE_SERVER",
    "SECURITY_SERVER_HEADER",
    "SECURITY_DEVELOPMENT_MODE",
]


@pytest.fixture
def clean_env(monkeypatch):
    """確保外部環境變數不干擾測試"""
    for key in SECURITY_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.mark.unit
class TestLoadSecurityConfig:
    """load_security_config 從 Settings 讀取 SECURITY_*"""

    def test_defaults(self, clean_env):
        config = load_security_config(Settings(_env_file=None))

        assert config == SecurityConfig()
        assert config.enable_hsts is True
        assert config.hsts_max_age == 31536000
        assert config.enable_csp is True
        assert config.csp_report_only is False
        assert config.csp_report_uri is None
        assert config.development_mode is False

    def test_values_from_env_file(self, clean_env, tmp_path):
        """寫在 .env 的 SECURITY_* 必須生效（pydantic-settings 不會寫入 os.environ）"""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "SECURITY_ENABLE_HSTS=false",
                    "SECURITY_HSTS_MAX_AGE=600",
                    "SECURITY_HSTS_INCLUDE_SUBDOMAINS=false",
                    "SECURITY_HSTS_PRELOAD=false",
                    "SECURITY_ENABLE_CSP=false",
                    "SECURITY_CSP_REPORT_ONLY=true",
                    "SECURITY_CSP_REPORT_URI=https://report.example.com/csp",
                    "SECURITY_ENABLE_HEADERS=false",
                    "SECURITY_HIDE_SERVER=false",
                    "SECURITY_SERVER_HEADER=Custom",
                    "SECURITY_DEVELOPMENT_MODE=true",
                ]
            )
        )

        config = load_security_config(Settings(_env_file=env_file))

        assert config == SecurityConfig(
            enable_hsts=False,
            hsts_max_age=600,
            hsts_include_subdomains=False,
            hsts_preload=False,
            enable_csp=False,
            csp_report_only=True,
            csp_report_uri="https://report.example.com/csp",
            enable_security_headers=False,
            hide_server_header=False,
            custom_server_header="Custom",
            development_mode=True,
        )

    def test_environment_variables_override(self, clean_env, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("SECURITY_HSTS_MAX_AGE=600\n")
        clean_env.setenv("SECURITY_HSTS_MAX_AGE", "1200")

        config = load_security_config(Settings(_env_file=env_file))

        assert config.hsts_max_age == 1200

    def test_uses_application_settings_by_default(self, clean_env, monkeypatch):
        custom = Settings(_env_file=None, SECURITY_HSTS_MAX_AGE=42)
        monkeypatch.setattr("app.security_config.settings", custom)

        assert load_security_config().hsts_max_age == 42


@pytest.mark.unit
class TestSecurityHeaders:
    """生產與開發模式實際產生的標頭內容"""

    def test_production_headers(self):
        headers = SecurityConfig(development_mode=False).get_security_headers()

        csp = headers.pop("Content-Security-Policy")
        assert headers == {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            ),
            "Strict-Transport-Security": (
                "max-age=31536000; includeSubDomains; preload"
            ),
        }
        assert "script-src 'self';" in csp
        assert "'unsafe-eval'" not in csp
        assert "frame-ancestors 'none'" in csp
        assert "upgrade-insecure-requests" in csp
        assert "report-uri" not in csp

    def test_development_mode_omits_hsts(self):
        headers = SecurityConfig(development_mode=True).get_security_headers()

        assert "Strict-Transport-Security" not in headers
        assert headers["X-Frame-Options"] == "DENY"

    def test_development_csp_allows_docs_cdn(self):
        csp = SecurityConfig(development_mode=True).get_csp_header()

        assert "https://cdn.jsdelivr.net" in csp
        assert "frame-ancestors 'none'" in csp

    def test_hsts_parts(self):
        config = SecurityConfig(
            hsts_max_age=60, hsts_include_subdomains=False, hsts_preload=False
        )
        assert config.get_hsts_header() == "max-age=60"

    def test_csp_report_only_and_report_uri(self):
        headers = SecurityConfig(
            csp_report_only=True, csp_report_uri="https://r.example.com"
        ).get_security_headers()

        assert "Content-Security-Policy" not in headers
        assert headers["Content-Security-Policy-Report-Only"].endswith(
            "; report-uri https://r.example.com"
        )

    def test_hsts_and_csp_can_be_disabled(self):
        headers = SecurityConfig(
            enable_hsts=False, enable_csp=False
        ).get_security_headers()

        assert "Strict-Transport-Security" not in headers
        assert "Content-Security-Policy" not in headers
        assert headers["X-Frame-Options"] == "DENY"

    def test_all_headers_can_be_disabled(self):
        assert (
            SecurityConfig(enable_security_headers=False).get_security_headers() == {}
        )
