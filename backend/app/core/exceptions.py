"""應用程式自訂異常層級"""


class AppError(Exception):
    """應用程式業務異常基底類別

    所有業務邏輯異常繼承此類別，由 FastAPI exception_handler 統一處理。
    status_code 屬性決定 HTTP 回應狀態碼。
    """

    status_code: int = 400
    headers: dict[str, str] | None = None

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    """資源不存在（404）"""

    status_code = 404


class UnauthorizedError(AppError):
    """認證失敗（401）"""

    status_code = 401
    headers = {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    """權限不足（403）"""

    status_code = 403


class ConflictError(AppError):
    """資源衝突（409）"""

    status_code = 409
