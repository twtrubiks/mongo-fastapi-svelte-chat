"""圖片處理工具"""

import logging
import os
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

# 縮圖尺寸配置
THUMBNAIL_SIZES = {"small": (150, 150), "medium": (300, 300), "large": (600, 600)}


class ImageProcessorError(Exception):
    """圖片處理錯誤"""

    pass


class ImageProcessor:
    """圖片處理器"""

    def __init__(self, output_dir: str = "processed"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # 創建縮圖目錄
        self.thumbnail_dir = self.output_dir / "thumbnails"
        self.thumbnail_dir.mkdir(exist_ok=True)

    def open_image(self, image_path: str) -> Image.Image:
        """
        打開圖片並處理 EXIF 方向

        Args:
            image_path: 圖片路徑

        Returns:
            Image.Image: 處理後的圖片物件

        Raises:
            ImageProcessorError: 圖片打開失敗
        """
        try:
            with Image.open(image_path) as img:
                # 處理 EXIF 方向資訊
                img = ImageOps.exif_transpose(img)
                # 轉換為 RGB 模式（如果不是的話）
                if img.mode != "RGB":
                    img = img.convert("RGB")
                return img.copy()
        except (OSError, UnidentifiedImageError, ValueError) as e:
            logger.error(f"Error opening image {image_path}: {e}")
            raise ImageProcessorError(f"無法打開圖片: {str(e)}") from e

    def get_image_info(self, image_path: str) -> dict[str, Any]:
        """
        獲取圖片資訊

        Args:
            image_path: 圖片路徑

        Returns:
            Dict[str, Any]: 圖片資訊
        """
        try:
            with Image.open(image_path) as img:
                # 獲取基本的 EXIF 資訊（避免複雜對象）
                exif_dict = {}
                try:
                    # 使用更安全的方法獲取EXIF，避免IFDRational等問題
                    if hasattr(img, "_getexif"):
                        exif = img._getexif()
                        if exif:
                            # 只處理基本的數值類型，避免複雜對象
                            for tag, value in exif.items():
                                try:
                                    decoded = ExifTags.TAGS.get(tag, f"Tag_{tag}")

                                    # 嚴格的類型檢查，只接受基本類型
                                    if isinstance(value, int | float | str):
                                        exif_dict[decoded] = value
                                    elif isinstance(value, bytes):
                                        # 安全地處理字節數據
                                        try:
                                            exif_dict[decoded] = value.decode(
                                                "utf-8", errors="ignore"
                                            )[:100]  # 限制長度
                                        except (UnicodeDecodeError, ValueError):
                                            pass  # 跳過無法解碼的字節
                                    elif (
                                        isinstance(value, list | tuple)
                                        and len(value) <= 10
                                    ):
                                        # 只處理小的基本類型列表/元組
                                        try:
                                            safe_list = []
                                            for item in value:
                                                if isinstance(item, int | float | str):
                                                    safe_list.append(item)
                                                else:
                                                    safe_list.append(
                                                        str(item)[:50]
                                                    )  # 轉字符串並限制長度
                                            exif_dict[decoded] = safe_list
                                        except (TypeError, ValueError):
                                            pass  # 跳過有問題的列表
                                    else:
                                        # 對於其他類型（包括IFDRational），安全地轉為字符串
                                        try:
                                            str_value = str(value)[
                                                :100
                                            ]  # 限制字符串長度
                                            exif_dict[decoded] = str_value
                                        except (TypeError, ValueError):
                                            pass  # 跳過無法字符串化的對象
                                except (TypeError, ValueError, AttributeError):
                                    # 完全跳過有問題的EXIF標籤
                                    continue
                except (AttributeError, TypeError, ValueError, OSError):
                    # 如果整個EXIF處理失敗，使用空字典
                    exif_dict = {}

                info = {
                    "filename": Path(image_path).name,
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "file_size": os.path.getsize(image_path),
                    "exif": exif_dict,
                }

                return info
        except (OSError, UnidentifiedImageError, ValueError) as e:
            # 安全地處理異常，避免IFDRational等對象泄漏到異常消息中
            error_msg = "無法獲取圖片資訊"
            try:
                # 嘗試安全地獲取錯誤信息
                if hasattr(e, "args") and e.args:
                    safe_args = []
                    for arg in e.args:
                        try:
                            safe_args.append(str(arg)[:200])  # 限制長度
                        except (TypeError, ValueError):
                            safe_args.append("<無法序列化的錯誤參數>")
                    error_msg = f"無法獲取圖片資訊: {' '.join(safe_args)}"
                else:
                    error_msg = f"無法獲取圖片資訊: {type(e).__name__}"
            except (TypeError, ValueError):
                error_msg = "無法獲取圖片資訊: 未知錯誤"

            logger.error(f"Error getting image info {image_path}: {type(e).__name__}")
            raise ImageProcessorError(error_msg) from e

    def resize_image(
        self,
        image: str | Image.Image,
        target_size: tuple[int, int],
        maintain_aspect_ratio: bool = True,
        resample: int = Image.LANCZOS,
    ) -> str | Image.Image:
        """
        調整圖片大小

        Args:
            image: 原始圖片路徑或 Image 物件
            target_size: 目標大小 (width, height)
            maintain_aspect_ratio: 是否保持長寬比
            resample: 重採樣方法

        Returns:
            調整大小後的圖片路徑或 Image 物件
        """
        try:
            # 處理輸入
            if isinstance(image, str):
                image_obj = self.open_image(image)
                image_path = Path(image)
                return_path = True
            else:
                image_obj = image
                return_path = False

            if maintain_aspect_ratio:
                # 保持長寬比，使用 thumbnail 方法
                image_copy = image_obj.copy()
                image_copy.thumbnail(target_size, resample)
                result_image = image_copy
            else:
                # 直接調整到目標大小
                result_image = image_obj.resize(target_size, resample)

            # 如果輸入是路徑，則保存並返回路徑
            if return_path:
                output_filename = f"{image_path.stem}_resized_{target_size[0]}x{target_size[1]}{image_path.suffix}"
                output_path = self.output_dir / output_filename
                result_image.save(
                    output_path,
                    format=result_image.format or "JPEG",
                    quality=85,
                    optimize=True,
                )
                return str(output_path)
            else:
                return result_image

        except (OSError, ValueError) as e:
            logger.error(f"Error resizing image: {e}")
            raise ImageProcessorError(f"調整圖片大小失敗: {str(e)}") from e

    def create_thumbnail(
        self,
        image_path: str,
        size: str = "medium",
        custom_size: tuple[int, int] | None = None,
    ) -> str:
        """
        創建縮圖

        Args:
            image_path: 原始圖片路徑
            size: 縮圖大小 ('small', 'medium', 'large')
            custom_size: 自定義大小

        Returns:
            str: 縮圖路徑
        """
        try:
            # 確定目標大小
            if custom_size:
                target_size = custom_size
                size_name = f"{custom_size[0]}x{custom_size[1]}"
            else:
                target_size = THUMBNAIL_SIZES.get(size, THUMBNAIL_SIZES["medium"])
                size_name = size

            # 打開原始圖片
            image = self.open_image(image_path)

            # 調整大小
            thumbnail = self.resize_image(image, target_size)

            # 生成縮圖檔案名
            original_path = Path(image_path)
            thumbnail_filename = (
                f"{original_path.stem}_{size_name}{original_path.suffix}"
            )
            thumbnail_path = self.thumbnail_dir / thumbnail_filename

            # 儲存縮圖
            thumbnail.save(
                thumbnail_path, format=image.format, quality=85, optimize=True
            )

            logger.info(f"Thumbnail created: {thumbnail_path}")
            return str(thumbnail_path)

        except (OSError, ValueError, ImageProcessorError) as e:
            logger.error(f"Error creating thumbnail: {e}")
            raise ImageProcessorError(f"創建縮圖失敗: {str(e)}") from e

    def create_multiple_thumbnails(
        self, image_path: str, sizes: list[str] = None
    ) -> dict[str, str]:
        """
        創建多個不同大小的縮圖

        Args:
            image_path: 原始圖片路徑
            sizes: 縮圖大小列表

        Returns:
            Dict[str, str]: 縮圖大小對應路徑的字典
        """
        if sizes is None:
            sizes = ["small", "medium", "large"]
        thumbnails = {}

        for size in sizes:
            try:
                thumbnail_path = self.create_thumbnail(image_path, size)
                thumbnails[size] = thumbnail_path
            except (OSError, ValueError, ImageProcessorError) as e:
                logger.error(f"Error creating thumbnail {size}: {e}")
                thumbnails[size] = None

        return thumbnails


# 全域圖片處理器實例
image_processor = ImageProcessor()


def get_image_processor() -> ImageProcessor:
    """獲取圖片處理器實例"""
    return image_processor
