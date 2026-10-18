"""One or two synthetic photos lying rotated on a white lid, for the fake scanner.

The photos are drawn shapes (a gradient and circles from a fixed seed), never real pictures. Each carries a magenta
block at its own top left corner and a green block at its own top right corner, so a test can tell whether a
cut-out came out upright. The scene is drawn small and enlarged to the size asked, so 1200 dots per inch stays cheap.
"""

import math
import random
from dataclasses import dataclass
from enum import Enum

from PIL import Image, ImageChops, ImageDraw

PHOTO_MARKER_SHARE = 0.18
LEFT_MARKER_COLOR = (230, 0, 230)
RIGHT_MARKER_COLOR = (0, 200, 0)
PHOTO_BORDER_SHARE = 0.01
PHOTO_BORDER_COLOR = (25, 25, 25)
PHOTO_CIRCLE_COUNT = 14
PHOTO_SEED_BASE = 1
LID_COLOR = (252, 252, 252)
LID_SHADING_LEVELS = 14
LEVEL_RANGE = 255
SCENE_DRAWING_WIDTH_PIXELS = 1275


class PhotoScene(str, Enum):
    SHEET = "sheet"  # the sheet of paper of the first simulator, see LidBackground
    PHOTOS_ONE = "photos_one"
    PHOTOS_TWO = "photos_two"


def parse_photo_scene(text: str | None) -> PhotoScene:
    """Absent or unknown text means the sheet of the first simulator."""
    try:
        return PhotoScene(text)
    except ValueError:
        return PhotoScene.SHEET


@dataclass(frozen=True)
class PhotoPlacement:
    """The centre as shares of the width (x) and of the height (y) of the glass; the size as shares of its width."""

    center_x: float
    center_y: float
    width: float
    height: float
    angle_degrees: float  # clockwise on the screen


PHOTO_PLACEMENTS_BY_SCENE: dict[PhotoScene, tuple[PhotoPlacement, ...]] = {
    PhotoScene.SHEET: (),
    PhotoScene.PHOTOS_ONE: (PhotoPlacement(0.50, 0.45, 0.62, 0.42, -30.0),),
    # The two 10 by 15 cm photos of the acceptance scene: the upper one turned about 30 degrees, the lower one upright.
    PhotoScene.PHOTOS_TWO: (
        PhotoPlacement(0.465, 0.30, 0.71, 0.48, -30.0),
        PhotoPlacement(0.535, 0.77, 0.71, 0.48, -2.0),
    ),
}


def _drawing_size(size_in_pixels: tuple[int, int]) -> tuple[int, int]:
    width, height = size_in_pixels
    if width <= SCENE_DRAWING_WIDTH_PIXELS:
        return size_in_pixels
    return SCENE_DRAWING_WIDTH_PIXELS, max(1, round(height * SCENE_DRAWING_WIDTH_PIXELS / width))


def _build_lid(size_in_pixels: tuple[int, int]) -> Image.Image:
    lid = Image.new("RGB", size_in_pixels, LID_COLOR)
    gradient = Image.linear_gradient("L").resize(size_in_pixels)
    shade = gradient.point(lambda level: LID_SHADING_LEVELS * level // LEVEL_RANGE)
    return ImageChops.subtract(lid, Image.merge("RGB", (shade, shade, shade)))


def _build_photo(size_in_pixels: tuple[int, int], seed: int) -> Image.Image:
    generator = random.Random(seed)
    width, height = size_in_pixels
    photo = Image.new("RGB", size_in_pixels)
    drawing = ImageDraw.Draw(photo)
    for row in range(height):
        shade = row / height
        drawing.line((0, row, width, row), fill=(int(60 + 120 * shade), int(110 + 60 * shade), int(190 - 100 * shade)))
    for _ in range(PHOTO_CIRCLE_COUNT):
        x, y = generator.randrange(width), generator.randrange(height)
        radius = generator.randrange(width // 20 + 2, width // 6 + 3)
        color = tuple(generator.randrange(20, 200) for _ in range(3))
        drawing.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    marker_edge = max(1, round(PHOTO_MARKER_SHARE * min(size_in_pixels)))
    drawing.rectangle((0, 0, marker_edge - 1, marker_edge - 1), fill=LEFT_MARKER_COLOR)
    drawing.rectangle((width - marker_edge, 0, width - 1, marker_edge - 1), fill=RIGHT_MARKER_COLOR)
    border = max(1, round(PHOTO_BORDER_SHARE * width))
    drawing.rectangle((0, 0, width - 1, height - 1), outline=PHOTO_BORDER_COLOR, width=border)
    return photo


def _paste_photo(lid: Image.Image, placement: PhotoPlacement, seed: int) -> None:
    lid_width, lid_height = lid.size
    photo_size = (max(1, round(placement.width * lid_width)), max(1, round(placement.height * lid_width)))
    photo = _build_photo(photo_size, seed)
    mask = Image.new("L", photo_size, LEVEL_RANGE)
    rotated_photo = photo.rotate(-placement.angle_degrees, expand=True, resample=Image.Resampling.BICUBIC)
    rotated_mask = mask.rotate(-placement.angle_degrees, expand=True, resample=Image.Resampling.BICUBIC)
    left = round(placement.center_x * lid_width - rotated_photo.width / 2)
    top = round(placement.center_y * lid_height - rotated_photo.height / 2)
    lid.paste(rotated_photo, (left, top), rotated_mask)


def photo_corners(placement: PhotoPlacement, size_in_pixels: tuple[int, int]) -> tuple[tuple[float, float], ...]:
    """The corners of the photo on the glass, in pixels: its top left, top right, bottom right and bottom left."""
    glass_width, glass_height = size_in_pixels
    angle = math.radians(placement.angle_degrees)
    half_width, half_height = placement.width * glass_width / 2, placement.height * glass_width / 2
    center_x, center_y = placement.center_x * glass_width, placement.center_y * glass_height
    offsets = (
        (-half_width, -half_height),
        (half_width, -half_height),
        (half_width, half_height),
        (-half_width, half_height),
    )
    return tuple(
        (
            center_x + offset_x * math.cos(angle) - offset_y * math.sin(angle),
            center_y + offset_x * math.sin(angle) + offset_y * math.cos(angle),
        )
        for offset_x, offset_y in offsets
    )


def build_photo_scene_image(size_in_pixels: tuple[int, int], scene: PhotoScene) -> Image.Image:
    """The glass with the photos of the scene on a white lid, as an RGB image of the size given."""
    drawing_size = _drawing_size(size_in_pixels)
    lid = _build_lid(drawing_size)
    for index, placement in enumerate(PHOTO_PLACEMENTS_BY_SCENE[scene]):
        _paste_photo(lid, placement, PHOTO_SEED_BASE + index)
    if drawing_size == size_in_pixels:
        return lid
    return lid.resize(size_in_pixels, Image.Resampling.BICUBIC)
