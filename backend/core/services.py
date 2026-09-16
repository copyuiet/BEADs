"""应用服务组合，便于 API 与测试使用同一套核心能力。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.core.auth import TokenManager
from backend.core.bead_generator import BeadPatternGenerator
from backend.core.color_mapper import PaletteRepository
from backend.core.database import Database
from backend.core.image_processor import ImageProcessor
from backend.core.storage import AssetStore


@dataclass(slots=True)
class ApplicationServices:
    store: AssetStore
    image_processor: ImageProcessor
    palettes: PaletteRepository
    generator: BeadPatternGenerator
    database: Database
    tokens: TokenManager

    @classmethod
    def create(cls, runtime_root: str | Path | None = None) -> "ApplicationServices":
        palettes = PaletteRepository()
        store = AssetStore(runtime_root)
        return cls(
            store=store,
            image_processor=ImageProcessor(),
            palettes=palettes,
            generator=BeadPatternGenerator(palettes),
            database=Database(store.root / "bead-generator.db"),
            tokens=TokenManager(store.root),
        )


__all__ = ["ApplicationServices"]
