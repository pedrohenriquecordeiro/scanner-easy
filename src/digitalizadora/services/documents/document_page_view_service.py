from digitalizadora.domain.errors import DamagedDocumentPageError, NoOpenDocumentError, ScanFailedError
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.services.documents.document_draft_store import DocumentDraftStore
from digitalizadora.services.page_image_view_service import (
    ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS,
    PageImageViewService,
)
from digitalizadora.services.thumbnail_service import THUMBNAIL_MAXIMUM_EDGE_PIXELS


class DocumentPageViewService:
    """The images the page of the document mode shows, turned as the manifest says; no lock is taken.

    A page file never changes after it is written, so a read that runs beside an edit sees a whole file.
    """

    def __init__(self, draft_store: DocumentDraftStore, image_view_service: PageImageViewService) -> None:
        self._draft_store = draft_store
        self._image_view_service = image_view_service

    def read_thumbnail(self, page_identifier: str, rotation: PageRotation) -> bytes | None:
        """None when the page is not in the draft. The stored thumbnail is the one of the unturned page."""
        thumbnail_jpeg = self._draft_store.read_thumbnail(page_identifier)
        if thumbnail_jpeg is None or rotation is PageRotation.NONE:
            return thumbnail_jpeg
        try:
            return self._image_view_service.build_view(thumbnail_jpeg, rotation, THUMBNAIL_MAXIMUM_EDGE_PIXELS)
        except ScanFailedError as error:
            raise DamagedDocumentPageError(page_identifier, self._position_of(page_identifier)) from error

    def read_preview(self, page_identifier: str, rotation: PageRotation) -> bytes:
        stored_page = self._draft_store.read_page_content(page_identifier)
        try:
            return self._image_view_service.build_view(
                stored_page.jpeg_content, rotation, ENLARGED_VIEW_MAXIMUM_EDGE_PIXELS
            )
        except ScanFailedError as error:
            raise DamagedDocumentPageError(page_identifier, stored_page.position) from error

    def _position_of(self, page_identifier: str) -> int:
        draft = self._draft_store.snapshot().draft
        if draft is None:
            raise NoOpenDocumentError("There is no document draft in progress")
        return draft.position_of(page_identifier)
