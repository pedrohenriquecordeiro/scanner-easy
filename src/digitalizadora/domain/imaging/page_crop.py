import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from numbers import Real

from digitalizadora.domain.errors import InvalidCropError
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.domain.imaging.pixel_region import PixelCorner, PixelRegion

MINIMUM_CROP_EDGE_SHARE = 0.02
MINIMUM_CORNER_TRIANGLE_SHARE = 0.05
CROP_PRECISION_DIGITS = 6
CROP_TOLERANCE = 1e-9
CROP_CORNER_ROLES = ("top_left", "top_right", "bottom_right", "bottom_left")
CROP_CORNER_COUNT = len(CROP_CORNER_ROLES)
MINIMUM_REGION_SIDE_PIXELS = 1


def _is_real_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _is_finite_number(value: object) -> bool:
    if not _is_real_number(value):
        return False
    try:
        return math.isfinite(value)  # type: ignore[arg-type]
    except OverflowError:
        return False


def _scaled(fraction: float, side_pixels: int) -> float:
    # The round keeps 0.07 * 100 = 7.000000000000001 from becoming 8 pixels.
    return round(fraction * side_pixels, CROP_PRECISION_DIGITS)


def _floor_pixels(fraction: float, side_pixels: int) -> int:
    return math.floor(_scaled(fraction, side_pixels))


def _ceil_pixels(fraction: float, side_pixels: int) -> int:
    return math.ceil(_scaled(fraction, side_pixels))


@dataclass(frozen=True)
class CropCorner:
    """A point of the page as it is displayed, in fractions: x to the right, y downwards."""

    x: float
    y: float

    def turned_clockwise(self) -> "CropCorner":
        """The page turns a quarter clockwise: the point (x, y) goes to (1 - y, x)."""
        return CropCorner(_rounded(1.0 - self.y), _rounded(self.x))

    def turned_counterclockwise(self) -> "CropCorner":
        return CropCorner(_rounded(self.y), _rounded(1.0 - self.x))


@dataclass(frozen=True)
class RectangleEdges:
    left: float
    top: float
    right: float
    bottom: float


def _rounded(value: float) -> float:
    return round(value, CROP_PRECISION_DIGITS)


def _twice_signed_area(corners: Sequence[CropCorner]) -> float:
    """Positive for clockwise corners on the screen, where y grows downwards."""
    return sum(
        corner.x * following.y - following.x * corner.y
        for corner, following in zip(corners, (*corners[1:], corners[0]), strict=True)
    )


def _twice_corner_triangle_area(previous: CropCorner, corner: CropCorner, following: CropCorner) -> float:
    return (corner.x - previous.x) * (following.y - previous.y) - (corner.y - previous.y) * (following.x - previous.x)


def find_quadrilateral_problem(corners: Sequence[CropCorner]) -> str | None:
    """Why four corners are not a crop, or None. The same names and rules as the shared test vectors."""
    coordinates = [value for corner in corners for value in (corner.x, corner.y)]
    if not all(_is_finite_number(value) for value in coordinates):
        return "not_finite"
    if not all(-CROP_TOLERANCE <= value <= 1.0 + CROP_TOLERANCE for value in coordinates):
        return "outside_the_page"
    twice_area = _twice_signed_area(corners)
    if twice_area <= CROP_TOLERANCE:
        return "not_clockwise_or_empty"
    following_corners = (*corners[1:], corners[0])
    if any(
        math.dist((corner.x, corner.y), (following.x, following.y)) < MINIMUM_CROP_EDGE_SHARE - CROP_TOLERANCE
        for corner, following in zip(corners, following_corners, strict=True)
    ):
        return "edge_too_short"
    triangles = [
        _twice_corner_triangle_area(corners[index - 1], corners[index], following_corners[index])
        for index in range(CROP_CORNER_COUNT)
    ]
    if any(triangle <= CROP_TOLERANCE for triangle in triangles):
        return "not_convex"
    if any(triangle < MINIMUM_CORNER_TRIANGLE_SHARE * twice_area for triangle in triangles):
        return "corner_too_flat"
    return None


@dataclass(frozen=True)
class PageCrop:
    """Four corners in fractions (0..1) of the page as displayed (after the rotation), clockwise on the screen.

    The role of a corner (top_left ...) says where that corner goes in the cut-out image: the edge from top_left
    to top_right is its top, so the roles also fix how the cut-out photo is turned.
    """

    top_left: CropCorner
    top_right: CropCorner
    bottom_right: CropCorner
    bottom_left: CropCorner

    def __post_init__(self) -> None:
        problem = find_quadrilateral_problem(self.corners)
        if problem is not None:
            raise InvalidCropError(f"The crop is not a valid quadrilateral ({problem}): {self.corners!r}")

    @classmethod
    def from_rectangle(cls, edges: RectangleEdges) -> "PageCrop":
        return cls(
            CropCorner(edges.left, edges.top),
            CropCorner(edges.right, edges.top),
            CropCorner(edges.right, edges.bottom),
            CropCorner(edges.left, edges.bottom),
        )

    @classmethod
    def from_pixel_region(cls, region: PixelRegion, image_size: tuple[int, int]) -> "PageCrop":
        width, height = image_size
        edges = (region.left / width, region.top / height, region.right / width, region.bottom / height)
        left, top, right, bottom = (_rounded(edge) for edge in edges)
        return cls.from_rectangle(RectangleEdges(left, top, right, bottom))

    @classmethod
    def rounded(cls, corners: Sequence[CropCorner]) -> "PageCrop":
        """Rounds each coordinate first, so that four quarter turns return exactly to the start."""
        if len(corners) != CROP_CORNER_COUNT:
            raise InvalidCropError(f"A crop has exactly {CROP_CORNER_COUNT} corners, got {len(corners)}")
        coordinates = [value for corner in corners for value in (corner.x, corner.y)]
        if not all(_is_finite_number(value) for value in coordinates):
            raise InvalidCropError(f"The crop corners must be finite numbers, got {corners!r}")
        return cls(*(CropCorner(_rounded(corner.x), _rounded(corner.y)) for corner in corners))

    @property
    def corners(self) -> tuple[CropCorner, CropCorner, CropCorner, CropCorner]:
        return (self.top_left, self.top_right, self.bottom_right, self.bottom_left)

    @property
    def is_rectangle(self) -> bool:
        """The four edges are parallel to the edges of the page, whichever corner has which role."""
        first, second, third, fourth = self.corners
        horizontal_first = _same(first.y, second.y) and _same(third.y, fourth.y)
        vertical_first = _same(first.x, second.x) and _same(third.x, fourth.x)
        if horizontal_first:
            return _same(second.x, third.x) and _same(fourth.x, first.x)
        return vertical_first and _same(second.y, third.y) and _same(fourth.y, first.y)

    @property
    def rotation_to_upright(self) -> PageRotation:
        """Rectangle only: how to turn the cut-out clockwise so that top_left is at its upper left."""
        if not self.is_rectangle:
            raise ValueError("Only a rectangle has a rotation to upright; the others are straightened as a whole")
        edges = self.bounding_edges
        is_at_left = _same(self.top_left.x, edges.left)
        is_at_top = _same(self.top_left.y, edges.top)
        if is_at_left:
            return PageRotation.NONE if is_at_top else PageRotation.CLOCKWISE_90
        return PageRotation.COUNTERCLOCKWISE_90 if is_at_top else PageRotation.HALF_TURN

    @property
    def covers_whole_page(self) -> bool:
        if not self.is_rectangle or self.rotation_to_upright is not PageRotation.NONE:
            return False
        edges = self.bounding_edges
        return (
            edges.left <= CROP_TOLERANCE
            and edges.top <= CROP_TOLERANCE
            and edges.right >= 1.0 - CROP_TOLERANCE
            and edges.bottom >= 1.0 - CROP_TOLERANCE
        )

    @property
    def bounding_edges(self) -> RectangleEdges:
        return RectangleEdges(
            left=min(corner.x for corner in self.corners),
            top=min(corner.y for corner in self.corners),
            right=max(corner.x for corner in self.corners),
            bottom=max(corner.y for corner in self.corners),
        )

    def turned_clockwise(self) -> "PageCrop":
        """The page turns a quarter clockwise: the points follow it and the old left edge becomes the top."""
        return self._with_points_turned(CropCorner.turned_clockwise).with_output_turned_clockwise()

    def turned_counterclockwise(self) -> "PageCrop":
        return self.with_output_turned_counterclockwise()._with_points_turned(CropCorner.turned_counterclockwise)

    def with_output_turned_clockwise(self) -> "PageCrop":
        """Only the roles advance: the cut-out photo comes out turned a quarter clockwise."""
        return PageCrop(self.bottom_left, self.top_left, self.top_right, self.bottom_right)

    def with_output_turned_counterclockwise(self) -> "PageCrop":
        return PageCrop(self.top_right, self.bottom_right, self.bottom_left, self.top_left)

    def seen_on_master(self, quarter_turns: int) -> "PageCrop":
        """The points turned back by the page rotation, to the orientation of the scanner JPEG; roles are kept."""
        crop = self
        for _ in range(quarter_turns):
            crop = crop._with_points_turned(CropCorner.turned_counterclockwise)
        return crop

    def to_pixel_region(self, image_size: tuple[int, int]) -> PixelRegion:
        """Of the bounding edges. The origin rounds down and the far edges round up, so no pixel is lost."""
        width, height = image_size
        edges = self.bounding_edges
        left = min(_floor_pixels(edges.left, width), width - MINIMUM_REGION_SIDE_PIXELS)
        top = min(_floor_pixels(edges.top, height), height - MINIMUM_REGION_SIDE_PIXELS)
        right = min(max(_ceil_pixels(edges.right, width), left + MINIMUM_REGION_SIDE_PIXELS), width)
        bottom = min(max(_ceil_pixels(edges.bottom, height), top + MINIMUM_REGION_SIDE_PIXELS), height)
        return PixelRegion(left, top, right, bottom)

    def to_pixel_corners(self, image_size: tuple[int, int]) -> tuple[PixelCorner, ...]:
        width, height = image_size
        return tuple(PixelCorner(_scaled(corner.x, width), _scaled(corner.y, height)) for corner in self.corners)

    def output_size_in_pixels(self, image_size: tuple[int, int]) -> tuple[int, int]:
        """The mean of the opposite edges, in pixels of the image the crop is read from; at least one pixel."""
        top_left, top_right, bottom_right, bottom_left = self.to_pixel_corners(image_size)
        mean_width = (_distance(top_left, top_right) + _distance(bottom_left, bottom_right)) / 2
        mean_height = (_distance(top_left, bottom_left) + _distance(top_right, bottom_right)) / 2
        return (
            max(MINIMUM_REGION_SIDE_PIXELS, round(mean_width)),
            max(MINIMUM_REGION_SIDE_PIXELS, round(mean_height)),
        )

    def _with_points_turned(self, turn: Callable[[CropCorner], CropCorner]) -> "PageCrop":
        return PageCrop(*(turn(corner) for corner in self.corners))


def _same(first: float, second: float) -> bool:
    return abs(first - second) <= CROP_TOLERANCE


def _distance(first: PixelCorner, second: PixelCorner) -> float:
    return math.dist((first.x, first.y), (second.x, second.y))
