"""Finds up to two photos (or a sheet) lying on the glass in a small preview, as rotated rectangles, with Pillow only.

The border of the preview is taken as the background (the lid, closed or open). Whatever differs enough from it is
foreground; the connected pieces of foreground are the candidates, each wrapped in the rectangle of least area that
holds it. When the border is not trustworthy or a candidate is not plausible there is no region, and the caller keeps
the whole image: failing to "do not crop" never loses content.
"""

import math
import re
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFilter

PREVIEW_MAXIMUM_EDGE_PIXELS = 400
BORDER_WIDTH_RATIO = 0.015
MINIMUM_BORDER_WIDTH_PIXELS = 2
BACKGROUND_TOLERANCE_LEVELS = 20
MINIMUM_BACKGROUND_BORDER_SHARE = 0.6
FOREGROUND_DIFFERENCE_LEVELS = 20
# Looser than the foreground, to see what a region left out: a dark part of the page next to the lid.
SURROUNDING_DIFFERENCE_LEVELS = 10
REGION_NOISE_FILTER_SIZE = 5
MINIMUM_PHOTO_AREA_SHARE = 0.01
MAXIMUM_PHOTOS = 2
# A photo is a solid block, while the rectangle around loose foreground (text, scratches) is not.
MINIMUM_REGION_FILL_SHARE = 0.75
# A photo flush with a corner of the glass touches two sides; a region on three or four sides is the background
# around a big sheet taken for the sheet itself.
MAXIMUM_TOUCHED_SIDES = 2
MAXIMUM_RING_FOREGROUND_SHARE = 0.25

GRAY_LEVEL_COUNT = 256
MASK_ON = 255
MASK_OFF = 0
RUN_OF_FOREGROUND = re.compile(b"\xff+")
Point = tuple[float, float]
Corners = tuple[Point, Point, Point, Point]


@dataclass(frozen=True)
class PhotoRegion:
    """A rotated rectangle in pixels of the preview, clockwise on the screen from the top left.

    The edge from the first corner to the second is the one closest to horizontal on the screen."""

    corners: Corners

    @property
    def top_edge_angle_degrees(self) -> float:
        """Of the first edge, clockwise on the screen (y grows downwards): 0 for an upright photo."""
        (first_x, first_y), (second_x, second_y) = self.corners[0], self.corners[1]
        return math.degrees(math.atan2(second_y - first_y, second_x - first_x))


@dataclass(frozen=True)
class PhotoRegions:
    regions: tuple[PhotoRegion, ...]
    ignored_count: int


@dataclass(frozen=True)
class _Component:
    area: int
    points: list[Point]


@dataclass(frozen=True)
class _Candidate:
    area: int
    corners: Corners


def _border_width(preview: Image.Image) -> int:
    return max(MINIMUM_BORDER_WIDTH_PIXELS, round(BORDER_WIDTH_RATIO * max(preview.size)))


def _border_strips(preview: Image.Image, border_width: int) -> list[Image.Image]:
    width, height = preview.size
    return [
        preview.crop((0, 0, width, border_width)),
        preview.crop((0, height - border_width, width, height)),
        preview.crop((0, border_width, border_width, height - border_width)),
        preview.crop((width - border_width, border_width, width, height - border_width)),
    ]


def _border_histogram(band: Image.Image) -> list[int]:
    histogram = [0] * GRAY_LEVEL_COUNT
    for strip in _border_strips(band, _border_width(band)):
        for level, count in enumerate(strip.histogram()):
            histogram[level] += count
    return histogram


def _median_level(histogram: list[int]) -> int:
    half_of_pixels = sum(histogram) / 2
    counted_pixels = 0
    for level, count in enumerate(histogram):
        counted_pixels += count
        if counted_pixels >= half_of_pixels:
            return level
    return GRAY_LEVEL_COUNT - 1


def _background_share(histogram: list[int], background_level: int) -> float:
    lowest_level = max(0, background_level - BACKGROUND_TOLERANCE_LEVELS)
    highest_level = min(GRAY_LEVEL_COUNT - 1, background_level + BACKGROUND_TOLERANCE_LEVELS)
    return sum(histogram[lowest_level : highest_level + 1]) / sum(histogram)


def _border_is_background(border_histograms: list[list[int]], background_levels: list[int]) -> bool:
    """Every colour channel of the border must be steady around its own median."""
    background_shares = [
        _background_share(histogram, background_level)
        for histogram, background_level in zip(border_histograms, background_levels, strict=True)
    ]
    return min(background_shares) >= MINIMUM_BACKGROUND_BORDER_SHARE


def _difference_from_level(band: Image.Image, background_level: int) -> Image.Image:
    return ImageChops.difference(band, Image.new("L", band.size, background_level))


def _foreground_mask(differences: list[Image.Image], difference_levels: int) -> Image.Image:
    """A pixel is foreground when any colour channel differs enough, so a dark but coloured cover is not lost."""
    table = [MASK_ON if level > difference_levels else MASK_OFF for level in range(GRAY_LEVEL_COUNT)]
    mask = differences[0].point(table)
    for difference in differences[1:]:
        mask = ImageChops.lighter(mask, difference.point(table))
    return mask.filter(ImageFilter.MedianFilter(REGION_NOISE_FILTER_SIZE))


def _ramp_term(ramp: Image.Image, span: int) -> Image.Image:
    """The ramp (0 to 255 across the image) as a term of 128 plus `span` levels spread over the image, centred."""
    return ramp.point(
        [
            min(GRAY_LEVEL_COUNT - 1, max(0, round(GRAY_LEVEL_COUNT / 2 + span * (level / 255 - 0.5))))
            for level in range(GRAY_LEVEL_COUNT)
        ]
    )


def _sloped_background(band: Image.Image) -> Image.Image:
    """The lid as a plane: the medians of the four sides of the border give its level and its slope on both axes."""
    top, bottom, left, right = (_median_level(strip.histogram()) for strip in _border_strips(band, _border_width(band)))
    vertical_ramp = Image.linear_gradient("L").resize(band.size, Image.Resampling.BILINEAR)
    horizontal_ramp = Image.linear_gradient("L").rotate(90).resize(band.size, Image.Resampling.BILINEAR)
    average_level = round((top + bottom + left + right) / 4)
    return ImageChops.add(
        _ramp_term(horizontal_ramp, right - left),
        _ramp_term(vertical_ramp, bottom - top),
        scale=1.0,
        offset=average_level - GRAY_LEVEL_COUNT,
    )


Run = tuple[int, int, int]


class _RunLabeling:
    """Connected pieces of foreground by the runs of each row and a union-find; keeps the corners of every run."""

    def __init__(self) -> None:
        self._parents: list[int] = []
        self._runs: list[tuple[int, int, int, int]] = []

    def label(self, mask: Image.Image) -> list[_Component]:
        width, height = mask.size
        data = mask.tobytes()
        previous_row: list[Run] = []
        for row in range(height):
            current_row = [
                self._add_run(match.start(), match.end(), row)
                for match in RUN_OF_FOREGROUND.finditer(data[row * width : (row + 1) * width])
            ]
            self._join_overlapping_runs(previous_row, current_row)
            previous_row = current_row
        return self._collect_components()

    def _add_run(self, start: int, end: int, row: int) -> Run:
        index = len(self._parents)
        self._parents.append(index)
        self._runs.append((start, end, row, index))
        return (start, end, index)

    def _find_root(self, index: int) -> int:
        while self._parents[index] != index:
            self._parents[index] = self._parents[self._parents[index]]
            index = self._parents[index]
        return index

    def _join_overlapping_runs(self, previous_row: list[Run], current_row: list[Run]) -> None:
        previous_position = current_position = 0
        while previous_position < len(previous_row) and current_position < len(current_row):
            previous_start, previous_end, previous_index = previous_row[previous_position]
            current_start, current_end, current_index = current_row[current_position]
            if previous_start < current_end and current_start < previous_end:
                previous_root, current_root = self._find_root(previous_index), self._find_root(current_index)
                if previous_root != current_root:
                    self._parents[current_root] = previous_root
            if previous_end < current_end:
                previous_position += 1
            else:
                current_position += 1

    def _collect_components(self) -> list[_Component]:
        areas: dict[int, int] = {}
        points_by_root: dict[int, list[Point]] = {}
        for start, end, row, index in self._runs:
            root = self._find_root(index)
            areas[root] = areas.get(root, 0) + end - start
            points_by_root.setdefault(root, []).extend(((start, row), (end, row), (start, row + 1), (end, row + 1)))
        return [_Component(areas[root], points) for root, points in points_by_root.items()]


def _cross(origin: Point, first: Point, second: Point) -> float:
    return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (second[0] - origin[0])


def _convex_hull(points: list[Point]) -> list[Point]:
    """Andrew's monotone chain."""
    ordered_points = sorted(set(points))
    if len(ordered_points) <= 2:
        return ordered_points
    lower: list[Point] = []
    for point in ordered_points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[Point] = []
    for point in reversed(ordered_points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _rectangle_on_edge(hull: list[Point], edge_start_index: int) -> tuple[float, Corners] | None:
    """The rectangle with one side along an edge of the hull, as (area, corners); None for an edge of no length."""
    start = hull[edge_start_index]
    end = hull[(edge_start_index + 1) % len(hull)]
    length = math.dist(start, end)
    if length == 0:
        return None
    along_x, along_y = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    across_x, across_y = -along_y, along_x
    alongs = [(x - start[0]) * along_x + (y - start[1]) * along_y for x, y in hull]
    acrosses = [(x - start[0]) * across_x + (y - start[1]) * across_y for x, y in hull]
    first_along, last_along, first_across, last_across = min(alongs), max(alongs), min(acrosses), max(acrosses)

    def corner(along: float, across: float) -> Point:
        return (start[0] + along * along_x + across * across_x, start[1] + along * along_y + across * across_y)

    corners = (
        corner(first_along, first_across),
        corner(last_along, first_across),
        corner(last_along, last_across),
        corner(first_along, last_across),
    )
    return (last_along - first_along) * (last_across - first_across), corners


def _minimum_area_rectangle(hull: list[Point]) -> Corners | None:
    """The optimum has a side on an edge of the hull, so each edge is tried and the least area wins."""
    rectangles = [_rectangle_on_edge(hull, index) for index in range(len(hull))]
    found_rectangles = [rectangle for rectangle in rectangles if rectangle is not None]
    if not found_rectangles:
        return None
    return min(found_rectangles, key=lambda rectangle: rectangle[0])[1]


def _rectangle_area(corners: Corners) -> float:
    return math.dist(corners[0], corners[1]) * math.dist(corners[1], corners[2])


def _edge_angle(corners: Corners, edge_index: int) -> float:
    start, end = corners[edge_index], corners[(edge_index + 1) % 4]
    return math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))


def _starting_at_the_top_edge(corners: Corners) -> Corners:
    """Clockwise on the screen, starting so that the first edge is the one closest to horizontal.

    A tie takes the edge that points downwards to the right, so a quarter-turned photo does not flip."""
    twice_area = sum(
        corners[index][0] * corners[(index + 1) % 4][1] - corners[(index + 1) % 4][0] * corners[index][1]
        for index in range(4)
    )
    clockwise_corners: Corners = corners if twice_area >= 0 else (corners[3], corners[2], corners[1], corners[0])
    angles = [_edge_angle(clockwise_corners, index) for index in range(4)]
    top_index = min(range(4), key=lambda index: (round(abs(angles[index]), 6), -angles[index]))
    ordered = clockwise_corners[top_index:] + clockwise_corners[:top_index]
    return (ordered[0], ordered[1], ordered[2], ordered[3])


def _candidates_of(mask: Image.Image) -> list[_Candidate]:
    """The pieces of foreground big enough to be a photo, each in its rectangle, the largest first."""
    minimum_area = MINIMUM_PHOTO_AREA_SHARE * mask.width * mask.height
    candidates = []
    for component in _RunLabeling().label(mask):
        if component.area < minimum_area:
            continue
        rectangle = _minimum_area_rectangle(_convex_hull(component.points))
        if rectangle is not None:
            candidates.append(_Candidate(component.area, _starting_at_the_top_edge(rectangle)))
    return sorted(candidates, key=lambda candidate: -candidate.area)


def _touched_side_count(corners: Corners, preview: Image.Image) -> int:
    width, height = preview.size
    border_width = _border_width(preview)
    horizontal_positions = [corner[0] for corner in corners]
    vertical_positions = [corner[1] for corner in corners]
    return sum(
        (
            min(horizontal_positions) <= border_width,
            min(vertical_positions) <= border_width,
            max(horizontal_positions) >= width - border_width,
            max(vertical_positions) >= height - border_width,
        )
    )


def grow_rectangle(corners: Corners, margin: float) -> Corners:
    """The rectangle pushed out by the margin on every side, along its own axes."""
    centre_x = sum(corner[0] for corner in corners) / 4
    centre_y = sum(corner[1] for corner in corners) / 4
    top_length = math.dist(corners[0], corners[1])
    along_x, along_y = (corners[1][0] - corners[0][0]) / top_length, (corners[1][1] - corners[0][1]) / top_length
    across_x, across_y = -along_y, along_x
    grown = []
    for x, y in corners:
        along_sign = 1 if (x - centre_x) * along_x + (y - centre_y) * along_y > 0 else -1
        across_sign = 1 if (x - centre_x) * across_x + (y - centre_y) * across_y > 0 else -1
        grown.append(
            (
                x + along_sign * margin * along_x + across_sign * margin * across_x,
                y + along_sign * margin * along_y + across_sign * margin * across_y,
            )
        )
    return (grown[0], grown[1], grown[2], grown[3])


def _polygon_mask(size: tuple[int, int], corners: Corners) -> Image.Image:
    mask = Image.new("L", size, MASK_OFF)
    ImageDraw.Draw(mask).polygon([tuple(corner) for corner in corners], fill=MASK_ON)
    return mask


def _ring_foreground_share(loose_mask: Image.Image, corners: Corners, accepted: list[Corners]) -> float:
    """Share of the ring just outside the region (not inside another region) that does not look like background."""
    ring_width = _border_width(loose_mask)
    ring = ImageChops.subtract(
        _polygon_mask(loose_mask.size, grow_rectangle(corners, ring_width)), _polygon_mask(loose_mask.size, corners)
    )
    for other_corners in accepted:
        ring = ImageChops.subtract(ring, _polygon_mask(loose_mask.size, grow_rectangle(other_corners, ring_width)))
    ring_pixels = ring.histogram()[MASK_ON]
    if ring_pixels == 0:
        return 0.0
    return ImageChops.multiply(ring, loose_mask).histogram()[MASK_ON] / ring_pixels


def _is_plausible(candidate: _Candidate, loose_mask: Image.Image, accepted: list[Corners]) -> bool:
    if candidate.area / _rectangle_area(candidate.corners) < MINIMUM_REGION_FILL_SHARE:
        return False
    if _touched_side_count(candidate.corners, loose_mask) > MAXIMUM_TOUCHED_SIDES:
        return False
    return _ring_foreground_share(loose_mask, candidate.corners, accepted) <= MAXIMUM_RING_FOREGROUND_SHARE


def _regions_in(differences: list[Image.Image]) -> PhotoRegions:
    """The plausible regions of foreground, largest first, at most MAXIMUM_PHOTOS; the others are counted."""
    mask = _foreground_mask(differences, FOREGROUND_DIFFERENCE_LEVELS)
    loose_mask = _foreground_mask(differences, SURROUNDING_DIFFERENCE_LEVELS)
    accepted: list[Corners] = []
    ignored_count = 0
    for candidate in _candidates_of(mask):
        if not _is_plausible(candidate, loose_mask, accepted):
            continue
        if len(accepted) < MAXIMUM_PHOTOS:
            accepted.append(candidate.corners)
        else:
            ignored_count += 1
    return PhotoRegions(tuple(PhotoRegion(corners) for corners in accepted), ignored_count)


def _regions_on_a_shaded_lid(bands: list[Image.Image]) -> PhotoRegions | None:
    """A lid that is darker on one side than on the other (not closed, a vignette) is not one level but a plane.

    This only answers when it finds two photos, which one level or the detection by side cannot tell apart; one
    object keeps with them, and the detection by side also copes with a book on an open lid."""
    differences = [ImageChops.difference(band, _sloped_background(band)) for band in bands]
    border_histograms = [_border_histogram(difference) for difference in differences]
    if not _border_is_background(border_histograms, [0] * len(differences)):
        return None
    detection = _regions_in(differences)
    return detection if len(detection.regions) == MAXIMUM_PHOTOS else None


def detect_photo_regions(preview: Image.Image) -> PhotoRegions | None:
    """preview: mode "L" or "RGB" with the longest edge up to PREVIEW_MAXIMUM_EDGE_PIXELS, in pixels of the preview.

    None: the border is not a uniform background (an open lid), so this detector has no say, unless the border is a
    shaded lid with two photos on it. Otherwise the regions, largest first, at most MAXIMUM_PHOTOS; the others that
    were plausible are counted as ignored."""
    width, height = preview.size
    if min(width, height) <= 2 * MINIMUM_BORDER_WIDTH_PIXELS:
        return None
    bands = list(preview.split())
    border_histograms = [_border_histogram(band) for band in bands]
    background_levels = [_median_level(histogram) for histogram in border_histograms]
    if not _border_is_background(border_histograms, background_levels):
        return _regions_on_a_shaded_lid(bands)
    differences = [_difference_from_level(band, level) for band, level in zip(bands, background_levels, strict=True)]
    detection = _regions_in(differences)
    if len(detection.regions) < MAXIMUM_PHOTOS:
        # A lid a little shaded still passes as one level, but its shade can hide a second photo.
        return _regions_on_a_shaded_lid(bands) or detection
    return detection
