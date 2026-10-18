import logging
from dataclasses import replace

from digitalizadora.domain.document_draft import DocumentPage
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.document_draft_store import CapturedPage, DocumentDraftStore
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.scan_encoder import ScanEncoder

LOGGER = logging.getLogger(__name__)


class DocumentPageCapture:
    """The ScanDestination[DocumentPage] of the document mode: the scanned page joins the draft.

    The page keeps the JPEG of the scanner. The automatic crop becomes the frame of the page, a suggestion
    the user can adjust, and is applied only when the PDF is written. Both methods run in a worker thread of
    the single scan sequence of ScanService.
    """

    def __init__(
        self,
        scan_encoder: ScanEncoder,
        draft_store: DocumentDraftStore,
        crop_detection_service: PageCropDetectionService,
    ) -> None:
        self._scan_encoder = scan_encoder
        self._draft_store = draft_store
        self._crop_detection_service = crop_detection_service

    def ensure_capacity(self, request: ScanRequest) -> None:
        # The page is stored as the scanner made it: no re-encoding to leave room for.
        self._draft_store.ensure_capacity_for_page(request.settings)

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> DocumentPage:
        # DocumentDraftService always asks for JPEG: the encoded content is the normalised master JPEG.
        unadjusted_job = replace(job, request=replace(job.request, adjustment=NO_ADJUSTMENT))
        encoded_scan = self._scan_encoder.encode(scanned_image, unadjusted_job)
        return self._draft_store.append_page(
            CapturedPage(
                jpeg_content=encoded_scan.content,
                thumbnail_jpeg=encoded_scan.thumbnail_jpeg,
                scanned_at=job.started_at,
                settings=job.request.settings,
                framing=self._suggest_framing(encoded_scan.content, job),
            )
        )

    def _suggest_framing(self, jpeg_content: bytes, job: ScanJob) -> PageFraming:
        if not job.request.adjustment.auto_crop:
            return UNFRAMED
        try:
            return PageFraming(crop=self._crop_detection_service.detect_crop_to_suggest(jpeg_content))
        except DigitalizadoraError:
            # A failed suggestion never costs the page: it joins the draft whole and the user can frame it.
            LOGGER.warning("The automatic crop of the page failed; the page was kept whole", exc_info=True)
            return UNFRAMED
