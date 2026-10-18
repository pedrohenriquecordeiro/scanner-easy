import asyncio
import functools
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from digitalizadora.domain.documents.document_draft import (
    DocumentDraft,
    DocumentFinalizationResult,
    DocumentPage,
    DraftSnapshot,
)
from digitalizadora.domain.errors import (
    DocumentBusyError,
    EmptyDocumentError,
    NoOpenDocumentError,
    ScanAlreadyRunningError,
)
from digitalizadora.domain.imaging.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.imaging.page_crop import PageCrop
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import Clock
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.documents.document_draft_store import DocumentDraftStore, DraftStorageState
from digitalizadora.services.documents.document_finalizer import DocumentFinalizer
from digitalizadora.services.documents.document_page_crop_detector import CropDetectionResult, DocumentPageCropDetector
from digitalizadora.services.documents.document_page_view_service import DocumentPageViewService
from digitalizadora.services.documents.document_pdf_assembler import DocumentAssemblyInput
from digitalizadora.services.scan_service import ScanService


@dataclass(frozen=True)
class DocumentDraftCollaborators:
    """The pieces the document service drives; the page scanner already knows its destination."""

    draft_store: DocumentDraftStore
    page_scanner: Callable[[ScanRequest], Awaitable[DocumentPage]]
    finalizer: DocumentFinalizer
    page_cropper: DocumentPageCropDetector
    page_views: DocumentPageViewService


class DocumentDraftService:
    """Owner of the single lock of the draft changes (6.6.7).

    Adding a page holds the lock for the whole scan and never waits for it (R17). The edits wait for the
    lock, refuse to run during a scan and run their disk work in a worker thread.
    """

    def __init__(self, scan_service: ScanService, collaborators: DocumentDraftCollaborators, clock: Clock) -> None:
        self._scan_service = scan_service
        self._draft_store = collaborators.draft_store
        self._page_scanner = collaborators.page_scanner
        self._finalizer = collaborators.finalizer
        self._page_cropper = collaborators.page_cropper
        self._page_views = collaborators.page_views
        self._clock = clock
        self._lock = asyncio.Lock()
        # Edits waiting for the lock: right after a release, locked() is False while a woken waiter has
        # not run yet, and acquire() would then queue the page behind it.
        self._waiting_edit_count = 0

    def recover_draft(self) -> None:
        self._draft_store.recover()

    def snapshot(self) -> DraftSnapshot:
        return self._draft_store.snapshot()

    def describe_draft_storage(self, settings: ScanSettings) -> DraftStorageState:
        return self._draft_store.describe_storage(settings)

    def read_thumbnail(self, page_identifier: str, rotation: PageRotation) -> bytes | None:
        # No lock: a thumbnail file never changes after it is written.
        return self._page_views.read_thumbnail(page_identifier, rotation)

    def read_preview(self, page_identifier: str, rotation: PageRotation) -> bytes:
        # No lock either: the stored page never changes, and a deleted one fails like a missing file.
        return self._page_views.read_preview(page_identifier, rotation)

    def ensure_can_add_page(self) -> None:
        self._scan_service.ensure_scan_can_start()
        if self._lock.locked() or self._waiting_edit_count:
            raise DocumentBusyError("Another change to the document draft is in progress")

    async def add_page(self, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> DocumentPage:
        self.ensure_can_add_page()
        # No await between the check and taking the lock: with no holder and no edit waiting, a free
        # asyncio.Lock is taken without yielding to the event loop, so the page never waits (R17).
        async with self._lock:
            return await self._page_scanner(
                ScanRequest(settings=settings, output_format=OutputFormat.JPEG, adjustment=adjustment)
            )

    async def rename(self, raw_name: str) -> DocumentDraft:
        return await self._run_edit(functools.partial(self._draft_store.rename, raw_name))

    async def reorder(self, page_identifiers: Sequence[str]) -> DocumentDraft:
        return await self._run_edit(functools.partial(self._draft_store.reorder, page_identifiers))

    async def delete_page(self, page_identifier: str) -> DocumentDraft | None:
        return await self._run_edit(functools.partial(self._draft_store.delete_page, page_identifier))

    async def rotate_page(self, page_identifier: str) -> DocumentDraft:
        return await self._run_edit(functools.partial(self._draft_store.turn_page_clockwise, page_identifier))

    async def set_page_crops(self, page_identifier: str, crops: Sequence[PageCrop]) -> DocumentDraft:
        return await self._run_edit(functools.partial(self._draft_store.set_page_crops, page_identifier, crops))

    async def detect_page_crops(self, page_identifier: str) -> CropDetectionResult:
        return await self._run_edit(functools.partial(self._page_cropper.detect_for_page, page_identifier))

    async def discard_last_page(self) -> DocumentDraft | None:
        return await self._run_edit(self._draft_store.discard_last_page)

    async def cancel(self) -> None:
        await self._run_edit(self._draft_store.discard)

    async def finalize(self) -> DocumentFinalizationResult:
        return await self._run_edit(self._finalize_draft)

    async def _run_edit[EditOutcome](self, edit: Callable[[], EditOutcome]) -> EditOutcome:
        self._ensure_no_scan_in_progress()
        self._waiting_edit_count += 1
        try:
            await self._lock.acquire()
        finally:
            self._waiting_edit_count -= 1
        try:
            # A quick scan may have started while this edit waited for the lock.
            self._ensure_no_scan_in_progress()
            return await asyncio.to_thread(edit)
        finally:
            self._lock.release()

    def _ensure_no_scan_in_progress(self) -> None:
        if self._scan_service.is_scan_in_progress():
            raise ScanAlreadyRunningError("A scan is already running")

    def _finalize_draft(self) -> DocumentFinalizationResult:
        """6.6.3, all in one worker thread."""
        draft = self._draft_store.snapshot().draft
        if draft is None:
            raise NoOpenDocumentError("There is no document draft to finalize")
        if draft.page_count == 0:
            raise EmptyDocumentError("The document draft has no pages")
        if self._draft_store.is_finished_document_present(draft):
            # The PDF of an earlier finalization exists: close the draft without writing another one (R15).
            finished_document = draft.finished_document
        else:
            finished_document = self._write_document(draft)
        finalization = DocumentFinalizationResult(result=finished_document, page_count=draft.output_page_count)
        self._draft_store.close_finished_draft(finalization)
        return finalization

    def _write_document(self, draft: DocumentDraft) -> ScanResult:
        self._finalizer.ensure_capacity(draft)
        page_files = self._draft_store.verify_page_files(draft)
        finalized_at = self._clock.now()
        self._draft_store.mark_finalization_started(finalized_at)
        try:
            return self._finalizer.write_document(DocumentAssemblyInput(draft, page_files, finalized_at))
        except Exception:
            # The draft stays intact; the intention marker of step 5 goes away (best effort).
            self._draft_store.clear_finalization_marker()
            raise
