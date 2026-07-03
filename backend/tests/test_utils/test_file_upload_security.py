"""檔案上傳安全驗證測試（magic-byte 檢查與圖片解壓縮炸彈防護）"""

import io
from unittest.mock import Mock

import pytest
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app.utils.file_upload import (
    FileUploadError,
    FileUploadManager,
    _matches_magic,
)
from app.utils.image_processor import (
    MAX_IMAGE_PIXELS,
    ImageProcessorError,
    _ensure_pixel_limit,
)


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
