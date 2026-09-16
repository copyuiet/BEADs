"""拼豆矩阵生成和两类 PNG 图纸渲染。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.core.color_mapper import (
    ColorMapper,
    ColorMode,
    MappedImage,
    PaletteRepository,
    default_palette_repository,
)
from backend.core.dithering import floyd_steinberg_dither


@dataclass(frozen=True, slots=True)
class BeadSpecification:
    key: str
    columns: int
    rows: int
    bead_count: int
    width_mm: float
    height_mm: float


SPECIFICATIONS: dict[str, BeadSpecification] = {
    "52x52": BeadSpecification("52x52", 52, 52, 2_704, 135.2, 135.2),
    "80x80": BeadSpecification("80x80", 80, 80, 6_400, 208.0, 208.0),
    "104x104": BeadSpecification("104x104", 104, 104, 10_816, 270.4, 270.4),
}


@dataclass(frozen=True, slots=True)
class PatternResult:
    specification: BeadSpecification
    mapped: MappedImage
    color_pattern: Image.Image
    number_pattern: Image.Image


class BeadGeneratorError(ValueError):
    """拼豆规格或输入矩阵无效。"""


class BeadPatternGenerator:
    def __init__(self, repository: PaletteRepository | None = None) -> None:
        self.repository = repository or default_palette_repository

    def generate(
        self,
        image: np.ndarray,
        size: str,
        palette_key: str,
        color_mode: ColorMode | str = ColorMode.LAB,
        dithering: bool = False,
        active_mask: np.ndarray | None = None,
    ) -> PatternResult:
        specification = get_specification(size)
        if image.shape[:2] != (specification.rows, specification.columns):
            raise BeadGeneratorError(
                f"输入矩阵必须为 {specification.rows}x{specification.columns}"
            )

        mapper = ColorMapper(self.repository.get(palette_key))
        mask = mapper.normalise_active_mask(active_mask, image.shape[:2])
        mapped = (
            floyd_steinberg_dither(image, mapper, color_mode, mask)
            if dithering
            else mapper.map_image(image, color_mode, mask)
        )
        return PatternResult(
            specification=specification,
            mapped=mapped,
            color_pattern=render_color_pattern(mapped.rgb, mapped.active_mask),
            number_pattern=render_number_pattern(mapped.rgb, mapped.codes, mapped.active_mask),
        )


def get_specification(size: str) -> BeadSpecification:
    try:
        return SPECIFICATIONS[size.strip().lower().replace("×", "x")]
    except (AttributeError, KeyError) as exc:
        raise BeadGeneratorError("图纸规格必须是 52x52、80x80 或 104x104") from exc


def render_color_pattern(
    rgb: np.ndarray,
    active_mask: np.ndarray | None = None,
    cell_pixels: int = 14,
) -> Image.Image:
    height, width, channels = rgb.shape
    if channels != 3 or cell_pixels < 2:
        raise BeadGeneratorError("色块矩阵或单元格尺寸无效")
    mask = ColorMapper.normalise_active_mask(active_mask, (height, width))
    ruler_pixels = _ruler_size(cell_pixels)
    canvas = Image.new(
        "RGBA",
        (ruler_pixels + width * cell_pixels + 1, ruler_pixels + height * cell_pixels + 1),
        (255, 255, 255, 0),
    )
    draw = ImageDraw.Draw(canvas)
    for row in range(height):
        for column in range(width):
            if not mask[row, column]:
                continue
            color = tuple(int(value) for value in rgb[row, column])
            left = ruler_pixels + column * cell_pixels
            top = ruler_pixels + row * cell_pixels
            draw.rectangle((left, top, left + cell_pixels - 1, top + cell_pixels - 1), fill=(*color, 255))
    _draw_grid(draw, width, height, cell_pixels, ruler_pixels, ruler_pixels)
    _draw_rulers(draw, width, height, cell_pixels, ruler_pixels)
    return canvas


def render_number_pattern(
    rgb: np.ndarray,
    codes: np.ndarray,
    active_mask: np.ndarray | None = None,
    cell_pixels: int = 36,
) -> Image.Image:
    height, width, channels = rgb.shape
    if channels != 3 or codes.shape != (height, width) or cell_pixels < 16:
        raise BeadGeneratorError("标注图矩阵或单元格尺寸无效")
    mask = ColorMapper.normalise_active_mask(active_mask, (height, width))
    ruler_pixels = _ruler_size(cell_pixels)
    canvas = Image.new(
        "RGBA",
        (ruler_pixels + width * cell_pixels + 1, ruler_pixels + height * cell_pixels + 1),
        (255, 255, 255, 0),
    )
    draw = ImageDraw.Draw(canvas)
    font = _load_font(max(9, round(cell_pixels * 0.31)))

    for row in range(height):
        for column in range(width):
            if not mask[row, column]:
                continue
            color = tuple(int(value) for value in rgb[row, column])
            left = ruler_pixels + column * cell_pixels
            top = ruler_pixels + row * cell_pixels
            draw.rectangle((left, top, left + cell_pixels - 1, top + cell_pixels - 1), fill=(*color, 255))
            code = str(codes[row, column])
            text_color = (15, 23, 42) if _relative_luminance(color) > 0.46 else (255, 255, 255)
            box = draw.textbbox((0, 0), code, font=font)
            text_width = box[2] - box[0]
            text_height = box[3] - box[1]
            draw.text(
                (left + (cell_pixels - text_width) / 2, top + (cell_pixels - text_height) / 2 - box[1]),
                code,
                fill=(*text_color, 255),
                font=font,
            )
    _draw_grid(draw, width, height, cell_pixels, ruler_pixels, ruler_pixels)
    _draw_rulers(draw, width, height, cell_pixels, ruler_pixels)
    return canvas


def _draw_grid(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    cell_pixels: int,
    origin_x: int,
    origin_y: int,
) -> None:
    for column in range(width + 1):
        coordinate = origin_x + column * cell_pixels
        major = column % 10 == 0
        draw.line(
            (coordinate, origin_y, coordinate, origin_y + height * cell_pixels),
            fill=(30, 41, 59, 220) if major else (100, 116, 139, 150),
            width=2 if major else 1,
        )
    for row in range(height + 1):
        coordinate = origin_y + row * cell_pixels
        major = row % 10 == 0
        draw.line(
            (origin_x, coordinate, origin_x + width * cell_pixels, coordinate),
            fill=(30, 41, 59, 220) if major else (100, 116, 139, 150),
            width=2 if major else 1,
        )


def _draw_rulers(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    cell_pixels: int,
    ruler_pixels: int,
) -> None:
    """在图纸顶部和左侧绘制从 1 开始的行列坐标标尺。"""

    pattern_width = width * cell_pixels
    pattern_height = height * cell_pixels
    background = (241, 245, 249, 255)
    border = (51, 65, 85, 255)
    tick = (100, 116, 139, 255)
    draw.rectangle((ruler_pixels, 0, ruler_pixels + pattern_width, ruler_pixels - 1), fill=background)
    draw.rectangle((0, ruler_pixels, ruler_pixels - 1, ruler_pixels + pattern_height), fill=background)
    draw.rectangle((0, 0, ruler_pixels - 1, ruler_pixels - 1), fill=(226, 232, 240, 255))

    for column in range(width + 1):
        x = ruler_pixels + column * cell_pixels
        length = 9 if column % 10 == 0 else 6 if column % 5 == 0 else 3
        draw.line((x, ruler_pixels - length, x, ruler_pixels), fill=border if length == 9 else tick)
    for row in range(height + 1):
        y = ruler_pixels + row * cell_pixels
        length = 9 if row % 10 == 0 else 6 if row % 5 == 0 else 3
        draw.line((ruler_pixels - length, y, ruler_pixels, y), fill=border if length == 9 else tick)

    font = _load_font(max(7, min(11, round(cell_pixels * 0.55))))
    for column in _ruler_label_indices(width):
        label = str(column + 1)
        box = draw.textbbox((0, 0), label, font=font)
        label_width = box[2] - box[0]
        x = ruler_pixels + (column + 0.5) * cell_pixels - label_width / 2
        draw.text((x, 3 - box[1]), label, fill=border, font=font)
    for row in _ruler_label_indices(height):
        label = str(row + 1)
        box = draw.textbbox((0, 0), label, font=font)
        label_width = box[2] - box[0]
        label_height = box[3] - box[1]
        x = ruler_pixels - 11 - label_width
        y = ruler_pixels + (row + 0.5) * cell_pixels - label_height / 2 - box[1]
        draw.text((max(2, x), y), label, fill=border, font=font)

    draw.line((ruler_pixels, 0, ruler_pixels, ruler_pixels + pattern_height), fill=border, width=1)
    draw.line((0, ruler_pixels, ruler_pixels + pattern_width, ruler_pixels), fill=border, width=1)


def _ruler_size(cell_pixels: int) -> int:
    return max(32, cell_pixels)


def _ruler_label_indices(count: int) -> list[int]:
    return sorted({0, count - 1, *range(4, count, 5)})


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        channel = value / 255.0
        channels.append(channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


__all__ = [
    "BeadPatternGenerator",
    "BeadSpecification",
    "PatternResult",
    "SPECIFICATIONS",
    "get_specification",
    "render_color_pattern",
    "render_number_pattern",
]
