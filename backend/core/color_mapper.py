"""基于真实 MARD 色卡的 RGB/Lab 最近色匹配。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from typing import TypeAlias

import numpy as np
from numpy.typing import NDArray
from skimage.color import rgb2lab

from backend.data.palette import BeadColor, get_tier


RGBArray: TypeAlias = NDArray[np.uint8]
IndexArray: TypeAlias = NDArray[np.int16]


class PaletteError(ValueError):
    """色库配置或数据无效。"""


class ColorMappingError(ValueError):
    """输入图片或颜色匹配模式无效。"""


class ColorMode(str, Enum):
    LAB = "lab"
    RGB = "rgb"


@dataclass(frozen=True, slots=True)
class PaletteColor:
    code: str
    name: str | None
    hex: str
    rgb: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class PaletteSnapshot:
    key: str
    label: str
    tier: int
    colors: tuple[PaletteColor, ...]
    rgb: NDArray[np.float64]
    lab: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class MappedImage:
    palette: PaletteSnapshot
    indices: IndexArray
    codes: NDArray[np.str_]
    rgb: RGBArray
    active_mask: NDArray[np.bool_]


class PaletteRepository:
    """严格加载 Web 产品允许选择的 MARD 套装。"""

    _PALETTES: dict[str, tuple[int, str]] = {
        "mard_221": (221, "MARD 221色"),
        "mard_291": (291, "MARD 291色"),
    }

    def available(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {"key": key, "label": label, "color_count": tier}
            for key, (tier, label) in self._PALETTES.items()
        )

    @lru_cache(maxsize=2)
    def get(self, key: str) -> PaletteSnapshot:
        if key not in self._PALETTES:
            choices = ", ".join(self._PALETTES)
            raise PaletteError(f"不支持的颜色库：{key}；可选颜色库：{choices}")

        tier, label = self._PALETTES[key]
        source_colors = get_tier(tier)
        self._validate_source(source_colors, tier)

        colors = tuple(
            PaletteColor(
                code=color.code,
                name=None,
                hex=color.hex,
                rgb=(color.r, color.g, color.b),
            )
            for color in source_colors
        )
        rgb = np.asarray([color.rgb for color in colors], dtype=np.float64)
        lab = rgb2lab((rgb / 255.0).reshape(1, -1, 3), channel_axis=-1).reshape(-1, 3)
        rgb.setflags(write=False)
        lab.setflags(write=False)
        return PaletteSnapshot(key=key, label=label, tier=tier, colors=colors, rgb=rgb, lab=lab)

    @staticmethod
    def _validate_source(colors: list[BeadColor], expected_count: int) -> None:
        if len(colors) != expected_count:
            raise PaletteError(f"MARD {expected_count} 色库实际包含 {len(colors)} 个颜色")
        codes = [color.code for color in colors]
        if len(codes) != len(set(codes)):
            raise PaletteError("MARD 色库包含重复色号")
        for color in colors:
            expected_hex = f"#{color.r:02X}{color.g:02X}{color.b:02X}"
            if color.hex.upper() != expected_hex:
                raise PaletteError(f"色号 {color.code} 的 HEX 与 RGB 不一致")


def normalise_color_mode(mode: ColorMode | str) -> ColorMode:
    if isinstance(mode, ColorMode):
        return mode
    if isinstance(mode, str):
        try:
            return ColorMode(mode.strip().lower())
        except ValueError as exc:
            raise ColorMappingError("颜色算法必须是 lab 或 rgb") from exc
    raise ColorMappingError("颜色算法必须是字符串或 ColorMode")


class ColorMapper:
    """将 RGB 图片映射到某个确定的 MARD 色库。"""

    def __init__(self, palette: PaletteSnapshot, chunk_size: int = 512) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        self.palette = palette
        self.chunk_size = chunk_size

    def map_image(
        self,
        image: RGBArray,
        mode: ColorMode | str = ColorMode.LAB,
        active_mask: NDArray[np.bool_] | None = None,
    ) -> MappedImage:
        rgb_image = self._validate_image(image)
        color_mode = normalise_color_mode(mode)
        flat = rgb_image.reshape(-1, 3)
        indices = np.empty(flat.shape[0], dtype=np.int16)

        for start in range(0, flat.shape[0], self.chunk_size):
            end = min(flat.shape[0], start + self.chunk_size)
            indices[start:end] = self._nearest_indices(flat[start:end], color_mode)

        return self.result_from_indices(indices.reshape(rgb_image.shape[:2]), active_mask)

    def nearest_index(self, rgb: NDArray[np.floating] | tuple[float, float, float], mode: ColorMode | str) -> int:
        pixel = np.asarray(rgb, dtype=np.float64).reshape(1, 3)
        pixel = np.clip(pixel, 0.0, 255.0)
        color_mode = normalise_color_mode(mode)
        if color_mode is ColorMode.RGB:
            difference = self.palette.rgb - pixel[0]
        else:
            difference = self.palette.lab - _rgb_to_lab_fast(pixel)[0]
        distance = np.einsum("ki,ki->k", difference, difference)
        return int(np.argmin(distance))

    def result_from_indices(
        self,
        indices: NDArray[np.integer],
        active_mask: NDArray[np.bool_] | None = None,
    ) -> MappedImage:
        if indices.ndim != 2:
            raise ColorMappingError("颜色索引矩阵必须是二维数组")
        if indices.size and (int(indices.min()) < 0 or int(indices.max()) >= len(self.palette.colors)):
            raise ColorMappingError("颜色索引超出当前 MARD 色库范围")
        safe_indices = np.ascontiguousarray(indices, dtype=np.int16)
        safe_mask = self.normalise_active_mask(active_mask, safe_indices.shape)
        codes_lookup = np.asarray([color.code for color in self.palette.colors])
        rgb_lookup = np.asarray(self.palette.rgb, dtype=np.uint8)
        codes = codes_lookup[safe_indices].copy()
        mapped_rgb = np.ascontiguousarray(rgb_lookup[safe_indices])
        codes[~safe_mask] = ""
        mapped_rgb[~safe_mask] = 0
        return MappedImage(
            palette=self.palette,
            indices=safe_indices,
            codes=codes,
            rgb=mapped_rgb,
            active_mask=safe_mask,
        )

    @staticmethod
    def normalise_active_mask(
        active_mask: NDArray[np.bool_] | None,
        shape: tuple[int, int],
    ) -> NDArray[np.bool_]:
        if active_mask is None:
            return np.ones(shape, dtype=np.bool_)
        mask = np.asarray(active_mask, dtype=np.bool_)
        if mask.shape != shape:
            raise ColorMappingError("拼豆占用掩码尺寸必须与图片矩阵一致")
        return np.ascontiguousarray(mask)

    def _nearest_indices(self, pixels: NDArray[np.generic], mode: ColorMode) -> IndexArray:
        pixels_float = np.asarray(pixels, dtype=np.float64)
        if mode is ColorMode.RGB:
            difference = pixels_float[:, None, :] - self.palette.rgb[None, :, :]
            distance = np.einsum("nki,nki->nk", difference, difference)
        else:
            pixel_lab = rgb2lab(
                (pixels_float / 255.0).reshape(-1, 1, 3),
                channel_axis=-1,
            ).reshape(-1, 3)
            difference = pixel_lab[:, None, :] - self.palette.lab[None, :, :]
            # Delta E 1976：Lab 空间中的标准欧氏距离。比较平方值不会改变最小值。
            distance = np.einsum("nki,nki->nk", difference, difference)
        return np.argmin(distance, axis=1).astype(np.int16)

    @staticmethod
    def _validate_image(image: RGBArray) -> RGBArray:
        array = np.asarray(image)
        if array.ndim != 3 or array.shape[2] != 3:
            raise ColorMappingError("输入必须是形状为 (行, 列, 3) 的 RGB 数组")
        if array.size == 0:
            raise ColorMappingError("输入图片不能为空")
        if not np.issubdtype(array.dtype, np.number):
            raise ColorMappingError("RGB 数组必须包含数值")
        if not np.isfinite(array).all() or float(array.min()) < 0 or float(array.max()) > 255:
            raise ColorMappingError("RGB 数值必须位于 0 到 255")
        return np.ascontiguousarray(array, dtype=np.uint8)


default_palette_repository = PaletteRepository()


def _rgb_to_lab_fast(pixels: NDArray[np.float64]) -> NDArray[np.float64]:
    """低开销 sRGB→CIE Lab，用于误差扩散中的逐像素查询。"""

    srgb = np.asarray(pixels, dtype=np.float64) / 255.0
    linear = np.where(
        srgb <= 0.04045,
        srgb / 12.92,
        ((srgb + 0.055) / 1.055) ** 2.4,
    )
    transform = np.asarray(
        (
            (0.4124564, 0.3575761, 0.1804375),
            (0.2126729, 0.7151522, 0.0721750),
            (0.0193339, 0.1191920, 0.9503041),
        ),
        dtype=np.float64,
    )
    xyz = linear @ transform.T
    xyz /= np.asarray((0.95047, 1.0, 1.08883), dtype=np.float64)
    delta = 6.0 / 29.0
    adjusted = np.where(
        xyz > delta**3,
        np.cbrt(xyz),
        xyz / (3.0 * delta**2) + 4.0 / 29.0,
    )
    return np.column_stack(
        (
            116.0 * adjusted[:, 1] - 16.0,
            500.0 * (adjusted[:, 0] - adjusted[:, 1]),
            200.0 * (adjusted[:, 1] - adjusted[:, 2]),
        )
    )


__all__ = [
    "ColorMapper",
    "ColorMappingError",
    "ColorMode",
    "MappedImage",
    "PaletteColor",
    "PaletteError",
    "PaletteRepository",
    "PaletteSnapshot",
    "default_palette_repository",
    "normalise_color_mode",
]
