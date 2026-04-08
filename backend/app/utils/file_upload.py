"""檔案上傳工具"""

import hashlib
import logging
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import HTTPException, UploadFile, status

logger = logging.getLogger(__name__)

# 允許的檔案類型
ALLOWED_FILE_TYPES = {
    "image": {
        "extensions": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
        "mime_types": [
            "image/jpeg",
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
            "image/bmp",
        ],
        "max_size": 10 * 1024 * 1024,  # 10MB
    },
    "document": {
        "extensions": [".pdf", ".doc", ".docx", ".txt", ".md"],
        "mime_types": [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
        ],
        "max_size": 50 * 1024 * 1024,  # 50MB
    },
    "video": {
        "extensions": [".mp4", ".mov", ".avi", ".mkv", ".webm"],
        "mime_types": [
            "video/mp4",
            "video/quicktime",
            "video/x-msvideo",
            "video/x-matroska",
            "video/webm",
        ],
        "max_size": 100 * 1024 * 1024,  # 100MB
    },
    "audio": {
        "extensions": [".mp3", ".wav", ".ogg", ".m4a", ".flac"],
        "mime_types": [
            "audio/mpeg",
            "audio/wav",
            "audio/ogg",
            "audio/mp4",
            "audio/flac",
        ],
        "max_size": 20 * 1024 * 1024,  # 20MB
    },
}


# 從 ALLOWED_FILE_TYPES 建立預計算的查找表（模組載入時一次性建立）
_EXT_TO_TYPE: dict[str, str] = {}
_EXT_TO_MIME: dict[str, str] = {}
_MIME_TO_TYPE: dict[str, str] = {}

for _file_type, _config in ALLOWED_FILE_TYPES.items():
    for _ext, _mime in zip(_config["extensions"], _config["mime_types"], strict=True):
        _EXT_TO_TYPE[_ext] = _file_type
        _EXT_TO_MIME[_ext] = _mime
        _MIME_TO_TYPE[_mime] = _file_type


def get_mime_type(ext: str) -> str:
    """根據副檔名取得 MIME 類型，找不到時回傳 application/octet-stream"""
    return _EXT_TO_MIME.get(ext, "application/octet-stream")


class FileUploadError(Exception):
    """檔案上傳錯誤"""

    pass


class FileUploadManager:
    """檔案上傳管理器"""

    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)

        # 創建不同類型的子目錄
        for file_type in ALLOWED_FILE_TYPES.keys():
            (self.upload_dir / file_type).mkdir(exist_ok=True)

    def get_file_type(self, file: UploadFile) -> str:
        """
        根據檔案擴展名和 MIME 類型判斷檔案類型

        Args:
            file: 上傳的檔案

        Returns:
            str: 檔案類型

        Raises:
            FileUploadError: 不支援的檔案類型
        """
        file_ext = Path(file.filename).suffix.lower()
        mime_type = file.content_type

        file_type = _EXT_TO_TYPE.get(file_ext) or _MIME_TO_TYPE.get(mime_type)
        if file_type:
            return file_type

        raise FileUploadError(f"不支援的檔案類型: {file_ext} ({mime_type})")

    def validate_file(self, file: UploadFile) -> tuple[str, dict[str, Any]]:
        """
        驗證檔案

        Args:
            file: 上傳的檔案

        Returns:
            Tuple[str, Dict[str, Any]]: 檔案類型和驗證資訊

        Raises:
            FileUploadError: 檔案驗證失敗
        """
        if not file.filename:
            raise FileUploadError("檔案名稱不能為空")

        # 獲取檔案類型
        file_type = self.get_file_type(file)
        config = ALLOWED_FILE_TYPES[file_type]

        # 檢查檔案大小
        if file.size and file.size > config["max_size"]:
            max_size_mb = config["max_size"] / (1024 * 1024)
            raise FileUploadError(f"檔案大小超過限制 ({max_size_mb:.1f}MB)")

        # 檢查檔案名稱長度
        if len(file.filename) > 255:
            raise FileUploadError("檔案名稱太長")

        # 檢查檔案名稱字符
        invalid_chars = ["<", ">", ":", '"', "|", "?", "*", "\\", "/"]
        if any(char in file.filename for char in invalid_chars):
            raise FileUploadError("檔案名稱包含不允許的字符")

        validation_info = {
            "file_type": file_type,
            "original_name": file.filename,
            "content_type": file.content_type,
            "size": file.size,
        }

        return file_type, validation_info

    def generate_unique_filename(self, original_filename: str) -> str:
        """
        生成唯一的檔案名稱

        Args:
            original_filename: 原始檔案名稱

        Returns:
            str: 唯一的檔案名稱
        """
        file_ext = Path(original_filename).suffix.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        return f"{timestamp}_{unique_id}{file_ext}"

    async def get_file_hash(self, file_path: Path) -> str:
        """
        計算檔案雜湊值

        Args:
            file_path: 檔案路徑

        Returns:
            str: 檔案的 SHA-256 雜湊值
        """
        sha256_hash = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(4096):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    async def save_file(
        self, file: UploadFile, custom_filename: str | None = None
    ) -> dict[str, Any]:
        """
        儲存檔案

        Args:
            file: 上傳的檔案
            custom_filename: 自定義檔案名稱（可選）

        Returns:
            Dict[str, Any]: 儲存的檔案資訊

        Raises:
            FileUploadError: 檔案儲存失敗
        """
        try:
            # 驗證檔案
            file_type, validation_info = self.validate_file(file)

            # 生成檔案名稱
            if custom_filename:
                filename = custom_filename
            else:
                filename = self.generate_unique_filename(file.filename)

            # 確定儲存路徑
            file_dir = self.upload_dir / file_type
            file_path = file_dir / filename

            # 確保目錄存在
            file_dir.mkdir(parents=True, exist_ok=True)

            # 儲存檔案
            async with aiofiles.open(file_path, "wb") as f:
                content = await file.read()
                await f.write(content)

            # 計算檔案雜湊值
            file_hash = await self.get_file_hash(file_path)

            # 獲取檔案資訊
            file_info = {
                "id": str(uuid.uuid4()),
                "filename": filename,
                "original_name": validation_info["original_name"],
                "file_type": file_type,
                "content_type": validation_info["content_type"],
                "size": os.path.getsize(file_path),
                "hash": file_hash,
                "path": str(file_path),
                "relative_path": f"{file_type}/{filename}",
                "url": f"/api/files/{file_type}/{filename}",
                "created_at": datetime.now(UTC),
            }

            logger.info(f"File uploaded successfully: {filename}")
            return file_info

        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise FileUploadError(f"檔案儲存失敗: {str(e)}") from e


# 全域檔案上傳管理器實例
file_upload_manager = FileUploadManager()


def get_file_upload_manager() -> FileUploadManager:
    """獲取檔案上傳管理器實例"""
    return file_upload_manager


async def upload_file(
    file: UploadFile, allowed_types: list[str] | None = None
) -> dict[str, Any]:
    """
    上傳單個檔案的便捷函數

    Args:
        file: 上傳的檔案
        allowed_types: 允許的檔案類型列表

    Returns:
        Dict[str, Any]: 上傳的檔案資訊

    Raises:
        HTTPException: 檔案上傳失敗
    """
    try:
        manager = get_file_upload_manager()

        # 如果指定了允許的類型，進行額外檢查
        if allowed_types:
            file_type = manager.get_file_type(file)
            if file_type not in allowed_types:
                raise FileUploadError(f"不允許的檔案類型: {file_type}")

        return await manager.save_file(file)

    except FileUploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="檔案上傳失敗"
        ) from e
