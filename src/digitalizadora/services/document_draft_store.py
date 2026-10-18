import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from digitalizadora.domain.document_draft import (
    FIRST_PAGE_POSITION,
    DocumentDraft,
    DocumentFinalizationResult,
    DocumentPage,
    DocumentPageFiles,
    DraftRecoveryReport,
    DraftSnapshot,
    RecoveryOutcome,
)
from digitalizadora.domain.document_draft_reconciliation import DraftFileInventory, DraftReconciliation, reconcile_draft
from digitalizadora.domain.document_name_policy import clean_document_name
from digitalizadora.domain.errors import (
    DamagedDocumentPageError,
    DigitalizadoraError,
    DraftStorageUnavailableError,
    InsufficientStorageError,
    NoOpenDocumentError,
    OutputFolderUnavailableError,
    UnreadableDraftError,
    as_draft_storage_error,
)
from digitalizadora.domain.page_crop import PageCrop
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.ports import DocumentDraftRepository
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.services.storage_guard_service import StorageGuardService

LOGGER = logging.getLogger(__name__)

INITIAL_REVISION = 0


@dataclass(frozen=True)
class CapturedPage:
    """A scanned page already encoded by the ScanEncoder, before it joins the draft."""

    jpeg_content: bytes
    thumbnail_jpeg: bytes
    scanned_at: datetime
    settings: ScanSettings
    framing: PageFraming = UNFRAMED


@dataclass(frozen=True)
class StoredPage:
    """A page of the draft with the content of its file, read to be rewritten."""

    page: DocumentPage
    position: int
    jpeg_content: bytes


@dataclass(frozen=True)
class DraftIdentitySource:
    """The draft session of this process (R19) and the factory of new page identifiers."""

    draft_session: str
    page_identifier_factory: Callable[[], str]


@dataclass(frozen=True)
class DraftStorageState:
    """Free space of the disk that holds the draft, for the interface (R20)."""

    free_space_in_bytes: int
    estimated_pages_remaining: int
    available: bool


UNAVAILABLE_DRAFT_STORAGE_STATE = DraftStorageState(free_space_in_bytes=0, estimated_pages_remaining=0, available=False)
FAILED_RECOVERY_REPORT = DraftRecoveryReport(
    outcome=RecoveryOutcome.FAILED, kept_page_count=0, dropped_page_positions=(), set_aside_folder=None
)


def _page_from_capture(page_identifier: str, captured_page: CapturedPage) -> DocumentPage:
    return DocumentPage(
        page_identifier=page_identifier,
        scanned_at=captured_page.scanned_at,
        dots_per_inch=captured_page.settings.dots_per_inch,
        color_mode=captured_page.settings.color_mode,
        size_in_bytes=len(captured_page.jpeg_content),
        framing=captured_page.framing,
    )


class DocumentDraftStore:
    """The draft in progress: its snapshot in memory and its files on the internal disk.

    Synchronous. The methods that change the draft run only in a thread opened by DocumentDraftService
    while it holds its lock, or at start-up before the server answers. Every accepted change ends by
    replacing the whole DraftSnapshot in one assignment, so snapshot() read from another thread is
    always coherent and never touches the disk.
    """

    def __init__(
        self,
        draft_repository: DocumentDraftRepository,
        storage_guard_service: StorageGuardService,
        identity_source: DraftIdentitySource,
    ) -> None:
        self._draft_repository = draft_repository
        self._storage_guard_service = storage_guard_service
        self._identity_source = identity_source
        self._snapshot = DraftSnapshot(
            draft_session=identity_source.draft_session, revision=INITIAL_REVISION, draft=None
        )
        self._recovery_failed = False

    def snapshot(self) -> DraftSnapshot:
        return self._snapshot

    def append_page(self, captured_page: CapturedPage) -> DocumentPage:
        """The page and its thumbnail first, the manifest last (6.6.1): a crash never lists a missing file."""
        page_identifier = self._identity_source.page_identifier_factory()
        current_draft = self._snapshot.draft
        if current_draft is None:
            self._clear_leftovers()
            self._draft_repository.ensure_draft_folder_exists()
        self._draft_repository.write_page_files(
            DocumentPageFiles(page_identifier, captured_page.jpeg_content, captured_page.thumbnail_jpeg)
        )
        page = _page_from_capture(page_identifier, captured_page)
        new_draft = DocumentDraft.start(page) if current_draft is None else current_draft.with_page_appended(page)
        try:
            self._draft_repository.save_manifest(new_draft)
        except DigitalizadoraError:
            self._draft_repository.delete_page_files(page_identifier)
            raise
        self._replace_snapshot(new_draft)
        return page

    def _replace_snapshot(
        self, draft: DocumentDraft | None, last_finished_document: DocumentFinalizationResult | None = None
    ) -> None:
        self._snapshot = DraftSnapshot(
            draft_session=self._snapshot.draft_session,
            revision=self._snapshot.revision + 1,
            draft=draft,
            last_finished_document=last_finished_document,
        )

    def describe_storage(self, settings: ScanSettings) -> DraftStorageState:
        storage_folder = self._draft_repository.storage_folder()
        try:
            return DraftStorageState(
                free_space_in_bytes=self._storage_guard_service.free_space_in_bytes(storage_folder),
                estimated_pages_remaining=self._storage_guard_service.estimate_pages_remaining(
                    storage_folder, settings
                ),
                available=True,
            )
        except OutputFolderUnavailableError:
            return UNAVAILABLE_DRAFT_STORAGE_STATE

    def ensure_capacity_for_page(self, settings: ScanSettings) -> None:
        """Runs before the printer spends 15 to 75 s on the page (6.6.1, step 3)."""
        self._ensure_recovered()
        self._draft_repository.ensure_storage_folder_ready()
        storage_folder = self._draft_repository.storage_folder()
        try:
            self._storage_guard_service.ensure_space_for_scan(storage_folder, settings)
        except (InsufficientStorageError, OutputFolderUnavailableError) as error:
            # The draft lives on the internal disk: the quick-mode messages would point at the output folder.
            raise as_draft_storage_error(error) from error

    def _ensure_recovered(self) -> None:
        if self._recovery_failed:
            # current/ may hold a valid draft that only could not be read now: a new first page would set it
            # aside, so new pages wait for the next start, which recovers again (R13).
            raise DraftStorageUnavailableError("The draft folder could not be recovered at start-up")

    def read_page_content(self, page_identifier: str) -> StoredPage:
        draft = self._require_draft()
        position = draft.position_of(page_identifier)
        page = draft.pages[position - FIRST_PAGE_POSITION]
        jpeg_content = self._draft_repository.read_page_file(page_identifier)
        if jpeg_content is None or len(jpeg_content) != page.size_in_bytes:
            raise DamagedDocumentPageError(page_identifier, position)
        return StoredPage(page, position, jpeg_content)

    def turn_page_clockwise(self, page_identifier: str) -> DocumentDraft:
        """Only the manifest changes: the page keeps its identifier and the JPEG of the scanner (D2)."""
        draft = self._require_draft()
        page = draft.pages[draft.position_of(page_identifier) - FIRST_PAGE_POSITION]
        return self._save_and_replace(draft.with_page_framing(page_identifier, page.framing.turned_clockwise()))

    def set_page_crop(self, page_identifier: str, crop: PageCrop | None) -> DocumentDraft:
        draft = self._require_draft()
        page = draft.pages[draft.position_of(page_identifier) - FIRST_PAGE_POSITION]
        framing = page.framing.with_crop(crop)
        if framing == page.framing:
            return draft
        return self._save_and_replace(draft.with_page_framing(page_identifier, framing))

    def rename(self, raw_name: str) -> DocumentDraft:
        document_name = clean_document_name(raw_name)
        draft = self._require_draft()
        if document_name == draft.name:
            return draft
        return self._save_and_replace(draft.renamed(document_name))

    def reorder(self, page_identifiers: Sequence[str]) -> DocumentDraft:
        draft = self._require_draft()
        reordered_draft = draft.reordered(page_identifiers)
        if reordered_draft.page_identifiers == draft.page_identifiers:
            return draft
        return self._save_and_replace(reordered_draft)

    def delete_page(self, page_identifier: str) -> DocumentDraft | None:
        remaining_draft = self._require_draft().without_page(page_identifier)
        return self._remove_page(remaining_draft, page_identifier)

    def discard_last_page(self) -> DocumentDraft | None:
        draft = self._require_draft()
        remaining_draft = draft.without_last_page()
        return self._remove_page(remaining_draft, draft.page_identifiers[-1])

    def discard(self) -> None:
        if self._snapshot.draft is None:
            return
        self._draft_repository.delete_draft()
        self._replace_snapshot(None)

    def read_thumbnail(self, page_identifier: str) -> bytes | None:
        draft = self._snapshot.draft
        if draft is None or page_identifier not in draft.page_identifiers:
            return None
        return self._draft_repository.read_thumbnail(page_identifier)

    def _require_draft(self) -> DocumentDraft:
        draft = self._snapshot.draft
        if draft is None:
            raise NoOpenDocumentError("There is no document draft in progress")
        return draft

    def _save_and_replace(self, draft: DocumentDraft) -> DocumentDraft:
        self._draft_repository.save_manifest(draft)
        self._replace_snapshot(draft)
        return draft

    def _remove_page(self, remaining_draft: DocumentDraft, page_identifier: str) -> DocumentDraft | None:
        if remaining_draft.page_count == 0:
            # A stored draft always has at least one page (R3): removing the last one ends the draft.
            self._draft_repository.delete_draft()
            self._replace_snapshot(None)
            return None
        # The manifest first: a crash never leaves it listing a file that was already deleted.
        self._save_and_replace(remaining_draft)
        self._draft_repository.delete_page_files(page_identifier)
        return remaining_draft

    def is_finished_document_present(self, draft: DocumentDraft) -> bool:
        finished_document = draft.finished_document
        if finished_document is None:
            return False
        return self._draft_repository.finished_document_exists(finished_document.output_path)

    def verify_page_files(self, draft: DocumentDraft) -> list[Path]:
        """Every page must exist with the size of the manifest before the PDF is assembled (R18)."""
        for position, page in enumerate(draft.pages, FIRST_PAGE_POSITION):
            if self._draft_repository.page_file_size(page.page_identifier) != page.size_in_bytes:
                raise DamagedDocumentPageError(page.page_identifier, position)
        return [self._draft_repository.page_file_path(page.page_identifier) for page in draft.pages]

    def mark_finalization_started(self, started_at: datetime) -> None:
        """Only on disk (R16): the snapshot keeps the draft without the intention marker."""
        self._save_manifest_best_effort(
            self._require_draft().with_finalization_started(started_at), "the finalization intention"
        )

    def clear_finalization_marker(self) -> None:
        self._save_manifest_best_effort(self._require_draft(), "the draft without the finalization intention")

    def close_finished_draft(self, finalization: DocumentFinalizationResult) -> None:
        """Never raises: the PDF already exists, so a cleanup that fails keeps the draft marked finished (R16)."""
        finished_draft = self._require_draft().marked_finished(finalization.result)
        self._save_manifest_best_effort(finished_draft, "the finished document mark")
        try:
            self._draft_repository.delete_draft()
        except DigitalizadoraError:
            LOGGER.warning("Could not delete the finished draft; it stays in memory marked finished", exc_info=True)
            self._replace_snapshot(finished_draft, finalization)
            return
        self._replace_snapshot(None, finalization)

    def _save_manifest_best_effort(self, draft: DocumentDraft, saved_change: str) -> None:
        try:
            self._draft_repository.save_manifest(draft)
        except DigitalizadoraError:
            LOGGER.warning("Could not save %s in the draft manifest", saved_change, exc_info=True)

    def _clear_leftovers(self) -> None:
        """Whatever current/ holds when no draft is in memory (6.6.8): only the disposable is deleted (R14)."""
        try:
            leftover_draft = self._draft_repository.load_manifest()
        except UnreadableDraftError as error:
            LOGGER.warning("The leftover draft manifest is unreadable: %s", error)
            self._set_leftover_aside()
            return
        if leftover_draft is None:
            # Never confirmed, or left by a cancellation: page, thumbnail and temporary files only.
            self._draft_repository.delete_files(self._draft_repository.take_inventory().known_file_names)
        elif self.is_finished_document_present(leftover_draft):
            self._draft_repository.delete_draft()
        else:
            self._set_leftover_aside()

    def _set_leftover_aside(self) -> None:
        set_aside_folder = self._draft_repository.set_aside_draft_folder()
        LOGGER.warning("Set the leftover draft folder aside as %s", set_aside_folder)

    def recover(self) -> None:
        """Runs once at start-up, after claim_exclusive_access and before the server answers (6.6.2).

        The revision stays at its initial value: recovering sets only the draft and the recovery report.
        Never raises, so the server always starts. A failure leaves current/ as it was (nothing before
        step 7 deletes anything), starts without a draft and blocks new pages until the next start (R13).
        """
        try:
            self._recover_from_disk()
        except Exception:  # any failure, even an unexpected one, must not keep the server from starting
            LOGGER.exception("Could not recover the document draft; new pages wait for the next start")
            self._recovery_failed = True
            self._finish_recovery(None, FAILED_RECOVERY_REPORT)

    def _recover_from_disk(self) -> None:
        inventory = self._draft_repository.take_inventory()
        try:
            recorded_draft = self._draft_repository.load_manifest()
        except UnreadableDraftError as error:
            self._set_unreadable_draft_aside(error)
            return
        self._warn_about_unknown_files(inventory)
        if recorded_draft is None:
            self._delete_unconfirmed_files(inventory)
        elif self.is_finished_document_present(recorded_draft):
            self._delete_draft_already_saved(recorded_draft)
        else:
            # A finished mark whose PDF cannot be confirmed now stays: the draft comes back with it (R15).
            self._resume(reconcile_draft(recorded_draft, inventory))

    def _set_unreadable_draft_aside(self, error: UnreadableDraftError) -> None:
        """Only an unreadable manifest sets the whole folder aside, with every file in it (R13)."""
        set_aside_folder = self._draft_repository.set_aside_draft_folder()
        LOGGER.warning(
            "The draft manifest is unreadable (%s); set the draft folder aside as %s", error, set_aside_folder
        )
        self._finish_recovery(
            None,
            DraftRecoveryReport(
                outcome=RecoveryOutcome.SET_ASIDE,
                kept_page_count=0,
                dropped_page_positions=(),
                set_aside_folder=set_aside_folder,
            ),
        )

    def _warn_about_unknown_files(self, inventory: DraftFileInventory) -> None:
        if inventory.unknown_file_names:
            LOGGER.warning(
                "Left the unknown files of the draft folder alone: %s", ", ".join(sorted(inventory.unknown_file_names))
            )

    def _delete_unconfirmed_files(self, inventory: DraftFileInventory) -> None:
        """Without a manifest, no page, thumbnail or temporary file was ever confirmed (R14)."""
        known_file_names = inventory.known_file_names
        if known_file_names:
            LOGGER.warning("Deleting %d unconfirmed files left in the draft folder", len(known_file_names))
            self._draft_repository.delete_files(known_file_names)

    def _delete_draft_already_saved(self, recorded_draft: DocumentDraft) -> None:
        """The finished mark points at a PDF that exists now: deleting the draft never duplicates it (R15)."""
        self._draft_repository.delete_draft()
        LOGGER.info("The draft was already saved as %s; deleted it", recorded_draft.finished_document.output_path)

    def _finish_recovery(self, draft: DocumentDraft | None, recovery_report: DraftRecoveryReport | None) -> None:
        self._snapshot = replace(self._snapshot, draft=draft, recovery_report=recovery_report)

    def _resume(self, reconciliation: DraftReconciliation) -> None:
        """Keeps the pages whose file has the recorded size, in the manifest order, with the name and both marks."""
        dropped_page_positions = reconciliation.dropped_page_positions
        for position in dropped_page_positions:
            LOGGER.warning("Page %d of the recovered draft is missing or has an unexpected size; dropped it", position)
        set_aside_folder = self._set_damaged_pages_aside(reconciliation.files_to_set_aside)
        recovered_draft = reconciliation.draft
        if recovered_draft.page_count == 0:
            self._draft_repository.delete_draft()
            if dropped_page_positions:  # a manifest that already listed no page has nothing to report
                self._finish_recovery(
                    None,
                    DraftRecoveryReport(
                        outcome=RecoveryOutcome.PAGES_LOST,
                        kept_page_count=0,
                        dropped_page_positions=dropped_page_positions,
                        set_aside_folder=set_aside_folder,
                    ),
                )
            return
        if dropped_page_positions:
            # Not fatal (R13): the manifest on disk keeps listing the dropped pages, and the next start
            # reconciles it the same way.
            self._save_manifest_best_effort(recovered_draft, "the recovered draft without its dropped pages")
        self._draft_repository.delete_files(reconciliation.files_to_delete)
        self._finish_recovery(
            recovered_draft,
            DraftRecoveryReport(
                outcome=RecoveryOutcome.RESUMED,
                kept_page_count=recovered_draft.page_count,
                dropped_page_positions=dropped_page_positions,
                set_aside_folder=set_aside_folder,
            ),
        )

    def _set_damaged_pages_aside(self, file_names: Sequence[str]) -> Path | None:
        """A confirmed page with an unexpected size is moved aside, never deleted (R14)."""
        if not file_names:
            return None
        set_aside_folder = self._draft_repository.set_aside_files(file_names)
        LOGGER.warning("Set the pages with an unexpected size aside in %s", set_aside_folder)
        return set_aside_folder
