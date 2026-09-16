"""图片读取、标准化、比例调整和网格降采样。

本模块不包含颜色匹配逻辑。输出始终是形状为 ``(行, 列, 3)`` 的
``numpy.uint8`` RGB 数组，可直接交给后续颜色映射模块。
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import BinaryIO, TypeAlias

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps, UnidentifiedImageError


SUPPORTED_GRID_SIZES: frozenset[int] = frozenset({52, 80, 104})
DEFAULT_BACKGROUND_RGB: tuple[int, int, int] = (255, 255, 255)

ImageSource: TypeAlias = bytes | bytearray | memoryview | BinaryIO | str | Path | Image.Image
RGBArray: TypeAlias = NDArray[np.uint8]


class ImageProcessingError(ValueError):
    """图片无法安全处理时抛出的基础异常。"""


class InvalidImageSourceError(ImageProcessingError):
    """图片来源为空、类型错误或无法读取。"""


class UnsupportedImageFormatError(ImageProcessingError):
    """图片实际编码格式不是 PNG 或 JPEG。"""


class ImageTooLargeError(ImageProcessingError):
    """图片文件大小或解码后的像素数量超过限制。"""


class InvalidGridSizeError(ImageProcessingError):
    """目标网格不是系统支持的标准规格。"""


class InvalidResizeModeError(ImageProcessingError):
    """图片比例处理模式无效。"""


class ResizeMode(str, Enum):
    """将原图放入正方形拼豆网格的方式。"""

    FIT_PAD = "fit_pad"
    CROP_FILL = "crop_fill"


@dataclass(frozen=True, slots=True)
class ImageProcessorConfig:
    """图片处理安全限制和默认背景配置。"""

    max_upload_bytes: int = 20 * 1024 * 1024
    max_image_pixels: int = 40_000_000
    background_rgb: tuple[int, int, int] = DEFAULT_BACKGROUND_RGB
    supported_formats: frozenset[str] = frozenset({"PNG", "JPEG"})

    def __post_init__(self) -> None:
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes 必须大于 0")
        if self.max_image_pixels <= 0:
            raise ValueError("max_image_pixels 必须大于 0")
        if len(self.background_rgb) != 3 or any(
            not isinstance(channel, int) or isinstance(channel, bool) or not 0 <= channel <= 255
            for channel in self.background_rgb
        ):
            raise ValueError("background_rgb 必须包含三个 0 到 255 的整数")


class ImageProcessor:
    """安全读取上传图片并生成标准拼豆网格 RGB 矩阵。"""

    def __init__(self, config: ImageProcessorConfig | None = None) -> None:
        self.config = config or ImageProcessorConfig()

    def load_image(self, source: ImageSource) -> Image.Image:
        """读取 PNG/JPEG 并返回完成方向修正和透明背景合成的 RGB 图片。

        已经解码的 :class:`PIL.Image.Image` 也可传入；这类输入没有文件格式，
        因而只进行尺寸检查、方向修正和 RGB 标准化。
        """

        if isinstance(source, Image.Image):
            return self._normalise_decoded_image(source.copy())

        payload = self._read_source_bytes(source)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(payload)) as probe:
                    image_format = (probe.format or "").upper()
                    if image_format not in self.config.supported_formats:
                        raise UnsupportedImageFormatError(
                            f"不支持的图片格式：{image_format or 'unknown'}；仅支持 PNG 和 JPEG"
                        )
                    self._validate_pixel_count(probe.width, probe.height)
                    probe.verify()

                with Image.open(io.BytesIO(payload)) as decoded:
                    self._validate_pixel_count(decoded.width, decoded.height)
                    return self._normalise_decoded_image(decoded)
        except (UnsupportedImageFormatError, ImageTooLargeError):
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageTooLargeError("图片像素数量超过 Pillow 安全限制") from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise InvalidImageSourceError("无法解码图片，文件可能已损坏") from exc

    def resize_to_grid(
        self,
        image: Image.Image,
        grid_size: int | str,
        mode: ResizeMode | str = ResizeMode.FIT_PAD,
    ) -> Image.Image:
        """按指定比例策略缩放为标准正方形网格图片。"""

        size = normalise_grid_size(grid_size)
        resize_mode = normalise_resize_mode(mode)
        rgb_image = self._normalise_decoded_image(image.copy())

        if resize_mode is ResizeMode.CROP_FILL:
            return ImageOps.fit(
                rgb_image,
                (size, size),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

        width, height = rgb_image.size
        scale = min(size / width, size / height)
        resized_width = min(size, max(1, round(width * scale)))
        resized_height = min(size, max(1, round(height * scale)))
        resized = rgb_image.resize(
            (resized_width, resized_height),
            resample=Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGB", (size, size), self.config.background_rgb)
        offset = ((size - resized_width) // 2, (size - resized_height) // 2)
        canvas.paste(resized, offset)
        return canvas

    def image_to_rgb_array(self, image: Image.Image) -> RGBArray:
        """将 PIL 图片转换为独立、连续的 uint8 RGB 数组。"""

        rgb_image = self._normalise_decoded_image(image.copy())
        return np.ascontiguousarray(np.asarray(rgb_image, dtype=np.uint8)).copy()

    def process(
        self,
        source: ImageSource,
        grid_size: int | str,
        mode: ResizeMode | str = ResizeMode.FIT_PAD,
        content_scale: float = 1.0,
    ) -> RGBArray:
        """完成读取、标准化、缩放和 RGB 数组转换。"""

        image = self.load_image(source)
        resized = self.resize_to_grid(image, grid_size, mode)
        scaled = self.scale_content_on_board(resized, content_scale)
        return self.image_to_rgb_array(scaled)

    def scale_content_on_board(self, image: Image.Image, content_scale: float) -> Image.Image:
        """缩放整幅图案在板中的占比，并将图案居中放置在白色板面。"""

        scale = normalise_content_scale(content_scale)
        rgb_image = self._normalise_decoded_image(image.copy())
        if rgb_image.width != rgb_image.height:
            raise InvalidImageSourceError("图案占板比例只能应用于正方形网格图片")
        if scale == 1.0:
            return rgb_image

        board_size = rgb_image.width
        offset, content_size = content_bounds(board_size, scale)
        content = rgb_image.resize(
            (content_size, content_size),
            resample=Image.Resampling.LANCZOS,
        )
        board = Image.new("RGB", (board_size, board_size), self.config.background_rgb)
        board.paste(content, (offset, offset))
        return board

    def _read_source_bytes(
        self,
        source: bytes | bytearray | memoryview | BinaryIO | str | Path,
    ) -> bytes:
        if isinstance(source, (bytes, bytearray, memoryview)):
            payload = bytes(source)
        elif isinstance(source, (str, Path)):
            path = Path(source)
            try:
                if path.stat().st_size > self.config.max_upload_bytes:
                    raise ImageTooLargeError(
                        f"图片文件不能超过 {self.config.max_upload_bytes} 字节"
                    )
                payload = path.read_bytes()
            except ImageTooLargeError:
                raise
            except OSError as exc:
                raise InvalidImageSourceError(f"无法读取图片文件：{path}") from exc
        elif hasattr(source, "read"):
            try:
                payload = source.read(self.config.max_upload_bytes + 1)
            except (OSError, ValueError) as exc:
                raise InvalidImageSourceError("无法读取图片数据流") from exc
            if not isinstance(payload, bytes):
                raise InvalidImageSourceError("图片数据流必须返回 bytes")
        else:
            raise InvalidImageSourceError("图片来源必须是字节、文件路径、二进制流或 PIL 图片")

        if not payload:
            raise InvalidImageSourceError("图片内容不能为空")
        if len(payload) > self.config.max_upload_bytes:
            raise ImageTooLargeError(f"图片文件不能超过 {self.config.max_upload_bytes} 字节")
        return payload

    def _normalise_decoded_image(self, image: Image.Image) -> Image.Image:
        self._validate_pixel_count(image.width, image.height)
        transposed = ImageOps.exif_transpose(image)

        has_alpha = transposed.mode in {"RGBA", "LA"} or (
            transposed.mode == "P" and "transparency" in transposed.info
        )
        if not has_alpha:
            return transposed.convert("RGB")

        rgba = transposed.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (*self.config.background_rgb, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")

    def _validate_pixel_count(self, width: int, height: int) -> None:
        if width <= 0 or height <= 0:
            raise InvalidImageSourceError("图片宽度和高度必须大于 0")
        if width * height > self.config.max_image_pixels:
            raise ImageTooLargeError(
                f"图片像素数量不能超过 {self.config.max_image_pixels}"
            )


def normalise_grid_size(grid_size: int | str) -> int:
    """将 ``52`` 或 ``52x52`` 转换为受支持的边长。"""

    value: int
    if isinstance(grid_size, bool):
        raise InvalidGridSizeError("图纸规格无效")
    if isinstance(grid_size, int):
        value = grid_size
    elif isinstance(grid_size, str):
        parts = grid_size.strip().lower().replace("×", "x").split("x")
        if len(parts) != 2 or parts[0] != parts[1] or not parts[0].isdigit():
            raise InvalidGridSizeError(f"无效图纸规格：{grid_size}")
        value = int(parts[0])
    else:
        raise InvalidGridSizeError("图纸规格必须是整数或 NxN 字符串")

    if value not in SUPPORTED_GRID_SIZES:
        supported = ", ".join(f"{item}x{item}" for item in sorted(SUPPORTED_GRID_SIZES))
        raise InvalidGridSizeError(f"不支持的图纸规格：{grid_size}；可选规格：{supported}")
    return value


def normalise_resize_mode(mode: ResizeMode | str) -> ResizeMode:
    """校验并标准化比例处理模式。"""

    if isinstance(mode, ResizeMode):
        return mode
    if isinstance(mode, str):
        try:
            return ResizeMode(mode.strip().lower())
        except ValueError as exc:
            raise InvalidResizeModeError(
                f"无效比例模式：{mode}；可选模式：fit_pad、crop_fill"
            ) from exc
    raise InvalidResizeModeError("比例模式必须是字符串或 ResizeMode")


def normalise_content_scale(content_scale: float) -> float:
    """校验图案在板中的边长占比。"""

    if isinstance(content_scale, bool) or not isinstance(content_scale, (int, float)):
        raise ImageProcessingError("图案占板比例必须是数值")
    value = float(content_scale)
    if not 0.2 <= value <= 1.0:
        raise ImageProcessingError("图案占板比例必须位于 20% 到 100%")
    return value


def content_bounds(board_size: int, content_scale: float) -> tuple[int, int]:
    """返回居中图案的起始格和边长。"""

    scale = normalise_content_scale(content_scale)
    content_size = max(1, min(board_size, round(board_size * scale)))
    return (board_size - content_size) // 2, content_size


def create_content_mask(grid_size: int | str, content_scale: float) -> NDArray[np.bool_]:
    """创建图案占用格掩码；掩码外的格子代表不放拼豆。"""

    board_size = normalise_grid_size(grid_size)
    offset, content_size = content_bounds(board_size, content_scale)
    mask = np.zeros((board_size, board_size), dtype=np.bool_)
    mask[offset : offset + content_size, offset : offset + content_size] = True
    return mask


default_image_processor = ImageProcessor()


def process_image(
    source: ImageSource,
    grid_size: int | str,
    mode: ResizeMode | str = ResizeMode.FIT_PAD,
    content_scale: float = 1.0,
) -> RGBArray:
    """使用默认配置生成标准拼豆网格 RGB 矩阵。"""

    return default_image_processor.process(source, grid_size, mode, content_scale)


__all__ = [
    "DEFAULT_BACKGROUND_RGB",
    "SUPPORTED_GRID_SIZES",
    "ImageProcessingError",
    "ImageProcessor",
    "ImageProcessorConfig",
    "ImageTooLargeError",
    "InvalidGridSizeError",
    "InvalidImageSourceError",
    "InvalidResizeModeError",
    "ResizeMode",
    "UnsupportedImageFormatError",
    "content_bounds",
    "create_content_mask",
    "normalise_grid_size",
    "normalise_content_scale",
    "normalise_resize_mode",
    "process_image",
]
