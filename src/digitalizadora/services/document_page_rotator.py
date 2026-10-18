from digitalizadora.domain.document_draft import DocumentDraft
from digitalizadora.domain.errors import DamagedDocumentPageError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.document_draft_store import CapturedPage, DocumentDraftStore
from digitalizadora.services.master_jpeg_service import MasterJpegService
from digitalizadora.services.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS, ThumbnailService

ONE_QUARTER_TURN = ImageAdjustment(rotation=PageRotation.CLOCKWISE_90)


class DocumentPageRotator:
    """Turns a page of the draft a quarter clockwise (6.4); runs inside an edit of DocumentDraftService.

    The page and its thumbnail are rebuilt from the stored JPEG with the same MasterJpegService as a new scan,
    so the density and the re-encoding are the same in both paths.
    """

    def __init__(
        self,
        draft_store: DocumentDraftStore,
        master_jpeg_service: MasterJpegService,
        thumbnail_service: ThumbnailService,
    ) -> None:
        self._draft_store = draft_store
        self._master_jpeg_service = master_jpeg_service
        self._thumbnail_service = thumbnail_service

    def rotate_clockwise(self, page_identifier: str) -> DocumentDraft:
        # Refuses before decoding anything: the new file lives beside the old one for an instant.
        self._draft_store.ensure_capacity_for_replacement(page_identifier)
        stored_page = self._draft_store.read_page_content(page_identifier)
        page = stored_page.page
        settings = ScanSettings(page.dots_per_inch, page.color_mode)
        request = ScanRequest(settings, OutputFormat.JPEG, ONE_QUARTER_TURN)
        try:
            turned_jpeg = self._master_jpeg_service.build_master_jpeg(stored_page.jpeg_content, request)
            thumbnail_jpeg = self._thumbnail_service.build_thumbnail(turned_jpeg, THUMBNAIL_MAXIMUM_EDGE_PIXELS)
        except ScanFailedError as error:
            raise DamagedDocumentPageError(page_identifier, stored_page.position) from error
        return self._draft_store.replace_page(
            page_identifier, CapturedPage(turned_jpeg, thumbnail_jpeg, page.scanned_at, settings)
        )
