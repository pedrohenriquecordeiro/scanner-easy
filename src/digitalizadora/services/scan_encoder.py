from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import (
    DEFAULT_PDF_TITLE_TEMPLATE,
    PdfAssemblyService,
    PdfDocumentSpecification,
)
from digitalizadora.services.thumbnail_service import ThumbnailService

EXPECTED_MEDIA_TYPE = "image/jpeg"
THUMBNAIL_MAXIMUM_EDGE_PIXELS = 480


class ScanEncoder:
    def __init__(
        self,
        jpeg_resolution_service: JpegResolutionService,
        pdf_assembly_service: PdfAssemblyService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        self._jpeg_resolution_service = jpeg_resolution_service
        self._pdf_assembly_service = pdf_assembly_service
        self._thumbnail_service = thumbnail_service

    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        if scanned_image.media_type != EXPECTED_MEDIA_TYPE:
            raise ScanFailedError(f"Expected {EXPECTED_MEDIA_TYPE} from the scanner, got {scanned_image.media_type}")
        request = job.request
        normalised_jpeg = self._jpeg_resolution_service.with_resolution(
            scanned_image.content, request.settings.dots_per_inch
        )
        thumbnail_jpeg = self._thumbnail_service.build_thumbnail(normalised_jpeg, THUMBNAIL_MAXIMUM_EDGE_PIXELS)
        return EncodedScan(
            content=self._build_final_content(normalised_jpeg, job),
            output_format=request.output_format,
            created_at=job.started_at,
            thumbnail_jpeg=thumbnail_jpeg,
        )

    def _build_final_content(self, normalised_jpeg: bytes, job: ScanJob) -> bytes:
        if job.request.output_format is not OutputFormat.PDF:
            return normalised_jpeg
        specification = PdfDocumentSpecification(
            dots_per_inch=job.request.settings.dots_per_inch,
            title=DEFAULT_PDF_TITLE_TEMPLATE.format(moment=job.started_at),
            created_at=job.started_at,
        )
        return self._pdf_assembly_service.build_pdf([normalised_jpeg], specification)
