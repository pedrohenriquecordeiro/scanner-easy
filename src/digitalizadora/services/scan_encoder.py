from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.master_jpeg_service import MasterJpegService
from digitalizadora.services.pdf_assembly_service import (
    DEFAULT_PDF_TITLE_TEMPLATE,
    PdfAssemblyService,
    PdfDocumentSpecification,
)
from digitalizadora.services.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS, ThumbnailService

EXPECTED_MEDIA_TYPE = "image/jpeg"


class ScanEncoder:
    def __init__(
        self,
        master_jpeg_service: MasterJpegService,
        pdf_assembly_service: PdfAssemblyService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        self._master_jpeg_service = master_jpeg_service
        self._pdf_assembly_service = pdf_assembly_service
        self._thumbnail_service = thumbnail_service

    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        if scanned_image.media_type != EXPECTED_MEDIA_TYPE:
            raise ScanFailedError(f"Expected {EXPECTED_MEDIA_TYPE} from the scanner, got {scanned_image.media_type}")
        request = job.request
        master_jpeg = self._master_jpeg_service.build_master_jpeg(scanned_image.content, request)
        thumbnail_jpeg = self._thumbnail_service.build_thumbnail(master_jpeg, THUMBNAIL_MAXIMUM_EDGE_PIXELS)
        return EncodedScan(
            content=self._build_final_content(master_jpeg, job),
            output_format=request.output_format,
            created_at=job.started_at,
            thumbnail_jpeg=thumbnail_jpeg,
        )

    def _build_final_content(self, master_jpeg: bytes, job: ScanJob) -> bytes:
        if job.request.output_format is not OutputFormat.PDF:
            return master_jpeg
        specification = PdfDocumentSpecification(
            dots_per_inch=job.request.settings.dots_per_inch,
            title=DEFAULT_PDF_TITLE_TEMPLATE.format(moment=job.started_at),
            created_at=job.started_at,
        )
        return self._pdf_assembly_service.build_pdf([master_jpeg], specification)
