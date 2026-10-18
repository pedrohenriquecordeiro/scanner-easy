from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.services.image_adjustment_service import ImageAdjustmentService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService


class MasterJpegService:
    """The JPEG that every output is made from: the scanner image, adjusted, with the requested density."""

    def __init__(
        self, image_adjustment_service: ImageAdjustmentService, jpeg_resolution_service: JpegResolutionService
    ) -> None:
        self._image_adjustment_service = image_adjustment_service
        self._jpeg_resolution_service = jpeg_resolution_service

    def build_master_jpeg(self, scanned_jpeg: bytes, request: ScanRequest) -> bytes:
        adjusted_jpeg = self._image_adjustment_service.adjust(scanned_jpeg, request.adjustment)
        return self._jpeg_resolution_service.with_resolution(adjusted_jpeg, request.settings.dots_per_inch)
