"""Small grayscale previews drawn with Pillow, to exercise the paper detection without a scanner."""

import random
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw

PREVIEW_SIZE = (200, 280)
DARK_LID_LEVEL = 30
WHITE_LEVEL = 255
PAPER_LEVEL = 235


@dataclass(frozen=True)
class FilledRectangle:
    box: tuple[int, int, int, int]
    level: int


def build_preview(
    size: tuple[int, int] = PREVIEW_SIZE,
    background_level: int = DARK_LID_LEVEL,
    rectangles: Sequence[FilledRectangle] = (),
) -> Image.Image:
    """Rectangle boxes are inclusive on both ends, like ImageDraw: (left, top, right, bottom)."""
    preview = Image.new("L", size, background_level)
    drawing = ImageDraw.Draw(preview)
    for rectangle in rectangles:
        drawing.rectangle(rectangle.box, fill=rectangle.level)
    return preview


def build_horizontal_gradient(size: tuple[int, int]) -> Image.Image:
    width, height = size
    ramp = bytes(round(column * 255 / (width - 1)) for column in range(width))
    return Image.frombytes("L", size, ramp * height)


def add_noise(preview: Image.Image, amplitude: int, seed: int) -> Image.Image:
    generator = random.Random(seed)
    pixel_count = preview.width * preview.height
    shifted_noise = Image.frombytes(
        "L", preview.size, bytes(generator.randint(0, 2 * amplitude) for _ in range(pixel_count))
    )
    return ImageChops.add(preview, shifted_noise, scale=1, offset=-amplitude)
