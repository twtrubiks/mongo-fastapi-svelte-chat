"""圖片處理工具"""

import base64
import logging
import os
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# 圖片格式配置
IMAGE_FORMATS = {
    "JPEG": {"extensions": [".jpg", ".jpeg"], "quality": 85, "optimize": True},
    "PNG": {"extensions": [".png"], "optimize": True},
    "WEBP": {"extensions": [".webp"], "quality": 85, "optimize": True},
    "GIF": {"extensions": [".gif"], "optimize": True},
}

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
        except Exception as e:
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
                                            )[
                                                :100
                                            ]  # 限制長度
                                        except Exception:
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
                                        except Exception:
                                            pass  # 跳過有問題的列表
                                    else:
                                        # 對於其他類型（包括IFDRational），安全地轉為字符串
                                        try:
                                            str_value = str(value)[
                                                :100
                                            ]  # 限制字符串長度
                                            exif_dict[decoded] = str_value
                                        except Exception:
                                            pass  # 跳過無法字符串化的對象
                                except Exception:
                                    # 完全跳過有問題的EXIF標籤
                                    continue
                except Exception:
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
        except Exception as e:
            # 安全地處理異常，避免IFDRational等對象泄漏到異常消息中
            error_msg = "無法獲取圖片資訊"
            try:
                # 嘗試安全地獲取錯誤信息
                if hasattr(e, "args") and e.args:
                    safe_args = []
                    for arg in e.args:
                        try:
                            safe_args.append(str(arg)[:200])  # 限制長度
                        except Exception:
                            safe_args.append("<無法序列化的錯誤參數>")
                    error_msg = f"無法獲取圖片資訊: {' '.join(safe_args)}"
                else:
                    error_msg = f"無法獲取圖片資訊: {type(e).__name__}"
            except Exception:
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

        except Exception as e:
            logger.error(f"Error resizing image: {e}")
            raise ImageProcessorError(f"調整圖片大小失敗: {str(e)}") from e

    def create_single_thumbnail(
        self, image_path: str, size: tuple[int, int], output_path: str | None = None
    ) -> str:
        """
        創建單個縮圖（向後兼容方法）

        Args:
            image_path: 原始圖片路徑
            size: 縮圖尺寸 (width, height)
            output_path: 輸出路徑（可選）

        Returns:
            str: 縮圖路徑
        """
        return self.create_thumbnail(image_path=image_path, custom_size=size)

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

        except Exception as e:
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
            except Exception as e:
                logger.error(f"Error creating thumbnail {size}: {e}")
                thumbnails[size] = None

        return thumbnails

    def compress_image(
        self,
        image_path: str,
        quality: int = 85,
        max_size: tuple[int, int] | None = None,
    ) -> str:
        """
        壓縮圖片

        Args:
            image_path: 原始圖片路徑
            quality: 壓縮品質 (1-100)
            max_size: 最大尺寸

        Returns:
            str: 壓縮後的圖片路徑
        """
        try:
            # 打開原始圖片
            image = self.open_image(image_path)

            # 如果指定了最大尺寸，先調整大小
            if max_size:
                image = self.resize_image(image, max_size)

            # 生成壓縮檔案名
            original_path = Path(image_path)
            compressed_filename = (
                f"{original_path.stem}_compressed{original_path.suffix}"
            )
            compressed_path = self.output_dir / compressed_filename

            # 儲存壓縮圖片
            image.save(compressed_path, format="JPEG", quality=quality, optimize=True)

            logger.info(f"Image compressed: {compressed_path}")
            return str(compressed_path)

        except Exception as e:
            logger.error(f"Error compressing image: {e}")
            raise ImageProcessorError(f"壓縮圖片失敗: {str(e)}") from e

    def crop_image(self, image_path: str, crop_box: tuple[int, int, int, int]) -> str:
        """
        裁剪圖片

        Args:
            image_path: 原始圖片路徑
            crop_box: 裁剪框 (left, top, right, bottom)

        Returns:
            str: 裁剪後的圖片路徑
        """
        try:
            # 打開原始圖片
            image = self.open_image(image_path)

            # 裁剪圖片
            cropped_image = image.crop(crop_box)

            # 生成裁剪檔案名
            original_path = Path(image_path)
            cropped_filename = f"{original_path.stem}_cropped{original_path.suffix}"
            cropped_path = self.output_dir / cropped_filename

            # 儲存裁剪圖片
            cropped_image.save(
                cropped_path, format=image.format, quality=85, optimize=True
            )

            logger.info(f"Image cropped: {cropped_path}")
            return str(cropped_path)

        except Exception as e:
            logger.error(f"Error cropping image: {e}")
            raise ImageProcessorError(f"裁剪圖片失敗: {str(e)}") from e

    def rotate_image(self, image_path: str, angle: float) -> str:
        """
        旋轉圖片

        Args:
            image_path: 原始圖片路徑
            angle: 旋轉角度

        Returns:
            str: 旋轉後的圖片路徑
        """
        try:
            # 打開原始圖片
            image = self.open_image(image_path)

            # 旋轉圖片
            rotated_image = image.rotate(angle, expand=True)

            # 生成旋轉檔案名
            original_path = Path(image_path)
            rotated_filename = f"{original_path.stem}_rotated{original_path.suffix}"
            rotated_path = self.output_dir / rotated_filename

            # 儲存旋轉圖片
            rotated_image.save(
                rotated_path, format=image.format, quality=85, optimize=True
            )

            logger.info(f"Image rotated: {rotated_path}")
            return str(rotated_path)

        except Exception as e:
            logger.error(f"Error rotating image: {e}")
            raise ImageProcessorError(f"旋轉圖片失敗: {str(e)}") from e

    def apply_filter(self, image_path: str, filter_type: str) -> str:
        """
        應用濾鏡

        Args:
            image_path: 原始圖片路徑
            filter_type: 濾鏡類型 ('blur', 'sharpen', 'smooth', 'emboss')

        Returns:
            str: 應用濾鏡後的圖片路徑
        """
        try:
            # 打開原始圖片
            image = self.open_image(image_path)

            # 應用濾鏡
            filter_map = {
                "blur": ImageFilter.BLUR,
                "sharpen": ImageFilter.SHARPEN,
                "smooth": ImageFilter.SMOOTH,
                "emboss": ImageFilter.EMBOSS,
            }

            if filter_type not in filter_map:
                raise ImageProcessorError(f"不支援的濾鏡類型: {filter_type}")

            filtered_image = image.filter(filter_map[filter_type])

            # 生成濾鏡檔案名
            original_path = Path(image_path)
            filtered_filename = (
                f"{original_path.stem}_{filter_type}{original_path.suffix}"
            )
            filtered_path = self.output_dir / filtered_filename

            # 儲存濾鏡圖片
            filtered_image.save(
                filtered_path, format=image.format, quality=85, optimize=True
            )

            logger.info(f"Filter applied: {filtered_path}")
            return str(filtered_path)

        except Exception as e:
            logger.error(f"Error applying filter: {e}")
            raise ImageProcessorError(f"應用濾鏡失敗: {str(e)}") from e

    def convert_format(self, image_path: str, target_format: str) -> str:
        """
        轉換圖片格式

        Args:
            image_path: 原始圖片路徑
            target_format: 目標格式 ('JPEG', 'PNG', 'WEBP')

        Returns:
            str: 轉換後的圖片路徑
        """
        try:
            # 打開原始圖片
            image = self.open_image(image_path)

            # 確認目標格式
            if target_format not in IMAGE_FORMATS:
                raise ImageProcessorError(f"不支援的圖片格式: {target_format}")

            # 生成新檔案名
            original_path = Path(image_path)
            new_extension = IMAGE_FORMATS[target_format]["extensions"][0]
            converted_filename = f"{original_path.stem}{new_extension}"
            converted_path = self.output_dir / converted_filename

            # 儲存轉換後的圖片
            save_kwargs = {
                "format": target_format,
                "optimize": IMAGE_FORMATS[target_format].get("optimize", True),
            }

            if "quality" in IMAGE_FORMATS[target_format]:
                save_kwargs["quality"] = IMAGE_FORMATS[target_format]["quality"]

            image.save(converted_path, **save_kwargs)

            logger.info(f"Format converted: {converted_path}")
            return str(converted_path)

        except Exception as e:
            logger.error(f"Error converting format: {e}")
            raise ImageProcessorError(f"轉換圖片格式失敗: {str(e)}") from e

    def image_to_base64(self, image_path: str) -> str:
        """
        將圖片轉換為 Base64 編碼

        Args:
            image_path: 圖片路徑

        Returns:
            str: Base64 編碼的圖片
        """
        try:
            with open(image_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

            # 獲取檔案擴展名以確定 MIME 類型
            file_ext = Path(image_path).suffix.lower()
            mime_type = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }.get(file_ext, "image/jpeg")

            return f"data:{mime_type};base64,{encoded_string}"

        except Exception as e:
            logger.error(f"Error converting image to base64: {e}")
            raise ImageProcessorError(f"轉換圖片為 Base64 失敗: {str(e)}") from e

    def base64_to_image(self, base64_string: str, output_path: str) -> str:
        """
        將 Base64 編碼轉換為圖片檔案

        Args:
            base64_string: Base64 編碼字串
            output_path: 輸出路徑

        Returns:
            str: 儲存的圖片路徑
        """
        try:
            # 移除 data URL 前綴（如果有）
            if base64_string.startswith("data:"):
                base64_string = base64_string.split(",")[1]

            # 解碼 Base64
            image_data = base64.b64decode(base64_string)

            # 儲存圖片
            with open(output_path, "wb") as f:
                f.write(image_data)

            logger.info(f"Base64 converted to image: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error converting base64 to image: {e}")
            raise ImageProcessorError(f"轉換 Base64 為圖片失敗: {str(e)}") from e

    def create_watermark(
        self,
        image_path: str,
        watermark_text: str,
        position: str = "bottom-right",
        opacity: float = 0.5,
    ) -> str:
        """
        添加浮水印

        Args:
            image_path: 原始圖片路徑
            watermark_text: 浮水印文字
            position: 浮水印位置
            opacity: 透明度

        Returns:
            str: 添加浮水印後的圖片路徑
        """
        try:
            from PIL import ImageDraw, ImageFont

            # 打開原始圖片
            image = self.open_image(image_path)

            # 創建透明覆蓋層
            overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)

            # 嘗試載入字體
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except Exception:
                font = ImageFont.load_default()

            # 計算文字大小
            text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # 計算位置
            margin = 20
            positions = {
                "top-left": (margin, margin),
                "top-right": (image.width - text_width - margin, margin),
                "bottom-left": (margin, image.height - text_height - margin),
                "bottom-right": (
                    image.width - text_width - margin,
                    image.height - text_height - margin,
                ),
                "center": (
                    (image.width - text_width) // 2,
                    (image.height - text_height) // 2,
                ),
            }

            text_position = positions.get(position, positions["bottom-right"])

            # 添加文字
            alpha = int(255 * opacity)
            draw.text(
                text_position, watermark_text, font=font, fill=(255, 255, 255, alpha)
            )

            # 合併圖片
            watermarked = Image.alpha_composite(image.convert("RGBA"), overlay)
            watermarked = watermarked.convert("RGB")

            # 生成浮水印檔案名
            original_path = Path(image_path)
            watermarked_filename = (
                f"{original_path.stem}_watermarked{original_path.suffix}"
            )
            watermarked_path = self.output_dir / watermarked_filename

            # 儲存浮水印圖片
            watermarked.save(watermarked_path, format="JPEG", quality=85, optimize=True)

            logger.info(f"Watermark added: {watermarked_path}")
            return str(watermarked_path)

        except Exception as e:
            logger.error(f"Error adding watermark: {e}")
            raise ImageProcessorError(f"添加浮水印失敗: {str(e)}") from e


# 全域圖片處理器實例
image_processor = ImageProcessor()


def get_image_processor() -> ImageProcessor:
    """獲取圖片處理器實例"""
    return image_processor


# 向後兼容的模組層級函數
def create_single_thumbnail(
    image_path: str, size: tuple[int, int], output_path: str | None = None
) -> str:
    """
    創建單個縮圖的模組層級函數（向後兼容）

    Args:
        image_path: 原始圖片路徑
        size: 縮圖尺寸 (width, height)
        output_path: 輸出路徑（可選）

    Returns:
        str: 縮圖路徑
    """
    processor = get_image_processor()
    return processor.create_single_thumbnail(image_path, size, output_path)
