"""檔案上傳相關的 API 端點"""

import logging
from pathlib import Path as PathLib

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_active_user
from app.config import settings
from app.utils.file_upload import upload_file
from app.utils.image_processor import get_image_processor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["檔案"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_single_file(
    file: UploadFile = File(...), current_user: dict = Depends(get_current_active_user)
):
    """
    上傳單個檔案

    Args:
        file: 上傳的檔案
        current_user: 當前使用者

    Returns:
        dict: 上傳的檔案資訊
    """
    try:
        # 上傳檔案
        file_info = await upload_file(file)

        # 如果是圖片且啟用了縮圖生成
        if file_info["file_type"] == "image" and settings.GENERATE_THUMBNAILS:
            try:
                processor = get_image_processor()
                thumbnails = processor.create_multiple_thumbnails(
                    file_info["path"], ["small", "medium", "large"]
                )
                file_info["thumbnails"] = thumbnails
            except Exception as e:
                logger.warning(f"Failed to generate thumbnails: {e}")
                file_info["thumbnails"] = {}

        # 記錄上傳者資訊
        file_info["uploaded_by"] = current_user["username"]
        file_info["user_id"] = str(current_user["_id"])

        return {"message": "檔案上傳成功", "file": file_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="檔案上傳失敗"
        ) from e


@router.post("/upload/image", status_code=status.HTTP_201_CREATED)
async def upload_image_only(
    file: UploadFile = File(...),
    generate_thumbnails: bool = Query(True, description="是否生成縮圖"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    僅上傳圖片檔案

    Args:
        file: 上傳的圖片檔案
        generate_thumbnails: 是否生成縮圖
        current_user: 當前使用者

    Returns:
        dict: 上傳的圖片資訊
    """
    try:
        # 限制只能上傳圖片
        file_info = await upload_file(file, allowed_types=["image"])

        # 生成縮圖
        if generate_thumbnails:
            try:
                processor = get_image_processor()
                thumbnails = processor.create_multiple_thumbnails(
                    file_info["path"], ["small", "medium", "large"]
                )
                file_info["thumbnails"] = thumbnails

                # 獲取圖片資訊
                image_info = processor.get_image_info(file_info["path"])
                file_info["image_info"] = image_info

            except Exception as e:
                logger.warning(f"Failed to process image: {e}")
                file_info["thumbnails"] = {}
                file_info["image_info"] = {}

        # 記錄上傳者資訊
        file_info["uploaded_by"] = current_user["username"]
        file_info["user_id"] = str(current_user["_id"])

        return {"message": "圖片上傳成功", "file": file_info}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in image upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="圖片上傳失敗"
        ) from e


@router.get("/thumbnail/{filename}")
async def get_thumbnail(
    filename: str = Path(..., description="檔案名稱"),
    size: str = Query("medium", description="縮圖大小"),
):
    """
    獲取縮圖

    Args:
        filename: 檔案名稱
        size: 縮圖大小

    Returns:
        FileResponse: 縮圖響應
    """
    try:
        # 驗證縮圖大小
        allowed_sizes = ["small", "medium", "large"]
        if size not in allowed_sizes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="無效的縮圖大小"
            )

        # 構建縮圖路徑
        file_stem = PathLib(filename).stem
        file_ext = PathLib(filename).suffix
        thumbnail_filename = f"{file_stem}_{size}{file_ext}"
        thumbnail_path = PathLib("processed") / "thumbnails" / thumbnail_filename

        # 檢查縮圖是否存在
        if not thumbnail_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="縮圖不存在"
            )

        # 返回縮圖
        return FileResponse(
            path=str(thumbnail_path),
            filename=thumbnail_filename,
            media_type="image/png",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading thumbnail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="縮圖下載失敗"
        ) from e


@router.get("/{file_type}/{filename}")
async def download_file(
    file_type: str = Path(..., description="檔案類型"),
    filename: str = Path(..., description="檔案名稱"),
):
    """
    下載檔案

    Args:
        file_type: 檔案類型
        filename: 檔案名稱

    Returns:
        FileResponse: 檔案響應
    """
    try:
        # 驗證檔案類型
        allowed_types = ["image", "document", "video", "audio"]
        if file_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="無效的檔案類型"
            )

        # 構建檔案路徑
        file_path = PathLib(settings.UPLOAD_DIR) / file_type / filename

        # 檢查檔案是否存在
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="檔案不存在"
            )

        # 根據檔案擴展名決定 MIME 類型和處理方式
        file_extension = file_path.suffix.lower()

        # 獲取正確的 MIME 類型
        mime_type = "application/octet-stream"  # 預設值
        should_inline = False  # 是否應該在瀏覽器中顯示而不是下載

        from ..utils.file_upload import ALLOWED_FILE_TYPES

        for file_type, config in ALLOWED_FILE_TYPES.items():
            if file_extension in config["extensions"]:
                # 找到對應的 MIME 類型
                ext_index = config["extensions"].index(file_extension)
                if ext_index < len(config["mime_types"]):
                    mime_type = config["mime_types"][ext_index]

                # PDF 和圖片應該在瀏覽器中顯示
                if file_type in ["image", "document"] and file_extension == ".pdf":
                    should_inline = True
                elif file_type == "image":
                    should_inline = True
                break

        # 根據是否應該內嵌顯示來決定響應頭
        if should_inline:
            # 對於 PDF 和圖片，不設置 filename 以避免強制下載
            return FileResponse(
                path=str(file_path),
                media_type=mime_type,
                headers={"Content-Disposition": "inline"},
            )
        else:
            # 對於其他文件類型，保持下載行為
            return FileResponse(
                path=str(file_path), filename=filename, media_type=mime_type
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="檔案下載失敗"
        ) from e
