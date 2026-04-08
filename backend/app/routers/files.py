"""檔案上傳相關的 API 端點"""

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.auth.dependencies import get_current_active_user
from app.core.fastapi_integration import FileServiceDep
from app.services.file_service import FileService

router = APIRouter(prefix="/files", tags=["檔案"])


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_single_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = FileServiceDep,
):
    """上傳單個檔案"""
    return await file_service.upload_file(file, current_user)


@router.post("/upload/image", status_code=status.HTTP_201_CREATED)
async def upload_image_only(
    file: UploadFile = File(...),
    generate_thumbnails: bool = Query(True, description="是否生成縮圖"),
    current_user: dict = Depends(get_current_active_user),
    file_service: FileService = FileServiceDep,
):
    """僅上傳圖片檔案"""
    return await file_service.upload_image(file, generate_thumbnails, current_user)


@router.get("/thumbnail/{filename}")
async def get_thumbnail(
    filename: str = Path(..., description="檔案名稱"),
    size: str = Query("medium", description="縮圖大小"),
    _current_user: dict = Depends(get_current_active_user),
    file_service: FileService = FileServiceDep,
):
    """獲取縮圖"""
    thumbnail_path, thumbnail_filename = file_service.resolve_thumbnail(filename, size)
    return FileResponse(
        path=str(thumbnail_path),
        filename=thumbnail_filename,
        media_type="image/png",
    )


@router.get("/{file_type}/{filename}")
async def download_file(
    file_type: str = Path(..., description="檔案類型"),
    filename: str = Path(..., description="檔案名稱"),
    _current_user: dict = Depends(get_current_active_user),
    file_service: FileService = FileServiceDep,
):
    """下載檔案"""
    file_path, safe_filename, mime_type, should_inline = file_service.resolve_download(
        file_type, filename
    )

    if should_inline:
        return FileResponse(
            path=str(file_path),
            media_type=mime_type,
            headers={"Content-Disposition": "inline"},
        )
    return FileResponse(
        path=str(file_path), filename=safe_filename, media_type=mime_type
    )
