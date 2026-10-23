"""檔案上傳安全驗證測試（副檔名白名單、magic-byte 檢查與圖片解壓縮炸彈防護）"""

import hashlib
import io
from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app.utils.file_upload import (
    _MAGIC_SIGNATURES,
    FileUploadError,
    FileUploadManager,
    _matches_magic,
)
from app.utils.image_processor import (
    MAX_IMAGE_PIXELS,
    ImageProcessorError,
    _ensure_pixel_limit,
)

# 允許的副檔名 → 檔案類型（白名單契約）
EXPECTED_TYPES = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image",
    ".bmp": "image",
    ".pdf": "document",
    ".doc": "document",
    ".docx": "document",
    ".txt": "document",
    ".md": "document",
    ".mp4": "video",
    ".mov": "video",
    ".avi": "video",
    ".mkv": "video",
    ".webm": "video",
    ".mp3": "audio",
    ".wav": "audio",
    ".ogg": "audio",
    ".m4a": "audio",
    ".flac": "audio",
}

# 真實檔案的檔頭樣本（獨立於 _MAGIC_SIGNATURES 的對照資料）
REAL_HEADERS = {
    ".jpg": [b"\xff\xd8\xff\xe0\x00\x10JFIF\x00"],
    ".jpeg": [b"\xff\xd8\xff\xe1\x00\x18Exif\x00"],
    ".png": [b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"],
    ".gif": [b"GIF89a\x01\x00\x01\x00", b"GIF87a\x01\x00\x01\x00"],
    ".webp": [b"RIFF\x24\x00\x00\x00WEBPVP8 "],
    ".bmp": [b"BM\x36\x00\x0c\x00\x00\x00"],
    ".pdf": [b"%PDF-1.7\n%\xe2\xe3"],
    ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1\x00\x00"],
    ".docx": [b"PK\x03\x04\x14\x00\x06\x00"],
    ".mp4": [b"\x00\x00\x00\x18ftypmp42"],
    ".mov": [b"\x00\x00\x00\x14ftypqt  "],
    ".m4a": [b"\x00\x00\x00\x20ftypM4A "],
    ".avi": [b"RIFF\x00\x10\x00\x00AVI LIST"],
    ".mkv": [b"\x1aE\xdf\xa3\x9fB\x86\x81\x01"],
    ".webm": [b"\x1aE\xdf\xa3\x9fB\x86\x81\x01"],
    ".mp3": [
        b"ID3\x04\x00\x00",
        b"\xff\xfb\x90\x64",
        b"\xff\xf3\x90\x64",
        b"\xff\xf2\x90\x64",
    ],
    ".wav": [b"RIFF\x24\x08\x00\x00WAVEfmt "],
    ".ogg": [b"OggS\x00\x02\x00\x00"],
    ".flac": [b"fLaC\x00\x00\x00\x22"],
}

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _make_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    """建立測試用 UploadFile（模擬 multipart 上傳）"""
    return UploadFile(
        file=io.BytesIO(content),
        size=len(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


class TestMatchesMagic:
    """_matches_magic 檔頭簽章比對"""

    def test_jpeg_header_matches(self):
        assert _matches_magic(b"\xff\xd8\xff\xe0" + b"\x00" * 12, ".jpg") is True

    def test_png_header_matches(self):
        assert _matches_magic(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, ".png") is True

    def test_text_disguised_as_jpeg_rejected(self):
        assert _matches_magic(b"<script>alert(1)</script>", ".jpg") is False

    def test_webp_requires_both_riff_and_webp(self):
        # RIFF 容器需同時比對 offset 0 與 offset 8 兩段
        assert (
            _matches_magic(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 4, ".webp") is True
        )
        assert (
            _matches_magic(b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 4, ".webp") is False
        )

    def test_plain_text_types_skip_check(self):
        # txt / md 無 magic number，不檢查
        assert _matches_magic(b"hello world", ".txt") is True
        assert _matches_magic(b"# markdown", ".md") is True

    def test_signature_table_covers_every_binary_type(self):
        """除了純文字外，每個允許的副檔名都必須有簽章（漏列 = 不檢查檔頭）"""
        assert set(_MAGIC_SIGNATURES) == set(EXPECTED_TYPES) - {".txt", ".md"}

    @pytest.mark.parametrize(
        ("ext", "header"),
        [(ext, header) for ext, headers in REAL_HEADERS.items() for header in headers],
    )
    def test_real_headers_accepted(self, ext, header):
        assert _matches_magic(header.ljust(16, b"\x00"), ext) is True

    @pytest.mark.parametrize("ext", sorted(REAL_HEADERS))
    def test_disguised_html_rejected(self, ext):
        assert _matches_magic(b"<html><script>alert(1)</script>", ext) is False


class TestGetFileType:
    """檔案類型只依副檔名白名單判斷，不採信客戶端的 content_type"""

    @pytest.mark.parametrize(("ext", "expected"), sorted(EXPECTED_TYPES.items()))
    def test_allowed_extension_decides_type(self, tmp_path, ext, expected):
        manager = FileUploadManager(upload_dir=str(tmp_path))
        upload = _make_upload(f"file{ext}", b"", "application/octet-stream")
        assert manager.get_file_type(upload) == expected

    def test_extension_case_insensitive(self, tmp_path):
        manager = FileUploadManager(upload_dir=str(tmp_path))
        assert manager.get_file_type(_make_upload("PHOTO.PNG", b"", "")) == "image"

    @pytest.mark.parametrize(
        "filename", ["evil.html", "evil.svg", "script.js", "noext", "image.png.exe"]
    )
    def test_unknown_extension_rejected_even_with_image_mime(self, tmp_path, filename):
        manager = FileUploadManager(upload_dir=str(tmp_path))
        upload = _make_upload(filename, PNG_BYTES, "image/png")
        with pytest.raises(FileUploadError, match="不支援的檔案類型"):
            manager.get_file_type(upload)

    @pytest.mark.asyncio
    async def test_disguised_html_is_not_stored(self, tmp_path):
        manager = FileUploadManager(upload_dir=str(tmp_path))
        upload = _make_upload("evil.html", PNG_BYTES, "image/png")

        with pytest.raises(FileUploadError):
            await manager.save_file(upload)

        assert not any(path.is_file() for path in tmp_path.rglob("*"))


class TestSaveFileMagicValidation:
    """save_file 對偽裝副檔名的拒絕行為"""

    @pytest.mark.asyncio
    async def test_fake_image_rejected(self, tmp_path):
        manager = FileUploadManager(upload_dir=str(tmp_path))
        fake = _make_upload("fake.jpg", b"not an image at all", "image/jpeg")
        with pytest.raises(FileUploadError, match="檔案內容與副檔名不符"):
            await manager.save_file(fake)

    @pytest.mark.asyncio
    async def test_real_png_header_accepted(self, tmp_path):
        manager = FileUploadManager(upload_dir=str(tmp_path))
        png = _make_upload("real.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png")
        file_info = await manager.save_file(png)
        assert file_info["file_type"] == "image"
        assert (tmp_path / "image" / file_info["filename"]).exists()

    @pytest.mark.asyncio
    async def test_saved_content_matches_upload(self, tmp_path):
        """存檔內容逐 byte 與上傳內容相同（檢查完檔頭要倒回開頭再寫入）"""
        manager = FileUploadManager(upload_dir=str(tmp_path))
        content = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4

        file_info = await manager.save_file(
            _make_upload("photo.png", content, "image/png")
        )

        stored = tmp_path / "image" / file_info["filename"]
        assert stored.read_bytes() == content
        assert file_info["size"] == len(content)
        assert file_info["hash"] == hashlib.sha256(content).hexdigest()
        assert file_info["url"] == f"/api/files/image/{file_info['filename']}"

    @pytest.mark.asyncio
    async def test_same_second_uploads_do_not_overwrite(self, tmp_path):
        """同一秒上傳同名檔案，各自得到唯一檔名、內容互不覆寫"""
        manager = FileUploadManager(upload_dir=str(tmp_path))
        frozen = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        first_content = PNG_BYTES + b"first"
        second_content = PNG_BYTES + b"second"

        with patch("app.utils.file_upload.datetime") as mock_datetime:
            mock_datetime.now.return_value = frozen
            first = await manager.save_file(
                _make_upload("same.png", first_content, "image/png")
            )
            second = await manager.save_file(
                _make_upload("same.png", second_content, "image/png")
            )

        assert first["filename"] != second["filename"]
        assert (tmp_path / "image" / first["filename"]).read_bytes() == first_content
        assert (tmp_path / "image" / second["filename"]).read_bytes() == second_content


class TestPixelLimit:
    """圖片解壓縮炸彈防護"""

    def test_small_image_passes(self):
        img = Image.new("RGB", (10, 10))
        _ensure_pixel_limit(img)  # 不應拋出

    def test_oversized_image_rejected(self):
        bomb = Mock(width=100_000, height=100_000)  # 100 億像素
        with pytest.raises(ImageProcessorError, match="像素數超過上限"):
            _ensure_pixel_limit(bomb)

    def test_pillow_global_limit_configured(self):
        # 第二道防線：Pillow 全域上限已設定
        assert Image.MAX_IMAGE_PIXELS == MAX_IMAGE_PIXELS
