from dataclasses import dataclass

from digitalizadora.domain.documents.document_draft import DocumentDraft
from digitalizadora.domain.errors import DamagedDocumentPageError, ScanFailedError
from digitalizadora.services.documents.document_draft_store import DocumentDraftStore
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService


@dataclass(frozen=True)
class CropDetectionResult:
    draft: DocumentDraft
    crops_detected: bool
    ignored_region_count: int


class DocumentPageCropDetector:
    """Looks for the sheet again on a page of the draft; runs inside an edit of DocumentDraftService.

    When nothing is found the frames stay as they were and the draft is not touched.
    """

    def __init__(
        self, draft_store: DocumentDraftStore, crop_detection_service: PageCropDetectionService
    ) -> None:
        self._draft_store = draft_store
        self._crop_detection_service = crop_detection_service

    def detect_for_page(self, page_identifier: str) -> CropDetectionResult:
        stored_page = self._draft_store.read_page_content(page_identifier)
        try:
            detected = self._crop_detection_service.detect_crops(stored_page.jpeg_content)
        except ScanFailedError as error:
            raise DamagedDocumentPageError(page_identifier, stored_page.position) from error
        if not detected.crops:
            return CropDetectionResult(self._current_draft(), False, detected.ignored_region_count)
        # The detection ran on the stored JPEG; the frames are kept in the orientation the page is displayed in.
        displayed_crops = stored_page.page.framing.crops_from_master(detected.crops)
        draft = self._draft_store.set_page_crops(page_identifier, displayed_crops)
        return CropDetectionResult(draft, True, detected.ignored_region_count)

    def _current_draft(self) -> DocumentDraft:
        return self._draft_store.snapshot().draft
