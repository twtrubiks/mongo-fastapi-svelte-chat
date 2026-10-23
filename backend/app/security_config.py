"""安全配置設定"""

from pydantic import BaseModel

from app.config import Settings, settings


class SecurityConfig(BaseModel):
    """安全配置類別"""

    # HSTS 設定
    enable_hsts: bool = True
    hsts_max_age: int = 31536000  # 1 年
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True

    # CSP 設定
    enable_csp: bool = True
    csp_report_only: bool = False
    csp_report_uri: str | None = None

    # 其他安全設定
    enable_security_headers: bool = True
    hide_server_header: bool = True
    custom_server_header: str = "FastAPI"

    # 開發/生產環境差異
    development_mode: bool = False

    def get_hsts_header(self) -> str:
        """取得 HSTS 標頭值"""
        parts = [f"max-age={self.hsts_max_age}"]

        if self.hsts_include_subdomains:
            parts.append("includeSubDomains")

        if self.hsts_preload:
            parts.append("preload")

        return "; ".join(parts)

    def get_csp_header(self) -> str:
        """取得 CSP 標頭值"""
        if self.development_mode:
            # 開發環境的寬鬆 CSP，允許 Swagger UI 載入 CDN 資源
            return (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "connect-src 'self' ws: wss: http: https:; "
                "img-src 'self' data: http: https:; "
                "font-src 'self' https: https://cdn.jsdelivr.net; "
                "frame-ancestors 'none'"
            )
        else:
            # 生產環境的嚴格 CSP
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' wss:; "
                "frame-ancestors 'none'; "
                "upgrade-insecure-requests"
            )

            # 如果設定了報告 URI，添加到 CSP
            if self.csp_report_uri:
                csp += f"; report-uri {self.csp_report_uri}"

            return csp

    def get_security_headers(self) -> dict[str, str]:
        """取得所有安全標頭"""
        headers = {}

        if not self.enable_security_headers:
            return headers

        # 基本安全標頭
        headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "X-XSS-Protection": "1; mode=block",
                "Referrer-Policy": "strict-origin-when-cross-origin",
                "Permissions-Policy": (
                    "geolocation=(), microphone=(), camera=(), "
                    "payment=(), usb=(), magnetometer=(), gyroscope=()"
                ),
            }
        )

        # HSTS 標頭（開發模式不送：瀏覽器會把 localhost 記成只能走 HTTPS，長達 max-age）
        if self.enable_hsts and not self.development_mode:
            headers["Strict-Transport-Security"] = self.get_hsts_header()

        # CSP 標頭
        if self.enable_csp:
            header_name = (
                "Content-Security-Policy-Report-Only"
                if self.csp_report_only
                else "Content-Security-Policy"
            )
            headers[header_name] = self.get_csp_header()

        return headers


def load_security_config(config: Settings | None = None) -> SecurityConfig:
    """從應用程式設定載入安全配置

    透過 Settings 讀取 SECURITY_*，因此 .env 與環境變數都會生效
    （pydantic-settings 讀取 .env 時不會寫入 os.environ，不能用 os.getenv）。
    """
    config = config or settings
    return SecurityConfig(
        enable_hsts=config.SECURITY_ENABLE_HSTS,
        hsts_max_age=config.SECURITY_HSTS_MAX_AGE,
        hsts_include_subdomains=config.SECURITY_HSTS_INCLUDE_SUBDOMAINS,
        hsts_preload=config.SECURITY_HSTS_PRELOAD,
        enable_csp=config.SECURITY_ENABLE_CSP,
        csp_report_only=config.SECURITY_CSP_REPORT_ONLY,
        csp_report_uri=config.SECURITY_CSP_REPORT_URI,
        enable_security_headers=config.SECURITY_ENABLE_HEADERS,
        hide_server_header=config.SECURITY_HIDE_SERVER,
        custom_server_header=config.SECURITY_SERVER_HEADER,
        development_mode=config.SECURITY_DEVELOPMENT_MODE,
    )
