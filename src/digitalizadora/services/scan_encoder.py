from dataclasses import dataclass
from datetime import datetime

from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scanning.scan_job import ScanJob
from digitalizadora.domain.scanning.scanned_image import ScannedImage
from digitalizadora.services.imaging.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS, ThumbnailService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.pdf_assembly_service import (
    DEFAULT_PDF_TITLE_TEMPLATE,
    PdfAssemblyService,
    PdfDocumentSpecification,
)

EXPECTED_MEDIA_TYPE = "image/jpeg"


@dataclass(frozen=True)
class EncodedMaster:
    """The master of a scan: the scanner JPEG with the density of the request, and a small thumbnail of it."""

    jpeg_content: bytes
    thumbnail_jpeg: bytes


@dataclass(frozen=True)
class OutputIdentity:
    """What an output file is made with besides its image: when it was scanned, how dense and in which format."""

    created_at: datetime
    dots_per_inch: int
    output_format: OutputFormat


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

    def encode_master(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedMaster:
        """The scanner image, untouched but for the density; the thumbnail is of the master as it comes."""
        if scanned_image.media_type != EXPECTED_MEDIA_TYPE:
            raise ScanFailedError(f"Expected {EXPECTED_MEDIA_TYPE} from the scanner, got {scanned_image.media_type}")
        master_jpeg = self._jpeg_resolution_service.with_resolution(
            scanned_image.content, job.request.settings.dots_per_inch
        )
        thumbnail_jpeg = self._thumbnail_service.build_thumbnail(master_jpeg, THUMBNAIL_MAXIMUM_EDGE_PIXELS)
        return EncodedMaster(jpeg_content=master_jpeg, thumbnail_jpeg=thumbnail_jpeg)

    def wrap_output(self, output_jpeg: bytes, identity: OutputIdentity) -> EncodedScan:
        """A JPG as it is; a PDF with the page at the fixed density, so it has the physical size of the image."""
        if identity.output_format is not OutputFormat.PDF:
            return EncodedScan(output_jpeg, identity.output_format, identity.created_at)
        specification = PdfDocumentSpecification(
            dots_per_inch=identity.dots_per_inch,
            title=DEFAULT_PDF_TITLE_TEMPLATE.format(moment=identity.created_at),
            created_at=identity.created_at,
        )
        return EncodedScan(
            self._pdf_assembly_service.build_pdf([output_jpeg], specification), OutputFormat.PDF, identity.created_at
        )
