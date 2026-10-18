import io
import logging
from collections.abc import Iterator
from contextlib import contextmanager

from PIL import Image

from digitalizadora.domain.errors import ImageAdjustmentFailedError, InvalidCropError, ScanFailedError
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.domain.pixel_region import PixelRegion
from digitalizadora.services.paper_edge_detection import PaperEdges, detect_paper_edges
from digitalizadora.services.paper_region_detection import PREVIEW_MAXIMUM_EDGE_PIXELS, detect_paper_region

LOGGER = logging.getLogger(__name__)
CROP_MARGIN_RATIO = 0.01
PREVIEW_COLOR_MODE = "RGB"


@contextmanager
def _failures_of_the_detection() -> Iterator[None]:
    try:
        yield
    except MemoryError as error:
        raise ImageAdjustmentFailedError("Not enough memory to look for the sheet in the scanned image") from error
    except (OSError, Image.DecompressionBombError, ValueError) as error:
        raise ScanFailedError("The scanned image could not be decoded to look for the sheet") from error


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


def _crop_around(region: PixelRegion, full_size: tuple[int, int]) -> PageCrop | None:
    """The region with a margin of a hundredth of the longest side, or None when it is the whole image."""
    margin = round(CROP_MARGIN_RATIO * max(full_size))
    grown_region = region.grown_within(margin, full_size)
    if grown_region.as_box() == (0, 0, *full_size):
        return None
    try:
        return PageCrop.from_pixel_region(grown_region, full_size)
    except InvalidCropError:
        LOGGER.info("The sheet found is too thin to be a crop; the whole image is kept")
        return None


def _logged_when_missing(crop: PageCrop | None) -> PageCrop | None:
    if crop is None:
        LOGGER.info("The automatic crop found no reliable sheet; the whole image is kept")
    return crop


class PageCropDetectionService:
    """Looks for the sheet of paper on the glass in a scanner JPEG and answers it as a crop in fractions.

    The quick mode applies the crop to the file it delivers, so it takes only the strict detection, which was
    validated against losing content. The document mode only suggests a frame the user can adjust, so it also
    takes the detection by side, which copes with an open lid.
    """

    def detect_crop_to_apply(self, jpeg_content: bytes) -> PageCrop | None:
        with _failures_of_the_detection():
            preview, full_size = _read_preview(jpeg_content)
            return _logged_when_missing(self._strict_crop(preview, full_size))

    def detect_crop_to_suggest(self, jpeg_content: bytes) -> PageCrop | None:
        with _failures_of_the_detection():
            preview, full_size = _read_preview(jpeg_content)
            crop = self._strict_crop(preview, full_size)
            if crop is None:
                crop = self._crop_by_side(preview, full_size)
            return _logged_when_missing(crop)

    def _strict_crop(self, preview: Image.Image, full_size: tuple[int, int]) -> PageCrop | None:
        paper_region = detect_paper_region(preview)
        if paper_region is None:
            return None
        return _crop_around(paper_region.scaled(preview.size, full_size), full_size)

    def _crop_by_side(self, preview: Image.Image, full_size: tuple[int, int]) -> PageCrop | None:
        edges = detect_paper_edges(preview)
        if edges is None:
            return None
        return _crop_around(_region_of_edges(edges, full_size), full_size)
