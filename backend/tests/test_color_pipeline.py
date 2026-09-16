"""颜色匹配、抖动、图纸、统计及 PDF 测试。"""

from __future__ import annotations

import unittest

import numpy as np

from backend.core.bead_generator import BeadPatternGenerator, get_specification
from backend.core.color_mapper import ColorMapper, PaletteError, PaletteRepository
from backend.core.dithering import floyd_steinberg_dither
from backend.core.pdf_exporter import build_pattern_pdf
from backend.core.statistic import calculate_statistics, statistics_to_csv


class ColorPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = PaletteRepository()

    def test_only_supported_real_palettes_can_be_loaded(self) -> None:
        self.assertEqual(len(self.repository.get("mard_221").colors), 221)
        self.assertEqual(len(self.repository.get("mard_291").colors), 291)
        with self.assertRaises(PaletteError):
            self.repository.get("mard_999")

    def test_palette_color_maps_to_its_own_code_in_both_modes(self) -> None:
        palette = self.repository.get("mard_221")
        mapper = ColorMapper(palette)
        source = np.asarray([[palette.colors[20].rgb]], dtype=np.uint8)

        self.assertEqual(mapper.map_image(source, "rgb").codes[0, 0], palette.colors[20].code)
        self.assertEqual(mapper.map_image(source, "lab").codes[0, 0], palette.colors[20].code)

    def test_duplicate_rgb_tie_preserves_source_order(self) -> None:
        palette = self.repository.get("mard_291")
        mapper = ColorMapper(palette)
        q4 = next(color for color in palette.colors if color.code == "Q4")

        result = mapper.map_image(np.asarray([[q4.rgb]], dtype=np.uint8), "lab")

        self.assertEqual(result.codes[0, 0], "Q4")

    def test_fast_scalar_lab_matching_agrees_with_batch_matching(self) -> None:
        palette = self.repository.get("mard_291")
        mapper = ColorMapper(palette)
        random = np.random.default_rng(20260904)
        pixels = random.integers(0, 256, size=(8, 8, 3), dtype=np.uint8)
        batch = mapper.map_image(pixels, "lab").indices.reshape(-1)
        scalar = np.asarray(
            [mapper.nearest_index(pixel, "lab") for pixel in pixels.reshape(-1, 3)]
        )

        np.testing.assert_array_equal(scalar, batch)

    def test_dithering_returns_only_selected_palette_indices(self) -> None:
        palette = self.repository.get("mard_221")
        mapper = ColorMapper(palette)
        gradient = np.linspace(0, 255, 8, dtype=np.uint8)
        image = np.stack(np.meshgrid(gradient, gradient), axis=-1)
        image = np.concatenate([image, image[:, :, :1]], axis=2)

        result = floyd_steinberg_dither(image, mapper, "rgb")

        self.assertEqual(result.indices.shape, (8, 8))
        self.assertLess(int(result.indices.max()), 221)

    def test_pattern_generation_statistics_csv_and_pdf(self) -> None:
        palette = self.repository.get("mard_221")
        source = np.full((52, 52, 3), palette.colors[0].rgb, dtype=np.uint8)
        result = BeadPatternGenerator(self.repository).generate(
            source, "52x52", "mard_221", "lab", False
        )
        statistics = calculate_statistics(result.mapped)
        csv_payload = statistics_to_csv(statistics)
        pdf_payload = build_pattern_pdf(result, statistics)

        self.assertEqual(result.color_pattern.size, (761, 761))
        self.assertEqual(result.number_pattern.size, (1909, 1909))
        self.assertEqual(len(statistics), 1)
        self.assertEqual(statistics[0].count, 2_704)
        self.assertAlmostEqual(statistics[0].percentage, 100.0)
        self.assertTrue(csv_payload.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(
            csv_payload.decode("utf-8-sig").splitlines()[0],
            "MARD色号,HEX,数量,占比",
        )
        self.assertTrue(pdf_payload.startswith(b"%PDF"))
        self.assertGreater(len(pdf_payload), 10_000)

    def test_inactive_board_cells_are_transparent_and_not_counted(self) -> None:
        palette = self.repository.get("mard_221")
        source = np.full((52, 52, 3), palette.colors[0].rgb, dtype=np.uint8)
        mask = np.zeros((52, 52), dtype=np.bool_)
        mask[13:39, 13:39] = True

        result = BeadPatternGenerator(self.repository).generate(
            source, "52x52", "mard_221", "lab", False, mask
        )
        statistics = calculate_statistics(result.mapped)

        self.assertEqual(sum(item.count for item in statistics), 26 * 26)
        self.assertEqual(result.mapped.codes[0, 0], "")
        self.assertEqual(result.color_pattern.mode, "RGBA")
        self.assertEqual(result.color_pattern.getpixel((7, 7))[3], 255)
        self.assertEqual(result.color_pattern.getpixel((32 + 7, 32 + 7))[3], 0)
        self.assertEqual(
            result.color_pattern.getpixel((32 + 26 * 14 + 7, 32 + 26 * 14 + 7))[3],
            255,
        )

    def test_specifications_match_physical_requirements(self) -> None:
        expected = {
            "52x52": (2_704, 135.2),
            "80x80": (6_400, 208.0),
            "104x104": (10_816, 270.4),
        }
        for key, (count, millimetres) in expected.items():
            with self.subTest(key=key):
                specification = get_specification(key)
                self.assertEqual(specification.bead_count, count)
                self.assertEqual(specification.width_mm, millimetres)
                self.assertEqual(specification.height_mm, millimetres)


if __name__ == "__main__":
    unittest.main()
