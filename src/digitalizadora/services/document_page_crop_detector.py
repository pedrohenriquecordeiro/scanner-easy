from dataclasses import dataclass

from digitalizadora.domain.document_draft import DocumentDraft
from digitalizadora.domain.errors import DamagedDocumentPageError, ScanFailedError
from digitalizadora.services.document_draft_store import DocumentDraftStore
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
            master_crop = self._crop_detection_service.detect_crop_to_suggest(stored_page.jpeg_content)
        except ScanFailedError as error:
            raise DamagedDocumentPageError(page_identifier, stored_page.position) from error
        if master_crop is None:
            return CropDetectionResult(self._current_draft(), crops_detected=False, ignored_region_count=0)
        # The detection ran on the stored JPEG; the frame is kept in the orientation the page is displayed in.
        displayed_crops = stored_page.page.framing.crops_from_master([master_crop])
        draft = self._draft_store.set_page_crops(page_identifier, displayed_crops)
        return CropDetectionResult(draft, crops_detected=True, ignored_region_count=0)

    def _current_draft(self) -> DocumentDraft:
        return self._draft_store.snapshot().draft
