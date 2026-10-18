import math
from dataclasses import dataclass
from numbers import Real

from digitalizadora.domain.errors import InvalidCropError
from digitalizadora.domain.pixel_region import PixelRegion

MINIMUM_CROP_SIDE_SHARE = 0.02
CROP_PRECISION_DIGITS = 6
CROP_SIDE_TOLERANCE = 1e-9
MINIMUM_REGION_SIDE_PIXELS = 1


def _is_real_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


@dataclass(frozen=True)
class PageCrop:
    """A rectangle in fractions (0..1) of the page as it is displayed, after the page rotation."""

    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        edges = (self.left, self.top, self.right, self.bottom)
        if not all(_is_real_number(edge) and math.isfinite(edge) for edge in edges):
            raise InvalidCropError(f"The crop edges must be finite numbers, got {edges!r}")
        if not all(0.0 <= edge <= 1.0 for edge in edges):
            raise InvalidCropError(f"The crop edges must be between 0 and 1, got {edges!r}")
        if self.right - self.left < MINIMUM_CROP_SIDE_SHARE - CROP_SIDE_TOLERANCE:
            raise InvalidCropError(f"The crop is too narrow: {edges!r}")
        if self.bottom - self.top < MINIMUM_CROP_SIDE_SHARE - CROP_SIDE_TOLERANCE:
            raise InvalidCropError(f"The crop is too short: {edges!r}")

    @classmethod
    def rounded(cls, edges: tuple[float, float, float, float]) -> "PageCrop":
        """Rounds each edge first, so that four quarter turns return exactly to the start."""
        if not all(_is_real_number(edge) and math.isfinite(edge) for edge in edges):
            raise InvalidCropError(f"The crop edges must be finite numbers, got {edges!r}")
        left, top, right, bottom = (round(edge, CROP_PRECISION_DIGITS) for edge in edges)
        return cls(left, top, right, bottom)

    @property
    def covers_whole_page(self) -> bool:
        return (
            self.left <= CROP_SIDE_TOLERANCE
            and self.top <= CROP_SIDE_TOLERANCE
            and self.right >= 1.0 - CROP_SIDE_TOLERANCE
            and self.bottom >= 1.0 - CROP_SIDE_TOLERANCE
        )

    def turned_clockwise(self) -> "PageCrop":
        """The point (x, y) of the page goes to (1 - y, x), so the rectangle follows the page."""
        return PageCrop.rounded((1.0 - self.bottom, self.left, 1.0 - self.top, self.right))

    def turned_counterclockwise(self) -> "PageCrop":
        return PageCrop.rounded((self.top, 1.0 - self.right, self.bottom, 1.0 - self.left))

    def to_pixel_region(self, image_size: tuple[int, int]) -> PixelRegion:
        """The origin rounds down and the far edges round up, so no pixel of the frame is lost."""
        width, height = image_size
        left = min(_floor_pixels(self.left, width), width - MINIMUM_REGION_SIDE_PIXELS)
        top = min(_floor_pixels(self.top, height), height - MINIMUM_REGION_SIDE_PIXELS)
        right = min(max(_ceil_pixels(self.right, width), left + MINIMUM_REGION_SIDE_PIXELS), width)
        bottom = min(max(_ceil_pixels(self.bottom, height), top + MINIMUM_REGION_SIDE_PIXELS), height)
        return PixelRegion(left, top, right, bottom)

    @classmethod
    def from_pixel_region(cls, region: PixelRegion, image_size: tuple[int, int]) -> "PageCrop":
        width, height = image_size
        return cls.rounded((region.left / width, region.top / height, region.right / width, region.bottom / height))


def _scaled(fraction: float, side_pixels: int) -> float:
    # The round keeps 0.07 * 100 = 7.000000000000001 from becoming 8 pixels.
    return round(fraction * side_pixels, CROP_PRECISION_DIGITS)


def _floor_pixels(fraction: float, side_pixels: int) -> int:
    return math.floor(_scaled(fraction, side_pixels))


def _ceil_pixels(fraction: float, side_pixels: int) -> int:
    return math.ceil(_scaled(fraction, side_pixels))


WHOLE_PAGE = PageCrop(0.0, 0.0, 1.0, 1.0)
