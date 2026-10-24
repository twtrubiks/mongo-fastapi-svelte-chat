"""檔案上傳 / 下載 HTTP API 測試（經由完整路由、依賴注入與 middleware）

上傳管理器與下載根目錄都指向 tmp_path，不寫入 repo 的 uploads/。
"""

import hashlib
import io
import re
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from PIL import Image

from app.config import settings
from app.core.fastapi_integration import create_file_service
from app.main import app
from app.services.file_service import FileService
from app.utils.file_upload import FileUploadManager
from app.utils.image_processor import ImageProcessor

FORM = {"Content-Type": "application/x-www-form-urlencoded"}

# 副檔名 → (存放的檔案類型, 下載回應的 Content-Type, 顯示方式)
DOWNLOAD_CONTRACT = {
    ".jpg": ("image", "image/jpeg", "inline"),
    ".jpeg": ("image", "image/jpeg", "inline"),
    ".png": ("image", "image/png", "inline"),
    ".gif": ("image", "image/gif", "inline"),
    ".webp": ("image", "image/webp", "inline"),
    ".bmp": ("image", "image/bmp", "inline"),
    ".pdf": ("document", "application/pdf", "inline"),
    ".doc": ("document", "application/msword", "attachment"),
    ".docx": (
        "document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "attachment",
    ),
    ".txt": ("document", "text/plain; charset=utf-8", "attachment"),
    ".md": ("document", "text/markdown; charset=utf-8", "attachment"),
    ".mp4": ("video", "video/mp4", "attachment"),
    ".mov": ("video", "video/quicktime", "attachment"),
    ".avi": ("video", "video/x-msvideo", "attachment"),
    ".mkv": ("video", "video/x-matroska", "attachment"),
    ".webm": ("video", "video/webm", "attachment"),
    ".mp3": ("audio", "audio/mpeg", "attachment"),
    ".wav": ("audio", "audio/wav", "attachment"),
    ".ogg": ("audio", "audio/ogg", "attachment"),
    ".m4a": ("audio", "audio/mp4", "attachment"),
    ".flac": ("audio", "audio/flac", "attachment"),
}


@pytest.fixture
async def uploader(async_client, isolated_db_manager):
    password = "password123"
    register = await async_client.post(
        "/api/auth/register",
        json={
            "username": "uploader",
            "email": "uploader@example.com",
            "password": password,
        },
    )
    assert register.status_code == 201
    login = await async_client.post(
        "/api/auth/login",
        data={"username": "uploader", "password": password},
        headers=FORM,
    )
    assert login.status_code == 200
    return {
        "id": register.json()["user"]["id"],
        "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
    }


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """讓上傳寫入與下載讀取都落在 tmp_path"""
    upload_dir = tmp_path / "uploads"
    service = FileService(
        FileUploadManager(str(upload_dir)), ImageProcessor(str(tmp_path / "processed"))
    )
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))
    app.dependency_overrides[create_file_service] = lambda: service
    yield upload_dir
    app.dependency_overrides.pop(create_file_service, None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestFilesApi:
    async def test_upload_response_and_download_round_trip(
        self, async_client, uploader, upload_dir
    ):
        """上傳回應的完整檔案資訊，且回傳的 url 可下載回相同內容"""
        content = b"# meeting notes\n"
        frozen = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

        with patch("app.utils.file_upload.datetime") as clock:
            clock.now.return_value = frozen
            response = await async_client.post(
                "/api/files/upload",
                files={"file": ("Notes.TXT", content, "text/plain")},
                headers=uploader["headers"],
            )

        assert response.status_code == 201, response.text
        body = response.json()
        file_info = body["file"]
        filename = file_info["filename"]
        # 儲存檔名：上傳時間_8 碼隨機十六進位 + 小寫副檔名
        assert re.fullmatch(r"20260102_030405_[0-9a-f]{8}\.txt", filename)
        assert uuid.UUID(file_info["id"]).version == 4
        assert body == {
            "message": "檔案上傳成功",
            "file": {
                "id": file_info["id"],
                "filename": filename,
                "original_name": "Notes.TXT",
                "file_type": "document",
                "content_type": "text/plain",
                "size": len(content),
                "hash": hashlib.sha256(content).hexdigest(),
                "relative_path": f"document/{filename}",
                "url": f"/api/files/document/{filename}",
                "created_at": "2026-01-02T03:04:05+00:00",
                "uploaded_by": "uploader",
                "user_id": uploader["id"],
            },
        }

        assert (upload_dir / "document" / filename).read_bytes() == content
        download = await async_client.get(file_info["url"], headers=uploader["headers"])
        assert download.status_code == 200
        assert download.content == content

    async def test_image_upload_exposes_urls_not_server_paths(
        self, async_client, uploader, upload_dir, tmp_path, monkeypatch
    ):
        """回應不含伺服器端絕對路徑；縮圖以可下載的 URL 表示"""
        monkeypatch.chdir(tmp_path)  # 縮圖下載以工作目錄下的 processed/ 為根
        image = io.BytesIO()
        Image.new("RGB", (400, 300), "blue").save(image, format="PNG")

        response = await async_client.post(
            "/api/files/upload/image",
            files={"file": ("photo.png", image.getvalue(), "image/png")},
            headers=uploader["headers"],
        )

        assert response.status_code == 201, response.text
        file_info = response.json()["file"]
        filename = file_info["filename"]
        assert "path" not in file_info
        assert str(tmp_path) not in response.text
        assert file_info["thumbnails"] == {
            size: f"/api/files/thumbnail/{filename}?size={size}"
            for size in ("small", "medium", "large")
        }
        thumbnail = await async_client.get(
            file_info["thumbnails"]["small"], headers=uploader["headers"]
        )
        assert thumbnail.status_code == 200
        with Image.open(io.BytesIO(thumbnail.content)) as img:
            assert max(img.size) == 150

    async def test_download_content_type_per_extension(
        self, async_client, uploader, upload_dir
    ):
        """下載回應的 Content-Type 依副檔名決定；圖片與 PDF 內嵌顯示，其餘以附件下載"""
        for ext, (file_type, _, _) in DOWNLOAD_CONTRACT.items():
            (upload_dir / file_type / f"sample{ext}").write_bytes(b"stored bytes")

        served = {}
        for ext, (file_type, _, _) in DOWNLOAD_CONTRACT.items():
            response = await async_client.get(
                f"/api/files/{file_type}/sample{ext}", headers=uploader["headers"]
            )
            assert response.status_code == 200, (ext, response.text)
            served[ext] = (
                file_type,
                response.headers["content-type"],
                response.headers["content-disposition"].split(";")[0],
            )

        assert served == DOWNLOAD_CONTRACT


@pytest.fixture
def default_storage(tmp_path, monkeypatch):
    """以預設目錄建立上傳管理器與圖片處理器（相對路徑，工作目錄切到 tmp_path）"""
    monkeypatch.chdir(tmp_path)
    service = FileService(FileUploadManager(), ImageProcessor())
    app.dependency_overrides[create_file_service] = lambda: service
    yield
    app.dependency_overrides.pop(create_file_service, None)


@pytest.mark.asyncio
@pytest.mark.integration
class TestDefaultStorageLocations:
    async def test_default_dirs_are_where_downloads_read(
        self, async_client, uploader, default_storage
    ):
        """預設的上傳與縮圖目錄要與下載端點讀取的目錄一致，否則上傳成功但一律 404"""
        image = io.BytesIO()
        Image.new("RGB", (400, 300), "green").save(image, format="PNG")

        response = await async_client.post(
            "/api/files/upload/image",
            files={"file": ("photo.png", image.getvalue(), "image/png")},
            headers=uploader["headers"],
        )

        assert response.status_code == 201, response.text
        file_info = response.json()["file"]
        download = await async_client.get(file_info["url"], headers=uploader["headers"])
        thumbnail = await async_client.get(
            file_info["thumbnails"]["small"], headers=uploader["headers"]
        )
        assert (download.status_code, thumbnail.status_code) == (200, 200)
        assert download.content == image.getvalue()
