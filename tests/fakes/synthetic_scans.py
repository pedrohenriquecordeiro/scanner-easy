"""JPEG scans drawn with Pillow: flat colour blocks survive JPEG compression well enough to be located by position."""

import io
from collections.abc import Sequence

from PIL import Image, ImageDraw

MARKER_COLOR = (220, 20, 20)
BACKGROUND_COLOR = (250, 250, 250)
SCAN_JPEG_QUALITY = 90


def build_scan_jpeg(
    size: tuple[int, int],
    boxes_and_colors: Sequence[tuple[tuple[int, int, int, int], tuple[int, int, int]]] = (),
    background: tuple[int, int, int] = BACKGROUND_COLOR,
    **save_options: object,
) -> bytes:
    """Boxes are inclusive on both ends, like ImageDraw, and painted in order over the background."""
    image = Image.new("RGB", size, background)
    drawing = ImageDraw.Draw(image)
    for box, color in boxes_and_colors:
        drawing.rectangle(box, fill=color)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=SCAN_JPEG_QUALITY, **save_options)
    return buffer.getvalue()


def build_marked_scan_jpeg(size: tuple[int, int], **save_options: object) -> bytes:
    """A light page with a red block in its top-left corner, asymmetric on purpose."""
    block_edge = min(size) // 4
    marker = ((0, 0, block_edge - 1, block_edge - 1), MARKER_COLOR)
    return build_scan_jpeg(size, [marker], **save_options)


def find_marker_corner(jpeg_content: bytes) -> str:
    """The corner of the image that holds the red block: top-left, top-right, bottom-left or bottom-right."""
    with Image.open(io.BytesIO(jpeg_content)) as image:
        rgb_image = image.convert("RGB")
    width, height = rgb_image.size
    inset = min(width, height) // 8
    corners = {
        "top-left": (inset, inset),
        "top-right": (width - 1 - inset, inset),
        "bottom-left": (inset, height - 1 - inset),
        "bottom-right": (width - 1 - inset, height - 1 - inset),
    }
    return max(corners, key=lambda corner: _redness(rgb_image.getpixel(corners[corner])))


def _redness(pixel: tuple[int, int, int]) -> int:
    red, green, blue = pixel
    return red - (green + blue) // 2


def read_jpeg_size(jpeg_content: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg_content)) as image:
        return image.size
