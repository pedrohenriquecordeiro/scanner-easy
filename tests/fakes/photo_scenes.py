"""Photos lying rotated on a white lid, drawn with Pillow: synthetic shapes with a known truth (the corners).

Each photo carries a red block at its own top-left corner, so a test can tell how a cut-out is turned.
"""

import io
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw

LID_COLOR = (252, 252, 252)
LID_SHADING_LEVELS = 14
MARKER_COLOR = (220, 20, 20)
MARKER_SHARE = 0.25
CIRCLES_PER_PHOTO = 14
SCENE_JPEG_QUALITY = 90
Point = tuple[float, float]


@dataclass(frozen=True)
class PlacedPhoto:
    """A photo of `size` (width, height) pixels, turned `angle_degrees` clockwise on the screen around `center`."""

    center: Point
    size: tuple[int, int]
    angle_degrees: float
    seed: int = 1


def photo_corners(placed_photo: PlacedPhoto) -> tuple[Point, Point, Point, Point]:
    """The corners of the photo on the canvas: top left, top right, bottom right, bottom left of the photo itself."""
    return rotated_rectangle_corners(placed_photo.center, placed_photo.size, placed_photo.angle_degrees)


def rotated_rectangle_corners(center: Point, size: tuple[int, int], angle_degrees: float) -> tuple[Point, ...]:
    width, height = size
    angle = math.radians(angle_degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    offsets = ((-width / 2, -height / 2), (width / 2, -height / 2), (width / 2, height / 2), (-width / 2, height / 2))
    return tuple(
        (center[0] + dx * cosine - dy * sine, center[1] + dx * sine + dy * cosine) for dx, dy in offsets
    )


def build_photo_image(size: tuple[int, int], seed: int) -> Image.Image:
    random_source = random.Random(seed)
    width, height = size
    photo = Image.new("RGB", size)
    drawing = ImageDraw.Draw(photo)
    for row in range(height):
        shade = row / height
        drawing.line((0, row, width, row), fill=(int(60 + 120 * shade), int(110 + 60 * shade), int(190 - 100 * shade)))
    for _ in range(CIRCLES_PER_PHOTO):
        x, y = random_source.randrange(width), random_source.randrange(height)
        radius = random_source.randrange(width // 20 + 2, width // 6 + 3)
        color = tuple(random_source.randrange(20, 200) for _ in range(3))
        drawing.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    marker_edge = round(MARKER_SHARE * min(size))
    drawing.rectangle((0, 0, marker_edge - 1, marker_edge - 1), fill=MARKER_COLOR)
    return photo


def build_lid(size: tuple[int, int], color: tuple[int, int, int] = LID_COLOR, shading: bool = True) -> Image.Image:
    """The lid: flat, or with the light vertical shading a closed white lid gives."""
    lid = Image.new("RGB", size, color)
    if not shading:
        return lid
    shade = Image.linear_gradient("L").resize(size).point(lambda level: LID_SHADING_LEVELS * level // 255)
    return ImageChops.subtract(lid, Image.merge("RGB", (shade, shade, shade)))


def paste_photo(canvas: Image.Image, placed_photo: PlacedPhoto) -> None:
    photo = build_photo_image(placed_photo.size, placed_photo.seed)
    mask = Image.new("L", placed_photo.size, 255)
    angle = -placed_photo.angle_degrees
    rotated_photo = photo.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    rotated_mask = mask.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    left = round(placed_photo.center[0] - rotated_photo.width / 2)
    top = round(placed_photo.center[1] - rotated_photo.height / 2)
    canvas.paste(rotated_photo, (left, top), rotated_mask)


def build_photo_scene(
    canvas_size: tuple[int, int], photos: Sequence[PlacedPhoto], lid: Image.Image | None = None
) -> Image.Image:
    canvas = build_lid(canvas_size) if lid is None else lid
    for placed_photo in photos:
        paste_photo(canvas, placed_photo)
    return canvas


def encode_jpeg(image: Image.Image, **save_options: object) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=SCENE_JPEG_QUALITY, **save_options)
    return buffer.getvalue()


def build_photo_scene_jpeg(
    canvas_size: tuple[int, int], photos: Sequence[PlacedPhoto], **save_options: object
) -> bytes:
    return encode_jpeg(build_photo_scene(canvas_size, photos), **save_options)
