import io
import logging
import math
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from PIL import Image

from digitalizadora.domain.errors import ImageAdjustmentFailedError, InvalidCropError, ScanFailedError
from digitalizadora.domain.page_crop import CropCorner, PageCrop
from digitalizadora.domain.page_framing import put_in_reading_order
from digitalizadora.domain.pixel_region import PixelRegion
from digitalizadora.services.paper_edge_detection import PaperEdges, detect_paper_edges
from digitalizadora.services.photo_region_detection import (
    PREVIEW_MAXIMUM_EDGE_PIXELS,
    Corners,
    PhotoRegion,
    PhotoRegions,
    detect_photo_regions,
    grow_rectangle,
)

LOGGER = logging.getLogger(__name__)
CROP_MARGIN_RATIO = 0.01
MAXIMUM_MARGIN_HALVINGS = 10
# A photo this close to upright is taken as upright: the crop is then a plain rectangle.
AXIS_SNAP_DEGREES = 1.5
PREVIEW_COLOR_MODE = "RGB"


@dataclass(frozen=True)
class _PageGeometry:
    """The page size in pixels and the margin around what was found, as a share of the longest side."""

    full_size: tuple[int, int]
    margin_ratio: float

    @property
    def margin_pixels(self) -> float:
        return self.margin_ratio * max(self.full_size)


@dataclass(frozen=True)
class DetectedCrops:
    """The crops found, in reading order and in the orientation of the JPEG given; 0 to 2."""

    crops: tuple[PageCrop, ...]
    ignored_region_count: int


@contextmanager
def _failures_of_the_detection() -> Iterator[None]:
    try:
        yield
    except MemoryError as error:
        raise ImageAdjustmentFailedError("Not enough memory to look for the photos in the scanned image") from error
    except (OSError, Image.DecompressionBombError, ValueError) as error:
        raise ScanFailedError("The scanned image could not be decoded to look for the photos") from error


def _read_preview(jpeg_content: bytes) -> tuple[Image.Image, tuple[int, int]]:
    """A reduced preview, which Pillow decodes at a fraction of the size even at 1200 dots per inch."""
    preview_edge = (PREVIEW_MAXIMUM_EDGE_PIXELS, PREVIEW_MAXIMUM_EDGE_PIXELS)
    with Image.open(io.BytesIO(jpeg_content)) as source:
        full_size = source.size
        source.draft(PREVIEW_COLOR_MODE, preview_edge)
        source.thumbnail(preview_edge, Image.Resampling.BOX)
        return source.convert(PREVIEW_COLOR_MODE), full_size


def _region_of_edges(edges: PaperEdges, full_size: tuple[int, int]) -> PixelRegion:
    """A side without an edge stays at the glass: 0 for the near sides and the full size for the far ones."""
    width, height = full_size
    return PixelRegion(
        left=0 if edges.left is None else round(edges.left * width),
        top=0 if edges.top is None else round(edges.top * height),
        right=width if edges.right is None else round(edges.right * width),
        bottom=height if edges.bottom is None else round(edges.bottom * height),
    )


def _crop_around(region: PixelRegion, page: _PageGeometry) -> PageCrop | None:
    """The region with the margin of the page, or None when it is the whole image."""
    full_size = page.full_size
    grown_region = region.grown_within(round(page.margin_pixels), full_size)
    if grown_region.as_box() == (0, 0, *full_size):
        return None
    try:
        return PageCrop.from_pixel_region(grown_region, full_size)
    except InvalidCropError:
        LOGGER.info("The region found is too thin to be a crop; it is left out")
        return None


def _bounding_region(region: PhotoRegion, preview_size: tuple[int, int]) -> PixelRegion:
    horizontal_positions = [corner[0] for corner in region.corners]
    vertical_positions = [corner[1] for corner in region.corners]
    width, height = preview_size
    return PixelRegion(
        left=max(0, math.floor(min(horizontal_positions))),
        top=max(0, math.floor(min(vertical_positions))),
        right=min(width, math.ceil(max(horizontal_positions))),
        bottom=min(height, math.ceil(max(vertical_positions))),
    )


def _is_inside(corners: Corners, size: tuple[int, int]) -> bool:
    width, height = size
    return all(0 <= x <= width and 0 <= y <= height for x, y in corners)


def _grown_within_the_page(corners: Corners, page: _PageGeometry) -> Corners:
    """Pushed out by the margin; a margin that would take a corner off the page is halved until it fits."""
    margin = page.margin_pixels
    for _ in range(MAXIMUM_MARGIN_HALVINGS):
        grown_corners = grow_rectangle(corners, margin)
        if _is_inside(grown_corners, page.full_size):
            return grown_corners
        margin /= 2
    return corners


def _clamped(value: float) -> float:
    return min(1.0, max(0.0, value))


def _rotated_crop(region: PhotoRegion, preview_size: tuple[int, int], page: _PageGeometry) -> PageCrop | None:
    full_size = page.full_size
    scale_x, scale_y = full_size[0] / preview_size[0], full_size[1] / preview_size[1]
    corners_on_the_page: Corners = tuple((x * scale_x, y * scale_y) for x, y in region.corners)  # type: ignore[assignment]
    grown_corners = _grown_within_the_page(corners_on_the_page, page)
    try:
        return PageCrop.rounded(
            [CropCorner(_clamped(x / full_size[0]), _clamped(y / full_size[1])) for x, y in grown_corners]
        )
    except InvalidCropError:
        LOGGER.info("The photo found is too thin or too small to be a crop; it is left out")
        return None


def _crop_of_region(region: PhotoRegion, preview_size: tuple[int, int], page: _PageGeometry) -> PageCrop | None:
    angle = abs(region.top_edge_angle_degrees)
    if angle <= AXIS_SNAP_DEGREES or angle >= 90 - AXIS_SNAP_DEGREES:
        bounding_region = _bounding_region(region, preview_size)
        return _crop_around(bounding_region.scaled(preview_size, page.full_size), page)
    return _rotated_crop(region, preview_size, page)


class PageCropDetectionService:
    """Looks for the photos or the sheet lying on the glass in a scanner JPEG and answers them as crops in fractions.

    Both modes only suggest crops the user can adjust. First the detector of regions, which finds up to two rotated
    photos when the border of the scan is a uniform lid, and then its answer is final (no region keeps the whole image);
    only when the border is not uniform (an open lid) the detection by side answers, with one rectangle.
    """

    def __init__(self, crop_margin_enabled: Callable[[], bool] = lambda: True) -> None:
        self._crop_margin_enabled = crop_margin_enabled

    def detect_crops(self, jpeg_content: bytes) -> DetectedCrops:
        with _failures_of_the_detection():
            preview, full_size = _read_preview(jpeg_content)
            page = _PageGeometry(full_size, CROP_MARGIN_RATIO if self._crop_margin_enabled() else 0.0)
            detection = detect_photo_regions(preview)
            if detection is None:
                detected_crops = DetectedCrops(self._crops_by_side(preview, page), 0)
            else:
                detected_crops = self._crops_of_regions(detection, preview.size, page)
            if not detected_crops.crops:
                LOGGER.info("The automatic crop found no reliable photo or sheet; the whole image is kept")
            return detected_crops

    def _crops_of_regions(
        self, detection: PhotoRegions, preview_size: tuple[int, int], page: _PageGeometry
    ) -> DetectedCrops:
        crops = [_crop_of_region(region, preview_size, page) for region in detection.regions]
        found_crops = [crop for crop in crops if crop is not None]
        return DetectedCrops(put_in_reading_order(found_crops), detection.ignored_count)

    def _crops_by_side(self, preview: Image.Image, page: _PageGeometry) -> tuple[PageCrop, ...]:
        edges = detect_paper_edges(preview)
        if edges is None:
            return ()
        crop = _crop_around(_region_of_edges(edges, page.full_size), page)
        return () if crop is None else (crop,)
