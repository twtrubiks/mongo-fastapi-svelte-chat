"""安全標頭中間件"""
from typing import Dict, Optional, Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """
    安全標頭中間件
    
    自動為所有回應添加安全相關的 HTTP 標頭，提升應用程式的基礎安全性。
    
    Features:
    - X-Content-Type-Options: 防止 MIME 類型嗅探攻擊
    - X-Frame-Options: 防止點擊劫持攻擊
    - X-XSS-Protection: 啟用瀏覽器的 XSS 保護
    - Strict-Transport-Security: 強制使用 HTTPS
    - Content-Security-Policy: 內容安全政策
    - Referrer-Policy: 控制引用來源資訊
    - Permissions-Policy: 控制瀏覽器功能權限
    """
    
    def __init__(
        self,
        enable_hsts: bool = True,
        hsts_max_age: int = 31536000,  # 1 年
        enable_csp: bool = True,
        custom_headers: Optional[Dict[str, str]] = None
    ):
        """
        初始化安全標頭中間件
        
        Args:
            enable_hsts: 是否啟用 HSTS (僅在 HTTPS 環境下生效)
            hsts_max_age: HSTS 最大年齡 (秒)
            enable_csp: 是否啟用內容安全政策
            custom_headers: 自訂標頭
        """
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.enable_csp = enable_csp
        self.custom_headers = custom_headers or {}
        
        # 基本安全標頭
        self.base_headers = {
            # 防止 MIME 類型嗅探
            "X-Content-Type-Options": "nosniff",
            
            # 防止點擊劫持 (Clickjacking)
            "X-Frame-Options": "DENY",
            
            # 啟用瀏覽器 XSS 保護
            "X-XSS-Protection": "1; mode=block",
            
            # 控制引用來源資訊
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # 控制瀏覽器功能權限
            "Permissions-Policy": (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )
        }
        
        # HSTS 標頭 (僅在 HTTPS 環境下有效)
        if self.enable_hsts:
            self.base_headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )
        
        # 內容安全政策
        if self.enable_csp:
            self.base_headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'"
            )
        
        # 合併自訂標頭
        self.headers = {**self.base_headers, **self.custom_headers}
        
        logger.info(f"SecurityHeadersMiddleware initialized with {len(self.headers)} headers")
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """
        處理請求並添加安全標頭
        
        Args:
            request: FastAPI 請求對象
            call_next: 下一個中間件或路由處理器
            
        Returns:
            Response: 帶有安全標頭的回應
        """
        try:
            # 執行下一個中間件或路由處理器
            response = await call_next(request)
            
            # 檢查是否為 HTTPS 連接
            is_https = (
                request.url.scheme == "https" or
                request.headers.get("x-forwarded-proto") == "https" or
                request.headers.get("x-forwarded-ssl") == "on"
            )
            
            # 添加安全標頭到回應
            for header_name, header_value in self.headers.items():
                # 如果不是 HTTPS 連接，跳過 HSTS 標頭
                if header_name == "Strict-Transport-Security" and not is_https:
                    continue
                
                # 避免覆蓋已存在的標頭 (除非明確設定)
                if header_name not in response.headers:
                    response.headers[header_name] = header_value
            
            # 添加伺服器資訊隱藏 (可選)
            if "Server" not in response.headers:
                response.headers["Server"] = "FastAPI"
            
            logger.debug(f"Added security headers to response for {request.url.path}")
            return response
            
        except Exception as e:
            # 安全地記錄錯誤信息，避免序列化問題
            error_type = type(e).__name__
            
            # 安全地獲取錯誤消息
            try:
                error_msg = str(e)[:500]  # 限制長度
            except:
                error_msg = "<無法序列化的錯誤消息>"
            
            # 安全地獲取堆棧追蹤
            try:
                import traceback
                error_details = traceback.format_exc()[:2000]  # 限制長度
            except:
                error_details = "<無法獲取堆棧追蹤>"
            
            logger.error(f"Error in SecurityHeadersMiddleware: [{error_type}] {error_msg}")
            logger.debug(f"SecurityHeadersMiddleware error traceback: {error_details}")
            
            # 如果發生錯誤，返回包含安全標頭的錯誤回應
            error_response = JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )
            
            # 即使在錯誤情況下也要添加安全標頭
            for header_name, header_value in self.headers.items():
                error_response.headers[header_name] = header_value
            
            return error_response
    
    def add_custom_header(self, name: str, value: str) -> None:
        """
        動態添加自訂標頭
        
        Args:
            name: 標頭名稱
            value: 標頭值
        """
        self.headers[name] = value
        logger.info(f"Added custom header: {name} = {value}")
    
    def remove_header(self, name: str) -> bool:
        """
        移除指定標頭
        
        Args:
            name: 標頭名稱
            
        Returns:
            bool: 是否成功移除
        """
        if name in self.headers:
            del self.headers[name]
            logger.info(f"Removed header: {name}")
            return True
        return False
    
    def get_headers(self) -> Dict[str, str]:
        """
        取得所有設定的標頭
        
        Returns:
            Dict[str, str]: 所有標頭的字典
        """
        return self.headers.copy()


# 預設設定的安全標頭中間件實例
default_security_middleware = SecurityHeadersMiddleware()

# 開發環境設定 (較寬鬆的 CSP)
dev_security_middleware = SecurityHeadersMiddleware(
    enable_hsts=False,  # 開發環境通常不使用 HTTPS
    enable_csp=True,
    custom_headers={
        "Content-Security-Policy": (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "connect-src 'self' ws: wss: http: https:; "
            "img-src 'self' data: http: https:; "
            "frame-ancestors 'none'"
        )
    }
)

# 生產環境設定 (嚴格的安全標頭)
prod_security_middleware = SecurityHeadersMiddleware(
    enable_hsts=True,
    hsts_max_age=63072000,  # 2 年
    enable_csp=True,
    custom_headers={
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' https:; "
            "connect-src 'self' wss:; "
            "frame-ancestors 'none'; "
            "upgrade-insecure-requests"
        )
    }
)