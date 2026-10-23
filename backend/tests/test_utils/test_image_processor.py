"""圖片處理器測試：縮圖尺寸與輸出目錄（以 Pillow 實際產生圖片驗證）"""

import pytest
from PIL import Image

from app.utils.image_processor import ImageProcessor


def _image_size(path: str) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


@pytest.mark.unit
class TestThumbnails:
    @pytest.mark.parametrize(
        ("source_size", "expected"),
        [
            (
                (1200, 600),
                {"small": (150, 75), "medium": (300, 150), "large": (600, 300)},
            ),
            (
                (600, 1200),
                {"small": (75, 150), "medium": (150, 300), "large": (300, 600)},
            ),
        ],
        ids=["landscape", "portrait"],
    )
    def test_thumbnails_fit_size_boxes(self, tmp_path, source_size, expected):
        """等比縮放進 small 150、medium 300、large 600 的正方形框（橫圖受寬、直圖受高限制）"""
        source = tmp_path / "photo.png"
        Image.new("RGB", source_size, "red").save(source)
        processor = ImageProcessor(output_dir=str(tmp_path / "processed"))

        thumbnails = processor.create_multiple_thumbnails(str(source))

        thumbnail_dir = tmp_path / "processed" / "thumbnails"
        assert thumbnails == {
            size: str(thumbnail_dir / f"photo_{size}.png") for size in expected
        }
        assert {size: _image_size(path) for size, path in thumbnails.items()} == (
            expected
        )

    def test_fresh_environment_creates_output_directories(self, tmp_path):
        output_dir = tmp_path / "processed"  # 尚不存在

        ImageProcessor(output_dir=str(output_dir))

        assert (output_dir / "thumbnails").is_dir()
