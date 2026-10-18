"""A book lying on the glass with the lid open, drawn like the real scans of the calibration (2026-10-18).

The cover is white. Above and below it the glass shows a light grey gradient, on its right a dark shadow, and its
left side is blown out to white, so the left edge of the book cannot be seen in the middle rows.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw

WHITE_LEVEL = 255
TEXT_LEVEL = 70
SHADOW_NEAR_LEVEL = 100
SHADOW_FAR_LEVEL = 150
GLASS_NEAR_BOOK_LEVEL = 225
GLASS_FAR_FROM_BOOK_LEVEL = 190
BLOWN_OUT_TRANSITION_SHARE = 0.04
TEXT_ROW_PERIOD = 9
TEXT_ROW_HEIGHT = 2
TEXT_DASH_WIDTH = 3
TEXT_DASH_PERIOD = 8
TEXT_MARGIN_SHARE = 0.06
JPEG_QUALITY = 90


@dataclass(frozen=True)
class BookOnGlass:
    """The edges of the book as fractions of the image (left, top, right, bottom) and the size of the image."""

    left: float = 0.13
    top: float = 0.125
    right: float = 0.91
    bottom: float = 0.915
    size: tuple[int, int] = (291, 400)


DEFAULT_BOOK = BookOnGlass()


def _interpolate(level_from: int, level_to: int, share: float) -> int:
    return round(level_from + (level_to - level_from) * min(1.0, max(0.0, share)))


def _glass_level(row: int, book_rows: tuple[int, int], height: int) -> int:
    top_row, bottom_row = book_rows
    if row < top_row:
        return _interpolate(GLASS_FAR_FROM_BOOK_LEVEL, GLASS_NEAR_BOOK_LEVEL, row / max(top_row, 1))
    below_share = (row - bottom_row) / max(height - bottom_row, 1)
    return _interpolate(GLASS_NEAR_BOOK_LEVEL, GLASS_FAR_FROM_BOOK_LEVEL, below_share)


def build_book_on_glass_preview(book: BookOnGlass = DEFAULT_BOOK) -> Image.Image:
    width, height = book.size
    left_column, right_column = round(book.left * width), round(book.right * width)
    top_row, bottom_row = round(book.top * height), round(book.bottom * height)
    transition = max(2, round(BLOWN_OUT_TRANSITION_SHARE * width))
    image = Image.new("L", book.size, WHITE_LEVEL)
    pixels = image.load()
    for row in range(height):
        glass_level = _glass_level(row, (top_row, bottom_row), height)
        for column in range(left_column, width):
            blown_out_share = (column - left_column) / transition
            pixels[column, row] = _interpolate(WHITE_LEVEL, glass_level, blown_out_share)
    ImageDraw.Draw(image).rectangle((left_column, top_row, right_column - 1, bottom_row - 1), fill=WHITE_LEVEL)
    for column in range(right_column, width):
        shadow_share = (column - right_column) / max(width - right_column, 1)
        shadow_level = _interpolate(SHADOW_NEAR_LEVEL, SHADOW_FAR_LEVEL, shadow_share)
        for row in range(height):
            pixels[column, row] = shadow_level
    _draw_text_rows(image, (left_column, top_row, right_column, bottom_row))
    return image


def _draw_text_rows(image: Image.Image, book_box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = book_box
    margin = round(TEXT_MARGIN_SHARE * (right - left))
    drawing = ImageDraw.Draw(image)
    for row in range(top + margin, bottom - margin, TEXT_ROW_PERIOD):
        for dash_left in range(left + margin, right - margin, TEXT_DASH_PERIOD):
            dash = (dash_left, row, dash_left + TEXT_DASH_WIDTH - 1, row + TEXT_ROW_HEIGHT - 1)
            drawing.rectangle(dash, fill=TEXT_LEVEL)


def build_book_on_glass_jpeg(book: BookOnGlass = DEFAULT_BOOK, **save_options: object) -> bytes:
    buffer = io.BytesIO()
    preview = build_book_on_glass_preview(book)
    preview.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY, **save_options)
    return buffer.getvalue()
