import io

from PIL import Image

from digitalizadora.domain.errors import ImageAdjustmentFailedError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.services.jpeg_reencoding import read_encoding_options, replace_with
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService


class ImageAdjustmentService:
    """Crops the sheet out of the lid background on a scanner JPEG; the quick mode keeps the cropped file."""

    def __init__(self, crop_detection_service: PageCropDetectionService) -> None:
        self._crop_detection_service = crop_detection_service

    def adjust(self, jpeg_content: bytes, adjustment: ImageAdjustment) -> bytes:
        if not adjustment.is_active:
            return jpeg_content
        try:
            detected_crops = self._crop_detection_service.detect_crops(jpeg_content).crops
            if not detected_crops:
                return jpeg_content
            return self._crop(jpeg_content, detected_crops[0], adjustment.jpeg_quality)
        except MemoryError as error:
            raise ImageAdjustmentFailedError("Not enough memory to adjust the scanned image") from error
        except (OSError, Image.DecompressionBombError, ValueError) as error:
            raise ScanFailedError("The scanned image could not be decoded for the adjustment") from error

    def _crop(self, jpeg_content: bytes, crop: PageCrop, jpeg_quality: int) -> bytes:
        image = Image.open(io.BytesIO(jpeg_content))
        try:
            encoding_options = read_encoding_options(image, jpeg_quality)
            region = crop.to_pixel_region(image.size)
            image = replace_with(image, lambda full_image: full_image.crop(region.as_box()))
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", **encoding_options)
        finally:
            image.close()
        return buffer.getvalue()
