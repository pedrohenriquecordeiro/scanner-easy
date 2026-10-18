from digitalizadora.domain.document_draft import DocumentPage
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.document_draft_store import CapturedPage, DocumentDraftStore
from digitalizadora.services.scan_encoder import ScanEncoder


class DocumentPageCapture:
    """The ScanDestination[DocumentPage] of the document mode: the scanned page joins the draft.

    Both methods run in a worker thread of the single scan sequence of ScanService.
    """

    def __init__(self, scan_encoder: ScanEncoder, draft_store: DocumentDraftStore) -> None:
        self._scan_encoder = scan_encoder
        self._draft_store = draft_store

    def ensure_capacity(self, request: ScanRequest) -> None:
        self._draft_store.ensure_capacity_for_page(request.settings)

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> DocumentPage:
        # DocumentDraftService always asks for JPEG: the encoded content is the normalised master JPEG.
        encoded_scan = self._scan_encoder.encode(scanned_image, job)
        return self._draft_store.append_page(
            CapturedPage(
                jpeg_content=encoded_scan.content,
                thumbnail_jpeg=encoded_scan.thumbnail_jpeg,
                scanned_at=job.started_at,
                settings=job.request.settings,
            )
        )
