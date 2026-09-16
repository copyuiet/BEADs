"""图片处理模块测试。"""

from __future__ import annotations

import io
import unittest

import numpy as np
from PIL import Image

from backend.core.image_processor import (
    ImageProcessingError,
    ImageProcessor,
    ImageProcessorConfig,
    ImageTooLargeError,
    InvalidGridSizeError,
    InvalidImageSourceError,
    InvalidResizeModeError,
    ResizeMode,
    UnsupportedImageFormatError,
    create_content_mask,
    normalise_grid_size,
)


def encode_image(image: Image.Image, image_format: str) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


class ImageProcessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.processor = ImageProcessor()

    def test_png_is_loaded_as_rgb(self) -> None:
        payload = encode_image(Image.new("RGB", (3, 2), (12, 34, 56)), "PNG")

        result = self.processor.load_image(payload)

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (3, 2))
        self.assertEqual(result.getpixel((0, 0)), (12, 34, 56))

    def test_jpeg_is_accepted(self) -> None:
        payload = encode_image(Image.new("RGB", (4, 3), (120, 80, 40)), "JPEG")

        result = self.processor.load_image(io.BytesIO(payload))

        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.size, (4, 3))

    def test_transparent_png_is_composited_on_white(self) -> None:
        image = Image.new("RGBA", (1, 1), (255, 0, 0, 0))

        result = self.processor.load_image(encode_image(image, "PNG"))

        self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))

    def test_fit_pad_preserves_ratio_and_adds_white_margin(self) -> None:
        image = Image.new("RGB", (4, 2), (200, 10, 20))

        result = self.processor.resize_to_grid(image, 52, ResizeMode.FIT_PAD)

        self.assertEqual(result.size, (52, 52))
        self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(result.getpixel((26, 26)), (200, 10, 20))

    def test_crop_fill_fills_grid_without_padding(self) -> None:
        image = Image.new("RGB", (4, 2), (200, 10, 20))

        result = self.processor.resize_to_grid(image, "52x52", ResizeMode.CROP_FILL)

        self.assertEqual(result.size, (52, 52))
        self.assertEqual(result.getpixel((0, 0)), (200, 10, 20))

    def test_all_grid_sizes_produce_uint8_rgb_matrices(self) -> None:
        payload = encode_image(Image.new("RGB", (13, 7), (1, 2, 3)), "PNG")

        for size in (52, 80, 104):
            with self.subTest(size=size):
                result = self.processor.process(payload, f"{size}x{size}", "crop_fill")
                self.assertEqual(result.shape, (size, size, 3))
                self.assertEqual(result.dtype, np.uint8)
                self.assertTrue(result.flags.c_contiguous)

    def test_grid_size_accepts_multiplication_symbol(self) -> None:
        self.assertEqual(normalise_grid_size("80×80"), 80)

    def test_invalid_grid_size_is_rejected(self) -> None:
        with self.assertRaises(InvalidGridSizeError):
            self.processor.process(Image.new("RGB", (2, 2)), "60x60")

    def test_invalid_resize_mode_is_rejected(self) -> None:
        with self.assertRaises(InvalidResizeModeError):
            self.processor.resize_to_grid(Image.new("RGB", (2, 2)), 52, "stretch")

    def test_content_scale_centres_smaller_pattern_on_white_board(self) -> None:
        image = Image.new("RGB", (4, 4), (200, 10, 20))

        result = self.processor.process(image, "52x52", "crop_fill", 0.5)

        self.assertEqual(result.shape, (52, 52, 3))
        np.testing.assert_array_equal(result[0, 0], (255, 255, 255))
        np.testing.assert_array_equal(result[26, 26], (200, 10, 20))
        mask = create_content_mask("52x52", 0.5)
        self.assertEqual(int(mask.sum()), 26 * 26)
        self.assertFalse(bool(mask[0, 0]))
        self.assertTrue(bool(mask[26, 26]))

    def test_invalid_content_scale_is_rejected(self) -> None:
        with self.assertRaises(ImageProcessingError):
            self.processor.process(Image.new("RGB", (2, 2)), "52x52", "crop_fill", 0.1)

    def test_gif_is_rejected_even_when_content_is_valid_image(self) -> None:
        payload = encode_image(Image.new("RGB", (2, 2)), "GIF")

        with self.assertRaises(UnsupportedImageFormatError):
            self.processor.load_image(payload)

    def test_empty_and_corrupt_inputs_are_rejected(self) -> None:
        with self.assertRaises(InvalidImageSourceError):
            self.processor.load_image(b"")
        with self.assertRaises(InvalidImageSourceError):
            self.processor.load_image(b"not-an-image")

    def test_file_size_limit_is_enforced(self) -> None:
        processor = ImageProcessor(ImageProcessorConfig(max_upload_bytes=4))

        with self.assertRaises(ImageTooLargeError):
            processor.load_image(b"12345")

    def test_decoded_pixel_limit_is_enforced(self) -> None:
        processor = ImageProcessor(ImageProcessorConfig(max_image_pixels=3))

        with self.assertRaises(ImageTooLargeError):
            processor.load_image(Image.new("RGB", (2, 2)))


if __name__ == "__main__":
    unittest.main()
