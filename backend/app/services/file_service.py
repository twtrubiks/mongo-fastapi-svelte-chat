"""檔案服務層"""

import logging
from pathlib import Path

from app.config import settings
from app.core.exceptions import AppError, NotFoundError
from app.utils.file_upload import (
    ALLOWED_FILE_TYPES as _FILE_TYPE_CONFIG,
)
from app.utils.file_upload import (
    FileUploadError,
    FileUploadManager,
    get_mime_type,
)
from app.utils.image_processor import (
    THUMBNAIL_SIZES,
    ImageProcessor,
    ImageProcessorError,
)

logger = logging.getLogger(__name__)

# 從 source-of-truth 衍生，避免硬編碼重複
ALLOWED_THUMBNAIL_SIZES = set(THUMBNAIL_SIZES.keys())
ALLOWED_FILE_TYPE_NAMES = set(_FILE_TYPE_CONFIG.keys())


class FileService:
    """檔案服務類別"""

    def __init__(
        self,
        file_manager: FileUploadManager,
        image_processor: ImageProcessor,
    ):
        self._file_manager = file_manager
        self._image_processor = image_processor

    def _validate_filename(self, filename: str) -> str:
        """驗證檔案名稱，防止路徑遍歷攻擊"""
        safe = Path(filename).name
        if safe != filename:
            raise AppError("無效的檔案名稱")
        return safe

    def _validate_path_within(self, file_path: Path, base_dir: Path) -> Path:
        """驗證解析後的路徑在允許的基礎目錄內，防止 symlink 逃逸"""
        resolved = file_path.resolve()
        if not resolved.is_relative_to(base_dir.resolve()):
            raise AppError("無效的檔案路徑")
        return resolved

    def _try_generate_thumbnails(self, image_path: str) -> dict:
        """嘗試生成縮圖（graceful degradation，失敗時回空 dict）"""
        try:
            return self._image_processor.create_multiple_thumbnails(image_path)
        except (
            OSError,
            ValueError,
            ImageProcessorError,
        ) as e:  # intentional fail-open: 縮圖生成失敗不影響上傳
            logger.warning(f"縮圖生成失敗: {e}")
            return {}

    def _try_get_image_info(self, image_path: str) -> dict:
        """嘗試獲取圖片資訊（graceful degradation，失敗時回空 dict）"""
        try:
            return self._image_processor.get_image_info(image_path)
        except (
            OSError,
            ValueError,
            ImageProcessorError,
        ) as e:  # intentional fail-open: 圖片資訊取得失敗不影響上傳
            logger.warning(f"獲取圖片資訊失敗: {e}")
            return {}

    async def _save_file(self, file, allowed_types: list[str] | None = None) -> dict:
        """透過 FileUploadManager 儲存檔案，將 FileUploadError 轉為 AppError"""
        try:
            if allowed_types:
                file_type = self._file_manager.get_file_type(file)
                if file_type not in allowed_types:
                    raise FileUploadError(f"不允許的檔案類型: {file_type}")
            return await self._file_manager.save_file(file)
        except FileUploadError as e:
            raise AppError(str(e)) from e

    @staticmethod
    def _attach_uploader(file_info: dict, current_user: dict) -> None:
        """在檔案資訊中記錄上傳者"""
        file_info["uploaded_by"] = current_user["username"]
        file_info["user_id"] = str(current_user["_id"])

    async def upload_file(self, file, current_user: dict) -> dict:
        """上傳單個檔案，自動生成圖片縮圖"""
        file_info = await self._save_file(file)

        # 圖片且啟用縮圖 → graceful degradation
        if file_info["file_type"] == "image" and settings.GENERATE_THUMBNAILS:
            file_info["thumbnails"] = self._try_generate_thumbnails(file_info["path"])

        self._attach_uploader(file_info, current_user)
        return {"message": "檔案上傳成功", "file": file_info}

    async def upload_image(
        self, file, generate_thumbnails: bool, current_user: dict
    ) -> dict:
        """僅上傳圖片檔案，可選生成縮圖與圖片資訊"""
        file_info = await self._save_file(file, allowed_types=["image"])

        if generate_thumbnails:
            file_info["thumbnails"] = self._try_generate_thumbnails(file_info["path"])
            file_info["image_info"] = self._try_get_image_info(file_info["path"])

        self._attach_uploader(file_info, current_user)
        return {"message": "圖片上傳成功", "file": file_info}

    def resolve_thumbnail(self, filename: str, size: str) -> tuple[Path, str]:
        """解析縮圖路徑，回傳 (絕對路徑, 檔案名稱)"""
        if size not in ALLOWED_THUMBNAIL_SIZES:
            raise AppError("無效的縮圖大小")

        safe_filename = self._validate_filename(filename)
        file_stem = Path(safe_filename).stem
        file_ext = Path(safe_filename).suffix
        thumbnail_filename = f"{file_stem}_{size}{file_ext}"

        thumbnail_dir = Path("processed") / "thumbnails"
        thumbnail_path = self._validate_path_within(
            thumbnail_dir / thumbnail_filename, thumbnail_dir
        )

        if not thumbnail_path.exists():
            raise NotFoundError("縮圖不存在")

        return thumbnail_path, thumbnail_filename

    def resolve_download(
        self, file_type: str, filename: str
    ) -> tuple[Path, str, str, bool]:
        """解析下載檔案路徑，回傳 (絕對路徑, 安全檔名, MIME 類型, 是否內嵌顯示)"""
        if file_type not in ALLOWED_FILE_TYPE_NAMES:
            raise AppError("無效的檔案類型")

        safe_filename = self._validate_filename(filename)

        upload_base = Path(settings.UPLOAD_DIR)
        file_path = self._validate_path_within(
            upload_base / file_type / safe_filename, upload_base
        )

        if not file_path.exists():
            raise NotFoundError("檔案不存在")

        file_extension = file_path.suffix.lower()
        mime_type = get_mime_type(file_extension)
        should_inline = file_type == "image" or file_extension == ".pdf"

        return file_path, safe_filename, mime_type, should_inline
