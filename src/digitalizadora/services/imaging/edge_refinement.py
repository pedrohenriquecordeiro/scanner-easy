"""Moves the sides of a coarse frame onto the true edge of the photo, on a luminance image of the page.

The coarse frame comes from a small preview whose noise cleaning swells the region, so its sides sit a few pixels
outside the photo. For each side, several profiles are read across it, from the lid outside towards the photo inside;
where a profile leaves the level of the lid is the edge, and the median of the profiles is where the side goes.
A side whose profiles do not agree (low contrast, the page boundary, clutter) keeps its coarse position.
"""

import math
import statistics
from dataclasses import dataclass

from PIL import Image

from digitalizadora.services.imaging.photo_region_detection import Corners, Point

PROFILE_POSITIONS = 9
FIRST_PROFILE_SHARE = 0.1
LAST_PROFILE_SHARE = 0.9
SEARCH_REACH_SHARE_OF_LONGEST_SIDE = 0.017
MINIMUM_SEARCH_REACH_PIXELS = 6
MINIMUM_OUTSIDE_SAMPLES = 6
MINIMUM_CONTRAST_LEVELS = 24
MINIMUM_DEPARTURE_LEVELS = 12
DEPARTURE_SHARE_OF_CONTRAST = 0.2
AGREEMENT_TOLERANCE_PIXELS = 1.5
MINIMUM_AGREEING_PROFILES = 5
MINIMUM_SIDE_LENGTH_SHARE = 0.5
TANGENT_SPREAD_PIXELS = 1.0
PIXEL_CENTRE_SHIFT = 0.5


@dataclass(frozen=True)
class _Side:
    """A side of the frame: its start, the unit vector along it and the unit vector pointing into the frame."""

    start: Point
    length: float
    along: Point
    inward: Point


def _sides_of(corners: Corners) -> list[_Side]:
    centre_x = sum(corner[0] for corner in corners) / 4
    centre_y = sum(corner[1] for corner in corners) / 4
    sides = []
    for index in range(4):
        start, end = corners[index], corners[(index + 1) % 4]
        length = math.dist(start, end)
        along = ((end[0] - start[0]) / length, (end[1] - start[1]) / length)
        inward = (-along[1], along[0])
        if (centre_x - start[0]) * inward[0] + (centre_y - start[1]) * inward[1] < 0:
            inward = (-inward[0], -inward[1])
        sides.append(_Side(start, length, along, inward))
    return sides


def _level_at(luminance: Image.Image, x: float, y: float) -> float | None:
    """Bilinear level at a point of the page, whose pixels span [i, i + 1], or None off the image."""
    width, height = luminance.size
    x, y = x - PIXEL_CENTRE_SHIFT, y - PIXEL_CENTRE_SHIFT
    if x < 0 or y < 0 or x > width - 1 or y > height - 1:
        return None
    left, top = int(x), int(y)
    right, bottom = min(left + 1, width - 1), min(top + 1, height - 1)
    share_x, share_y = x - left, y - top
    upper = luminance.getpixel((left, top)) * (1 - share_x) + luminance.getpixel((right, top)) * share_x
    lower = luminance.getpixel((left, bottom)) * (1 - share_x) + luminance.getpixel((right, bottom)) * share_x
    return upper * (1 - share_y) + lower * share_y


def _profile(luminance: Image.Image, side: _Side, share: float, reach: int) -> list[float | None]:
    """Levels at one pixel steps across the side, from `reach` outside to `reach` inside (None off the image)."""
    origin_x = side.start[0] + side.along[0] * side.length * share
    origin_y = side.start[1] + side.along[1] * side.length * share
    levels: list[float | None] = []
    for offset in range(-reach, reach + 1):
        samples = [
            _level_at(
                luminance,
                origin_x + side.inward[0] * offset + side.along[0] * spread,
                origin_y + side.inward[1] * offset + side.along[1] * spread,
            )
            for spread in (-TANGENT_SPREAD_PIXELS, 0.0, TANGENT_SPREAD_PIXELS)
        ]
        found = [sample for sample in samples if sample is not None]
        levels.append(sum(found) / len(found) if len(found) == len(samples) else None)
    return levels


def _departure_offset(levels: list[float | None], reach: int) -> float | None:
    """Offset (negative outside the frame) where the profile leaves the level of the lid, None if it is not clear."""
    outside = [level for level in levels[: reach // 2] if level is not None]
    inside = [level for level in levels[reach + reach // 2 :] if level is not None]
    if len(outside) < MINIMUM_OUTSIDE_SAMPLES or not inside:
        return None
    lid_level = statistics.median(outside)
    contrast = abs(statistics.median(inside) - lid_level)
    if contrast < MINIMUM_CONTRAST_LEVELS:
        return None
    threshold = max(MINIMUM_DEPARTURE_LEVELS, DEPARTURE_SHARE_OF_CONTRAST * contrast)
    for index in range(reach // 2, len(levels) - 1):
        current, following = levels[index], levels[index + 1]
        if current is None or following is None:
            return None
        if abs(current - lid_level) > threshold and abs(following - lid_level) > threshold:
            previous = levels[index - 1]
            fraction = 0.0
            if previous is not None:
                before = abs(previous - lid_level)
                fraction = (threshold - before) / max(abs(current - lid_level) - before, 1e-9)
            return index - reach - 1 + min(1.0, max(0.0, fraction))
    return None


def _side_shift(luminance: Image.Image, side: _Side, reach: int) -> float | None:
    """How far the side moves inwards (negative: outwards), or None to keep it where it is."""
    shares = [
        FIRST_PROFILE_SHARE + (LAST_PROFILE_SHARE - FIRST_PROFILE_SHARE) * index / (PROFILE_POSITIONS - 1)
        for index in range(PROFILE_POSITIONS)
    ]
    offsets = [_departure_offset(_profile(luminance, side, share, reach), reach) for share in shares]
    found = [offset for offset in offsets if offset is not None]
    if len(found) < MINIMUM_AGREEING_PROFILES:
        return None
    middle = statistics.median(found)
    agreeing = [offset for offset in found if abs(offset - middle) <= AGREEMENT_TOLERANCE_PIXELS]
    if len(agreeing) < MINIMUM_AGREEING_PROFILES:
        return None
    return statistics.median(agreeing)


def _meeting_point(first: tuple[Point, Point], second: tuple[Point, Point]) -> Point | None:
    """Where two lines, each as a point and a direction, cross; None if they are parallel."""
    (first_x, first_y), (first_along_x, first_along_y) = first
    (second_x, second_y), (second_along_x, second_along_y) = second
    determinant = first_along_x * second_along_y - first_along_y * second_along_x
    if abs(determinant) < 1e-9:
        return None
    distance = ((second_x - first_x) * second_along_y - (second_y - first_y) * second_along_x) / determinant
    return (first_x + first_along_x * distance, first_y + first_along_y * distance)


def _moved_corners(sides: list[_Side], shifts: list[float]) -> Corners | None:
    lines = [
        (
            (side.start[0] + side.inward[0] * shift, side.start[1] + side.inward[1] * shift),
            side.along,
        )
        for side, shift in zip(sides, shifts, strict=True)
    ]
    corners = [_meeting_point(lines[index - 1], lines[index]) for index in range(4)]
    if any(corner is None for corner in corners):
        return None
    return (corners[0], corners[1], corners[2], corners[3])  # type: ignore[return-value]


def _is_sane(moved: Corners, sides: list[_Side]) -> bool:
    """No side collapsed or crossed the opposite one."""
    return all(
        math.dist(moved[index], moved[(index + 1) % 4]) >= MINIMUM_SIDE_LENGTH_SHARE * side.length
        for index, side in enumerate(sides)
    )


def refine_corners(luminance: Image.Image, corners: Corners) -> Corners:
    """The frame (clockwise, in pixels of the luminance image) with each side moved onto the edge of the photo."""
    reach = max(MINIMUM_SEARCH_REACH_PIXELS, round(SEARCH_REACH_SHARE_OF_LONGEST_SIDE * max(luminance.size)))
    sides = _sides_of(corners)
    shifts = [_side_shift(luminance, side, reach) or 0.0 for side in sides]
    moved = _moved_corners(sides, shifts)
    if moved is None or not _is_sane(moved, sides):
        return corners
    return moved
