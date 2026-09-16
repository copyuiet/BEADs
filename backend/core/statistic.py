"""MARD 拼豆用量统计和 CSV 材料清单。"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import numpy as np

from backend.core.color_mapper import MappedImage


@dataclass(frozen=True, slots=True)
class ColorStatistic:
    code: str
    name: str | None
    hex: str
    rgb: tuple[int, int, int]
    count: int
    percentage: float


def calculate_statistics(mapped: MappedImage) -> list[ColorStatistic]:
    active_indices = mapped.indices[mapped.active_mask]
    total = int(active_indices.size)
    if total == 0:
        return []
    counts = np.bincount(active_indices, minlength=len(mapped.palette.colors))
    statistics = [
        ColorStatistic(
            code=color.code,
            name=color.name,
            hex=color.hex,
            rgb=color.rgb,
            count=int(counts[index]),
            percentage=round(float(counts[index]) * 100.0 / total, 4),
        )
        for index, color in enumerate(mapped.palette.colors)
        if counts[index] > 0
    ]
    return sorted(statistics, key=lambda item: (-item.count, item.code))


def statistics_to_csv(statistics: list[ColorStatistic]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["MARD色号", "HEX", "数量", "占比"])
    for item in statistics:
        writer.writerow([item.code, item.hex, item.count, f"{item.percentage:.2f}%"])
    return output.getvalue().encode("utf-8-sig")


__all__ = ["ColorStatistic", "calculate_statistics", "statistics_to_csv"]
