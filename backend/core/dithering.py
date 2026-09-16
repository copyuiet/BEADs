"""Floyd-Steinberg 误差扩散。"""

from __future__ import annotations

import numpy as np

from backend.core.color_mapper import ColorMapper, ColorMode, MappedImage, normalise_color_mode


def floyd_steinberg_dither(
    image: np.ndarray,
    mapper: ColorMapper,
    mode: ColorMode | str = ColorMode.LAB,
    active_mask: np.ndarray | None = None,
) -> MappedImage:
    """逐像素匹配颜色，并在 RGB 空间扩散量化误差。"""

    source = mapper._validate_image(image)
    color_mode = normalise_color_mode(mode)
    working = source.astype(np.float32, copy=True)
    height, width, _ = working.shape
    mask = mapper.normalise_active_mask(active_mask, (height, width))
    indices = np.zeros((height, width), dtype=np.int16)

    for row in range(height):
        for column in range(width):
            if not mask[row, column]:
                continue
            old_pixel = np.clip(working[row, column], 0.0, 255.0)
            color_index = mapper.nearest_index(old_pixel, color_mode)
            new_pixel = mapper.palette.rgb[color_index].astype(np.float32)
            indices[row, column] = color_index
            error = old_pixel - new_pixel

            if column + 1 < width and mask[row, column + 1]:
                working[row, column + 1] += error * (7.0 / 16.0)
            if row + 1 < height:
                if column > 0 and mask[row + 1, column - 1]:
                    working[row + 1, column - 1] += error * (3.0 / 16.0)
                if mask[row + 1, column]:
                    working[row + 1, column] += error * (5.0 / 16.0)
                if column + 1 < width and mask[row + 1, column + 1]:
                    working[row + 1, column + 1] += error * (1.0 / 16.0)

    return mapper.result_from_indices(indices, mask)


__all__ = ["floyd_steinberg_dither"]
