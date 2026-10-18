"""Finds each edge of the sheet on the glass in a small preview, side by side, with Pillow only.

photo_region_detection takes the border of the preview for a uniform background and fails when the lid is open:
the border then holds a blown-out side, a shadow and a gradient. Here every side is searched on its own, from the
glass inwards, on a profile of medians that ignores text. A side where the cover blends into the glass is read from
the glass beside the sheet. The result is only a suggestion for a frame the user can still adjust.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import mean, median

from PIL import Image

PROFILE_BAND_START_SHARE = 0.25
PROFILE_BAND_END_SHARE = 0.75
SKIPPED_BORDER_SHARE = 0.02
EDGE_SEARCH_REACH_SHARE = 0.35
EDGE_COMPARISON_WINDOW_PIXELS = 3
EDGE_STEP_LEVELS = 12
EDGE_REFINEMENT_PIXELS = 6
EDGE_DWELL_SHARE = 0.03
EDGE_OUTSIDE_SHARE = 0.03
OUTSIDE_FLATNESS_LEVELS = 12
GLASS_DEPARTURE_LEVELS = 8
GLASS_BAND_GAP_SHARE = 0.02
MINIMUM_GLASS_BAND_PIXELS = 3
MINIMUM_SEARCHABLE_SIDE_PIXELS = 20
MINIMUM_DETECTED_SIDES = 2
MINIMUM_FRAME_SIDE_SHARE = 0.02
MINIMUM_FRAME_AREA_SHARE = 0.20
GRAY_MODE = "L"


@dataclass(frozen=True)
class PaperEdges:
    """Edges as fractions (0..1) of the preview; None is a side with no reliable edge, left at the glass."""

    left: float | None
    top: float | None
    right: float | None
    bottom: float | None


Sides = tuple[float | None, float | None]
EdgeSearch = Callable[[Sequence[float]], float | None]


def _median_profile(gray: Image.Image, row_ranges: Sequence[tuple[int, int]]) -> list[float]:
    """The median of every column over the given rows: text covers a minority of a column, so it is ignored."""
    width = gray.width
    rows = b"".join(gray.crop((0, first_row, width, last_row)).tobytes() for first_row, last_row in row_ranges)
    return [median(rows[column::width]) for column in range(width)]


def _step_at(profile: Sequence[float], position: int) -> float:
    inside = mean(profile[position : position + EDGE_COMPARISON_WINDOW_PIXELS])
    outside = mean(profile[position - EDGE_COMPARISON_WINDOW_PIXELS : position])
    return abs(inside - outside)


def _outside_pixels(profile: Sequence[float]) -> int:
    return max(EDGE_COMPARISON_WINDOW_PIXELS, round(EDGE_OUTSIDE_SHARE * len(profile)))


def _search_range(profile: Sequence[float]) -> range:
    """Past the skipped border and a stretch of glass: an edge needs a plateau of glass before it."""
    first = round(SKIPPED_BORDER_SHARE * len(profile)) + _outside_pixels(profile)
    return range(first, round(EDGE_SEARCH_REACH_SHARE * len(profile)))


def _comes_from_a_plateau(profile: Sequence[float], position: int) -> bool:
    """The glass before a sheet edge is steady; a thin printed line is not, and its far side is no edge."""
    outside_levels = profile[position - _outside_pixels(profile) : position]
    return max(outside_levels) - min(outside_levels) <= OUTSIDE_FLATNESS_LEVELS


def _stays_beyond_the_step(profile: Sequence[float], position: int) -> bool:
    """A sheet edge is a step to a new level; a line of text is a step that returns to the old level at once."""
    outside_level = mean(profile[position - EDGE_COMPARISON_WINDOW_PIXELS : position])
    dwell_pixels = max(EDGE_COMPARISON_WINDOW_PIXELS, round(EDGE_DWELL_SHARE * len(profile)))
    dwelling_levels = profile[position : position + dwell_pixels]
    return all(abs(level - outside_level) >= EDGE_STEP_LEVELS / 2 for level in dwelling_levels)


def _first_step(profile: Sequence[float]) -> float | None:
    """The first step of the profile, from its start. Not the strongest: the text of the cover would win."""
    positions = _search_range(profile)
    for position in positions:
        if (
            _step_at(profile, position) >= EDGE_STEP_LEVELS
            and _comes_from_a_plateau(profile, position)
            and _stays_beyond_the_step(profile, position)
        ):
            refinement = range(position, min(positions.stop, position + EDGE_REFINEMENT_PIXELS))
            return max(refinement, key=lambda candidate: _step_at(profile, candidate)) / len(profile)
    return None


def _first_departure(profile: Sequence[float]) -> float | None:
    """Where the profile first leaves the level it starts at: the glass beside the sheet changes there."""
    positions = _search_range(profile)
    starting_level = median(profile[positions.start : positions.start + EDGE_COMPARISON_WINDOW_PIXELS])
    for position in positions:
        if abs(profile[position] - starting_level) >= GLASS_DEPARTURE_LEVELS:
            return position / len(profile)
    return None


def _sides_found_by(search: EdgeSearch, profile: Sequence[float]) -> Sides:
    near_edge = search(profile)
    far_edge = search(profile[::-1])
    return near_edge, None if far_edge is None else 1.0 - far_edge


def _central_sides(gray: Image.Image) -> Sides:
    first_row = round(PROFILE_BAND_START_SHARE * gray.height)
    last_row = round(PROFILE_BAND_END_SHARE * gray.height)
    return _sides_found_by(_first_step, _median_profile(gray, [(first_row, last_row)]))


def _glass_row_ranges(height: int, across_sides: Sides) -> list[tuple[int, int]]:
    """The rows beyond the sheet, above and below it, which show only the glass."""
    top_edge, bottom_edge = across_sides
    skipped_rows = round(SKIPPED_BORDER_SHARE * height)
    gap_rows = round(GLASS_BAND_GAP_SHARE * height)
    candidates = []
    if top_edge is not None:
        candidates.append((skipped_rows, round(top_edge * height) - gap_rows))
    if bottom_edge is not None:
        candidates.append((round(bottom_edge * height) + gap_rows, height - skipped_rows))
    return [(first, last) for first, last in candidates if last - first >= MINIMUM_GLASS_BAND_PIXELS]


def _outermost(candidates: list[float | None], pick: Callable[[list[float]], float]) -> float | None:
    found = [candidate for candidate in candidates if candidate is not None]
    return pick(found) if found else None


def _complete_from_the_glass(gray: Image.Image, central_sides: Sides, across_sides: Sides) -> Sides:
    """Sides the centre cannot see are read where the glass beside the sheet starts to change."""
    near_edge, far_edge = central_sides
    if near_edge is not None and far_edge is not None:
        return central_sides
    glass_sides = [
        _sides_found_by(_first_departure, _median_profile(gray, [row_range]))
        for row_range in _glass_row_ranges(gray.height, across_sides)
    ]
    # The outermost candidate keeps the sheet whole: a frame a little too wide loses nothing.
    near_candidates = [near for near, _ in glass_sides]
    far_candidates = [far for _, far in glass_sides]
    if near_edge is None:
        near_edge = _outermost(near_candidates, min)
    if far_edge is None:
        far_edge = _outermost(far_candidates, max)
    return near_edge, far_edge


def _is_plausible_frame(edges: PaperEdges) -> bool:
    detected_sides = [edge for edge in (edges.left, edges.top, edges.right, edges.bottom) if edge is not None]
    if len(detected_sides) < MINIMUM_DETECTED_SIDES:
        return False
    # Edges on one axis only are the first and last lines of text of a full page, not a sheet.
    if edges.left is None and edges.right is None or edges.top is None and edges.bottom is None:
        return False
    frame_width = (1.0 if edges.right is None else edges.right) - (0.0 if edges.left is None else edges.left)
    frame_height = (1.0 if edges.bottom is None else edges.bottom) - (0.0 if edges.top is None else edges.top)
    if min(frame_width, frame_height) < MINIMUM_FRAME_SIDE_SHARE:
        return False
    return frame_width * frame_height >= MINIMUM_FRAME_AREA_SHARE


def detect_paper_edges(preview: Image.Image) -> PaperEdges | None:
    """preview: any mode, the longest edge up to PREVIEW_MAXIMUM_EDGE_PIXELS. Returns fractions of the preview."""
    gray = preview if preview.mode == GRAY_MODE else preview.convert(GRAY_MODE)
    if min(gray.size) < MINIMUM_SEARCHABLE_SIDE_PIXELS:
        return None
    transposed = gray.transpose(Image.Transpose.TRANSPOSE)
    column_sides = _central_sides(gray)
    row_sides = _central_sides(transposed)
    left, right = _complete_from_the_glass(gray, column_sides, row_sides)
    top, bottom = _complete_from_the_glass(transposed, row_sides, (left, right))
    edges = PaperEdges(left, top, right, bottom)
    return edges if _is_plausible_frame(edges) else None
