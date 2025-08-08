"""安全配置設定"""

import os

from pydantic import BaseModel


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

        # HSTS 標頭 (僅在啟用時)
        if self.enable_hsts:
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


# 從環境變數載入安全配置
def load_security_config() -> SecurityConfig:
    """從環境變數載入安全配置"""
    return SecurityConfig(
        enable_hsts=os.getenv("SECURITY_ENABLE_HSTS", "true").lower() == "true",
        hsts_max_age=int(os.getenv("SECURITY_HSTS_MAX_AGE", "31536000")),
        hsts_include_subdomains=os.getenv(
            "SECURITY_HSTS_INCLUDE_SUBDOMAINS", "true"
        ).lower()
        == "true",
        hsts_preload=os.getenv("SECURITY_HSTS_PRELOAD", "true").lower() == "true",
        enable_csp=os.getenv("SECURITY_ENABLE_CSP", "true").lower() == "true",
        csp_report_only=os.getenv("SECURITY_CSP_REPORT_ONLY", "false").lower()
        == "true",
        csp_report_uri=os.getenv("SECURITY_CSP_REPORT_URI"),
        enable_security_headers=os.getenv("SECURITY_ENABLE_HEADERS", "true").lower()
        == "true",
        hide_server_header=os.getenv("SECURITY_HIDE_SERVER", "true").lower() == "true",
        custom_server_header=os.getenv("SECURITY_SERVER_HEADER", "FastAPI"),
        development_mode=os.getenv("SECURITY_DEVELOPMENT_MODE", "false").lower()
        == "true",
    )


# 預設安全配置實例
default_security_config = load_security_config()

# 開發環境安全配置
dev_security_config = SecurityConfig(
    enable_hsts=False, enable_csp=True, development_mode=True
)

# 生產環境安全配置
prod_security_config = SecurityConfig(
    enable_hsts=True,
    hsts_max_age=63072000,  # 2 年
    enable_csp=True,
    development_mode=False,
    csp_report_uri="/api/csp-report",  # 可選的 CSP 報告端點
)
