"""統一錯誤處理中間件"""

import logging
import traceback
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pymongo.errors import BulkWriteError, DuplicateKeyError, PyMongoError
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import (
    BusinessLogicError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)

UTC = UTC
logger = logging.getLogger(__name__)


class ErrorDetail:
    """錯誤詳情類別"""

    def __init__(self, error_code: str, message: str, details: dict[str, Any] = None):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now(UTC)


class GlobalErrorHandler(BaseHTTPMiddleware):
    """全域錯誤處理中間件"""

    def __init__(self, app, debug: bool = False):
        super().__init__(app)
        self.debug = debug

        # 錯誤映射表
        self.error_mappings = {
            # 業務邏輯錯誤
            BusinessLogicError: (status.HTTP_400_BAD_REQUEST, "BUSINESS_LOGIC_ERROR"),
            ValidationError: (status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_ERROR"),
            NotFoundError: (status.HTTP_404_NOT_FOUND, "RESOURCE_NOT_FOUND"),
            UnauthorizedError: (status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED"),
            ForbiddenError: (status.HTTP_403_FORBIDDEN, "FORBIDDEN"),
            ConflictError: (status.HTTP_409_CONFLICT, "RESOURCE_CONFLICT"),
            # HTTP 錯誤
            HTTPException: (None, "HTTP_ERROR"),  # 使用原始狀態碼
            # 資料庫錯誤
            DuplicateKeyError: (status.HTTP_409_CONFLICT, "DUPLICATE_KEY_ERROR"),
            BulkWriteError: (status.HTTP_400_BAD_REQUEST, "BULK_WRITE_ERROR"),
            PyMongoError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "DATABASE_ERROR"),
            # Redis 錯誤
            RedisConnectionError: (
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "CACHE_CONNECTION_ERROR",
            ),
            RedisError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "CACHE_ERROR"),
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        """處理請求並捕獲錯誤"""
        try:
            # 記錄請求開始
            start_time = datetime.now(UTC)
            logger.debug(f"開始處理請求: {request.method} {request.url}")

            # 執行請求
            response = await call_next(request)

            # 記錄請求完成
            end_time = datetime.now(UTC)
            duration = (end_time - start_time).total_seconds()
            logger.debug(
                f"請求完成: {request.method} {request.url} - {response.status_code} ({duration:.3f}s)"
            )

            return response

        except Exception as exc:
            return await self.handle_error(request, exc)

    async def handle_error(self, request: Request, exc: Exception) -> JSONResponse:
        """處理錯誤並返回標準化回應"""
        try:
            error_detail = self._create_error_detail(exc)
            status_code = self._get_status_code(exc)

            # 記錄錯誤
            await self._log_error(request, exc, error_detail, status_code)

            # 構建回應
            response_data = {
                "success": False,
                "error": {
                    "code": error_detail.error_code,
                    "message": error_detail.message,
                    "timestamp": error_detail.timestamp.isoformat(),
                    "path": str(request.url),
                    "method": request.method,
                },
            }

            # 在 debug 模式下添加詳細資訊
            if self.debug and error_detail.details:
                response_data["error"]["details"] = error_detail.details

            # 在 debug 模式下添加 traceback
            if self.debug and not isinstance(
                exc, HTTPException | BusinessLogicError | ValidationError
            ):
                response_data["error"]["traceback"] = traceback.format_exc()

            return JSONResponse(
                status_code=status_code,
                content=response_data,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        except Exception as handler_error:
            # 錯誤處理器本身出錯的最後備援
            logger.critical(f"錯誤處理器發生錯誤: {handler_error}", exc_info=True)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "success": False,
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "伺服器內部錯誤",
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                },
            )

    def _create_error_detail(self, exc: Exception) -> ErrorDetail:
        """根據異常類型創建錯誤詳情"""
        error_type = type(exc)

        # 處理自定義業務錯誤
        if isinstance(
            exc,
            BusinessLogicError
            | ValidationError
            | NotFoundError
            | UnauthorizedError
            | ForbiddenError
            | ConflictError,
        ):
            return ErrorDetail(
                error_code=self.error_mappings[error_type][1],
                message=str(exc),
                details=getattr(exc, "details", {}),
            )

        # 處理 HTTPException
        elif isinstance(exc, HTTPException):
            return ErrorDetail(
                error_code="HTTP_ERROR",
                message=exc.detail,
                details={"status_code": exc.status_code},
            )

        # 處理資料庫錯誤
        elif isinstance(exc, DuplicateKeyError):
            return ErrorDetail(
                error_code="DUPLICATE_KEY_ERROR",
                message="資源重複，請檢查唯一性限制",
                details={"error": str(exc)},
            )

        elif isinstance(exc, BulkWriteError):
            return ErrorDetail(
                error_code="BULK_WRITE_ERROR",
                message="批量寫入操作失敗",
                details={"write_errors": exc.details.get("writeErrors", [])},
            )

        elif isinstance(exc, PyMongoError):
            return ErrorDetail(
                error_code="DATABASE_ERROR",
                message="資料庫操作失敗",
                details={"error": str(exc)} if self.debug else {},
            )

        # 處理 Redis 錯誤
        elif isinstance(exc, RedisConnectionError):
            return ErrorDetail(
                error_code="CACHE_CONNECTION_ERROR",
                message="快取服務連線失敗",
                details={"error": str(exc)} if self.debug else {},
            )

        elif isinstance(exc, RedisError):
            return ErrorDetail(
                error_code="CACHE_ERROR",
                message="快取操作失敗",
                details={"error": str(exc)} if self.debug else {},
            )

        # 處理其他未知錯誤
        else:
            return ErrorDetail(
                error_code="INTERNAL_SERVER_ERROR",
                message="伺服器內部錯誤" if not self.debug else str(exc),
                details={"error_type": error_type.__name__} if self.debug else {},
            )

    def _get_status_code(self, exc: Exception) -> int:
        """獲取錯誤對應的 HTTP 狀態碼"""
        error_type = type(exc)

        # HTTPException 使用原始狀態碼
        if isinstance(exc, HTTPException):
            return exc.status_code

        # 其他錯誤使用映射表
        if error_type in self.error_mappings:
            status_code, _ = self.error_mappings[error_type]
            return status_code

        # 未知錯誤預設為 500
        return status.HTTP_500_INTERNAL_SERVER_ERROR

    async def _log_error(
        self,
        request: Request,
        exc: Exception,
        error_detail: ErrorDetail,
        status_code: int,
    ):
        """記錄錯誤詳情"""
        error_info = {
            "method": request.method,
            "url": str(request.url),
            "status_code": status_code,
            "error_code": error_detail.error_code,
            "error_message": error_detail.message,
            "timestamp": error_detail.timestamp.isoformat(),
            "user_agent": request.headers.get("user-agent"),
            "client_ip": self._get_client_ip(request),
        }

        # 根據錯誤嚴重程度選擇日誌級別
        if status_code >= 500:
            logger.error(f"伺服器錯誤: {error_info}", exc_info=True)
        elif status_code >= 400:
            logger.warning(f"客戶端錯誤: {error_info}")
        else:
            logger.info(f"請求錯誤: {error_info}")

    def _get_client_ip(self, request: Request) -> str:
        """獲取客戶端 IP 地址"""
        # 檢查代理標頭
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            return x_real_ip

        # 使用連線資訊
        if hasattr(request, "client") and request.client:
            return request.client.host

        return "unknown"


# 便利函數
def create_error_handler_middleware(debug: bool = False) -> GlobalErrorHandler:
    """創建錯誤處理中間件實例"""
    return GlobalErrorHandler(app=None, debug=debug)
