import io
import logging

from PIL import Image

from digitalizadora.domain.errors import ImageAdjustmentFailedError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.pixel_region import PixelRegion
from digitalizadora.services.jpeg_reencoding import read_encoding_options, replace_with
from digitalizadora.services.paper_region_detection import PREVIEW_MAXIMUM_EDGE_PIXELS, detect_paper_region

LOGGER = logging.getLogger(__name__)
CROP_MARGIN_RATIO = 0.01
PREVIEW_COLOR_MODE = "RGB"


class ImageAdjustmentService:
    """Crops the sheet out of the lid background on a scanner JPEG; the quick mode keeps the cropped file."""

    def adjust(self, jpeg_content: bytes, adjustment: ImageAdjustment) -> bytes:
        if not adjustment.is_active:
            return jpeg_content
        try:
            crop_region = self._find_crop_region(jpeg_content)
            if crop_region is None:
                return jpeg_content
            return self._crop(jpeg_content, crop_region)
        except MemoryError as error:
            raise ImageAdjustmentFailedError("Not enough memory to adjust the scanned image") from error
        except (OSError, Image.DecompressionBombError, ValueError) as error:
            raise ScanFailedError("The scanned image could not be decoded for the adjustment") from error

    def _find_crop_region(self, jpeg_content: bytes) -> PixelRegion | None:
        """Detects on a reduced preview, which Pillow decodes at a fraction of the size even at 1200 dpi."""
        preview_edge = (PREVIEW_MAXIMUM_EDGE_PIXELS, PREVIEW_MAXIMUM_EDGE_PIXELS)
        with Image.open(io.BytesIO(jpeg_content)) as source:
            full_size = source.size
            source.draft(PREVIEW_COLOR_MODE, preview_edge)
            source.thumbnail(preview_edge, Image.Resampling.BOX)
            preview = source.convert(PREVIEW_COLOR_MODE)
        paper_region = detect_paper_region(preview)
        if paper_region is None:
            LOGGER.info("The automatic crop found no reliable sheet; the whole image is kept")
            return None
        margin = round(CROP_MARGIN_RATIO * max(full_size))
        crop_region = paper_region.scaled(preview.size, full_size).grown_within(margin, full_size)
        covers_everything = crop_region.as_box() == (0, 0, *full_size)
        return None if covers_everything else crop_region

    def _crop(self, jpeg_content: bytes, crop_region: PixelRegion) -> bytes:
        image = Image.open(io.BytesIO(jpeg_content))
        try:
            encoding_options = read_encoding_options(image)
            image = replace_with(image, lambda full_image: full_image.crop(crop_region.as_box()))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", **encoding_options)
        finally:
            image.close()
        return buffer.getvalue()
