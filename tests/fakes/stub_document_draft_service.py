from collections.abc import Sequence
from pathlib import Path

from digitalizadora.domain.document_draft import DocumentDraft, DocumentFinalizationResult, DocumentPage, DraftSnapshot
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.document_draft_store import DraftStorageState
from digitalizadora.services.document_page_crop_detector import CropDetectionResult
from tests.fakes.document_drafts import DRAFT_CREATED_AT, build_document_draft, build_document_page, page_identifier_at

STUB_DRAFT_SESSION = "5c0f9a2e7b1d4c38"
STUB_DRAFT_STORAGE = DraftStorageState(
    free_space_in_bytes=80_000_000_000, estimated_pages_remaining=9000, available=True
)
STUB_FINALIZATION = DocumentFinalizationResult(
    result=ScanResult(
        output_path=Path("/Volumes/External/scans/Contrato do apartamento.pdf"),
        output_format=OutputFormat.PDF,
        scanned_at=DRAFT_CREATED_AT,
        size_in_bytes=1612246,
    ),
    page_count=2,
)
NO_PAGES = 0


def build_stub_snapshot(page_count: int) -> DraftSnapshot:
    """A snapshot whose revision equals the page count; zero pages means no draft."""
    draft = None if page_count == NO_PAGES else build_document_draft(page_count)
    return DraftSnapshot(draft_session=STUB_DRAFT_SESSION, revision=page_count, draft=draft)


class StubDocumentDraftService:
    """Duck-typed stand-in for DocumentDraftService for the controllers: records calls and fails on demand.

    add_page_refusal is raised by ensure_can_add_page; failure is raised by add_page and by every edit.
    An operation that succeeds replaces draft_snapshot with snapshot_after_edit when one is set.
    """

    def __init__(self, draft_snapshot: DraftSnapshot) -> None:
        self.draft_snapshot = draft_snapshot
        self.snapshot_after_edit: DraftSnapshot | None = None
        self.draft_storage = STUB_DRAFT_STORAGE
        self.add_page_refusal: Exception | None = None
        self.failure: Exception | None = None
        self.finalization = STUB_FINALIZATION
        self.crop_detected = True
        self.thumbnails: dict[str, bytes] = {}
        self.previews: dict[str, bytes] = {}
        self.read_thumbnail_failure: Exception | None = None
        self.calls: list[str] = []
        self.received_arguments: dict[str, object] = {}

    def snapshot(self) -> DraftSnapshot:
        return self.draft_snapshot

    def describe_draft_storage(self, settings: ScanSettings) -> DraftStorageState:
        self.received_arguments["describe_draft_storage"] = settings
        return self.draft_storage

    def ensure_can_add_page(self) -> None:
        self.calls.append("ensure_can_add_page")
        if self.add_page_refusal is not None:
            raise self.add_page_refusal

    def read_thumbnail(self, page_identifier: str, rotation: PageRotation) -> bytes | None:
        self.received_arguments["read_thumbnail"] = (page_identifier, rotation)
        if self.read_thumbnail_failure is not None:
            raise self.read_thumbnail_failure
        return self.thumbnails.get(page_identifier)

    def read_preview(self, page_identifier: str, rotation: PageRotation) -> bytes:
        self.received_arguments["read_preview"] = (page_identifier, rotation)
        if self.failure is not None:
            raise self.failure
        return self.previews[page_identifier]

    async def add_page(self, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> DocumentPage:
        self._record("add_page", (settings, adjustment))
        return build_document_page(page_identifier_at(1))

    async def rename(self, raw_name: str) -> DocumentDraft | None:
        self._record("rename", raw_name)
        return self.draft_snapshot.draft

    async def reorder(self, page_identifiers: Sequence[str]) -> DocumentDraft | None:
        self._record("reorder", page_identifiers)
        return self.draft_snapshot.draft

    async def delete_page(self, page_identifier: str) -> DocumentDraft | None:
        self._record("delete_page", page_identifier)
        return self.draft_snapshot.draft

    async def rotate_page(self, page_identifier: str) -> DocumentDraft | None:
        self._record("rotate_page", page_identifier)
        return self.draft_snapshot.draft

    async def set_page_crop(self, page_identifier: str, crop: PageCrop | None) -> DocumentDraft | None:
        self._record("set_page_crop", (page_identifier, crop))
        return self.draft_snapshot.draft

    async def detect_page_crop(self, page_identifier: str) -> CropDetectionResult:
        self._record("detect_page_crop", page_identifier)
        return CropDetectionResult(self.draft_snapshot.draft, self.crop_detected)

    async def discard_last_page(self) -> DocumentDraft | None:
        self._record("discard_last_page", None)
        return self.draft_snapshot.draft

    async def cancel(self) -> None:
        self._record("cancel", None)

    async def finalize(self) -> DocumentFinalizationResult:
        self._record("finalize", None)
        return self.finalization

    def _record(self, operation: str, argument: object) -> None:
        self.calls.append(operation)
        self.received_arguments[operation] = argument
        if self.failure is not None:
            raise self.failure
        if self.snapshot_after_edit is not None:
            self.draft_snapshot = self.snapshot_after_edit
