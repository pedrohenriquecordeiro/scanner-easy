import dataclasses
import errno
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft import (
    DocumentDraft,
    DocumentFinalizationResult,
    DocumentPage,
    DraftSnapshot,
)
from digitalizadora.domain.errors import (
    DamagedDocumentPageError,
    DraftStorageUnavailableError,
    InsufficientDraftStorageError,
    InvalidCropError,
    InvalidDocumentNameError,
    InvalidPageOrderError,
    NoOpenDocumentError,
    OutputFolderUnavailableError,
    PageNotFoundError,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.repositories.file_system_document_draft_repository import FileSystemDocumentDraftRepository
from digitalizadora.services.document_draft_store import (
    UNAVAILABLE_DRAFT_STORAGE_STATE,
    CapturedPage,
    DocumentDraftStore,
    DraftIdentitySource,
    DraftStorageState,
)
from digitalizadora.services.storage_guard_service import (
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
    read_free_space_in_bytes,
)
from tests.fakes.document_drafts import DRAFT_CREATED_AT, build_document_draft, page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.page_crops import rectangle
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.scripted_file_writer import ScriptedFileWriter
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers

WHOLE_PAGE_CROP = rectangle(0.0, 0.0, 1.0, 1.0)

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
NOW = DRAFT_CREATED_AT + timedelta(minutes=15)
SETTINGS = ScanPreset.DOCUMENT.settings
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
SECOND_PAGE_IDENTIFIER = page_identifier_at(2)
FIRST_PAGE_FILE_NAME = f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
FIRST_THUMBNAIL_FILE_NAME = f"thumbnail-{FIRST_PAGE_IDENTIFIER}.jpg"
SECOND_PAGE_FILE_NAME = f"page-{SECOND_PAGE_IDENTIFIER}.jpg"
SECOND_THUMBNAIL_FILE_NAME = f"thumbnail-{SECOND_PAGE_IDENTIFIER}.jpg"
MANIFEST_FILE_NAME = "manifest.json"
FIRST_PAGE_JPEG = b"first page jpeg"
SECOND_PAGE_JPEG = b"second page jpeg"
THUMBNAIL_JPEG = b"thumbnail jpeg"
ENOUGH_FREE_SPACE = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(SETTINGS)
FULL_DISK_ERROR = OSError(errno.ENOSPC, "No space left on device")
EXPECTED_FIRST_PAGE = DocumentPage(
    page_identifier=FIRST_PAGE_IDENTIFIER,
    scanned_at=DRAFT_CREATED_AT,
    dots_per_inch=SETTINGS.dots_per_inch,
    color_mode=SETTINGS.color_mode,
    size_in_bytes=len(FIRST_PAGE_JPEG),
)


def build_captured_page(jpeg_content: bytes, settings: ScanSettings = SETTINGS) -> CapturedPage:
    return CapturedPage(
        jpeg_content=jpeg_content, thumbnail_jpeg=THUMBNAIL_JPEG, scanned_at=DRAFT_CREATED_AT, settings=settings
    )


def build_store(draft_repository, free_space_reader: Callable[[Path], int]) -> DocumentDraftStore:
    return DocumentDraftStore(
        draft_repository,
        StorageGuardService(free_space_reader),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )


def build_store_writing_with(drafts_folder: Path, file_writer: ScriptedFileWriter) -> DocumentDraftStore:
    draft_repository = FileSystemDocumentDraftRepository(drafts_folder, file_writer, FixedClock(NOW))
    return build_store(draft_repository, RecordingFreeSpaceReader(ENOUGH_FREE_SPACE))


def list_file_names(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.iterdir())


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def draft_folder(drafts_folder: Path) -> Path:
    return drafts_folder / "current"


@pytest.fixture
def file_writer() -> ScriptedFileWriter:
    return ScriptedFileWriter({})


@pytest.fixture
def free_space_reader() -> RecordingFreeSpaceReader:
    return RecordingFreeSpaceReader(ENOUGH_FREE_SPACE)


@pytest.fixture
def draft_repository(drafts_folder: Path, file_writer: ScriptedFileWriter) -> FileSystemDocumentDraftRepository:
    return FileSystemDocumentDraftRepository(drafts_folder, file_writer, FixedClock(NOW))


@pytest.fixture
def draft_store(
    draft_repository: FileSystemDocumentDraftRepository, free_space_reader: RecordingFreeSpaceReader
) -> DocumentDraftStore:
    return build_store(draft_repository, free_space_reader)


def test_a_captured_page_with_a_frame_joins_the_draft_framed(draft_store):
    framing = PageFraming(PageRotation.NONE, (SAMPLE_CROP,))

    page = draft_store.append_page(dataclasses.replace(build_captured_page(FIRST_PAGE_JPEG), framing=framing))

    assert page.framing == framing


def test_the_frame_of_a_captured_page_is_saved_in_the_manifest(draft_store, drafts_folder):
    framing = PageFraming(PageRotation.NONE, (SAMPLE_CROP,))

    draft_store.append_page(dataclasses.replace(build_captured_page(FIRST_PAGE_JPEG), framing=framing))

    assert reopen_manifest(drafts_folder).pages[0].framing == framing


def test_a_captured_page_has_no_frame_by_default(draft_store):
    assert draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG)).framing == UNFRAMED


def test_new_store_has_no_draft_at_revision_zero_in_its_session(draft_store):
    assert draft_store.snapshot() == DraftSnapshot(draft_session=DRAFT_SESSION, revision=0, draft=None)


def test_first_page_starts_a_draft_with_that_page(draft_store):
    draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))

    assert draft_store.snapshot().draft == DocumentDraft.start(EXPECTED_FIRST_PAGE)


def test_append_page_returns_the_page_it_added(draft_store):
    assert draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG)) == EXPECTED_FIRST_PAGE


def test_first_page_creates_the_draft_folder_with_its_files(draft_store, draft_folder):
    draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))

    assert list_file_names(draft_folder) == [MANIFEST_FILE_NAME, FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME]


def test_page_files_hold_the_captured_jpeg_and_thumbnail(draft_store, draft_folder):
    draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))

    written_contents = (
        (draft_folder / FIRST_PAGE_FILE_NAME).read_bytes(),
        (draft_folder / FIRST_THUMBNAIL_FILE_NAME).read_bytes(),
    )
    assert written_contents == (FIRST_PAGE_JPEG, THUMBNAIL_JPEG)


def test_saved_manifest_matches_the_draft_in_memory(draft_store, drafts_folder):
    draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))
    draft_store.append_page(build_captured_page(SECOND_PAGE_JPEG))

    reopened_repository = FileSystemDocumentDraftRepository(drafts_folder, ScriptedFileWriter({}), FixedClock(NOW))
    assert reopened_repository.load_manifest() == draft_store.snapshot().draft


def test_next_page_is_appended_after_the_first(draft_store):
    draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))
    draft_store.append_page(build_captured_page(SECOND_PAGE_JPEG))

    assert draft_store.snapshot().draft.page_identifiers == (FIRST_PAGE_IDENTIFIER, SECOND_PAGE_IDENTIFIER)


def test_page_keeps_the_resolution_and_colour_of_its_own_settings(draft_store):
    draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))

    page = draft_store.append_page(build_captured_page(SECOND_PAGE_JPEG, ScanPreset.DOCUMENT_ECONOMY.settings))

    assert (page.dots_per_inch, page.color_mode) == (200, ColorMode.GRAYSCALE)


def test_each_appended_page_increases_the_revision_by_one(draft_store):
    draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))
    draft_store.append_page(build_captured_page(SECOND_PAGE_JPEG))

    assert draft_store.snapshot().revision == 2


def test_manifest_failure_raises_insufficient_draft_storage(drafts_folder):
    draft_store = build_store_writing_with(drafts_folder, ScriptedFileWriter({MANIFEST_FILE_NAME: FULL_DISK_ERROR}))

    with pytest.raises(InsufficientDraftStorageError):
        draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))


def test_manifest_failure_deletes_the_new_page_files(drafts_folder, draft_folder):
    draft_store = build_store_writing_with(drafts_folder, ScriptedFileWriter({MANIFEST_FILE_NAME: FULL_DISK_ERROR}))

    with pytest.raises(InsufficientDraftStorageError):
        draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))

    assert list_file_names(draft_folder) == []


def test_manifest_failure_leaves_the_snapshot_unchanged(drafts_folder):
    draft_store = build_store_writing_with(drafts_folder, ScriptedFileWriter({MANIFEST_FILE_NAME: FULL_DISK_ERROR}))
    snapshot_before = draft_store.snapshot()

    with pytest.raises(InsufficientDraftStorageError):
        draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))

    assert draft_store.snapshot() == snapshot_before


def test_page_file_failure_leaves_the_snapshot_unchanged(drafts_folder):
    draft_store = build_store_writing_with(drafts_folder, ScriptedFileWriter({FIRST_PAGE_FILE_NAME: FULL_DISK_ERROR}))
    snapshot_before = draft_store.snapshot()

    with pytest.raises(InsufficientDraftStorageError):
        draft_store.append_page(build_captured_page(FIRST_PAGE_JPEG))

    assert draft_store.snapshot() == snapshot_before


REMAINING_PAGES = 5


def test_capacity_check_prepares_the_drafts_folder(draft_store, drafts_folder):
    draft_store.ensure_capacity_for_page(SETTINGS)

    assert drafts_folder.is_dir()


def test_capacity_check_accepts_exactly_enough_space_on_the_drafts_disk(draft_store, drafts_folder, free_space_reader):
    draft_store.ensure_capacity_for_page(SETTINGS)

    assert free_space_reader.requested_folders == [drafts_folder]


def test_one_byte_less_on_the_drafts_disk_raises_insufficient_draft_storage(draft_repository):
    draft_store = build_store(draft_repository, RecordingFreeSpaceReader(ENOUGH_FREE_SPACE - 1))

    with pytest.raises(InsufficientDraftStorageError):
        draft_store.ensure_capacity_for_page(SETTINGS)


def test_capacity_check_uses_the_settings_of_the_page(draft_store):
    with pytest.raises(InsufficientDraftStorageError):
        draft_store.ensure_capacity_for_page(ScanPreset.PHOTO.settings)


def test_unreadable_free_space_raises_draft_storage_unavailable(draft_store, free_space_reader):
    free_space_reader.failure = OutputFolderUnavailableError("Cannot read the free space")

    with pytest.raises(DraftStorageUnavailableError) as raised:
        draft_store.ensure_capacity_for_page(SETTINGS)

    assert type(raised.value) is DraftStorageUnavailableError


def test_drafts_folder_that_cannot_be_created_raises_draft_storage_unavailable(tmp_path, free_space_reader):
    (tmp_path / "plain-file").write_bytes(b"not a folder")
    draft_repository = FileSystemDocumentDraftRepository(
        tmp_path / "plain-file" / "drafts", ScriptedFileWriter({}), FixedClock(NOW)
    )
    draft_store = build_store(draft_repository, free_space_reader)

    with pytest.raises(DraftStorageUnavailableError):
        draft_store.ensure_capacity_for_page(SETTINGS)


def test_describe_storage_reports_the_free_space_of_the_drafts_disk(draft_repository):
    free_space = MINIMUM_FREE_SPACE_BYTES + REMAINING_PAGES * estimated_page_bytes(SETTINGS)
    draft_store = build_store(draft_repository, RecordingFreeSpaceReader(free_space))

    assert draft_store.describe_storage(SETTINGS) == DraftStorageState(
        free_space_in_bytes=free_space, estimated_pages_remaining=REMAINING_PAGES, available=True
    )


def test_describe_storage_reads_the_drafts_folder(draft_store, drafts_folder, free_space_reader):
    draft_store.describe_storage(SETTINGS)

    assert set(free_space_reader.requested_folders) == {drafts_folder}


def test_describe_storage_of_a_missing_drafts_folder_is_unavailable(draft_repository):
    draft_store = build_store(draft_repository, read_free_space_in_bytes)

    assert draft_store.describe_storage(SETTINGS) == UNAVAILABLE_DRAFT_STORAGE_STATE


PAGE_JPEGS = (FIRST_PAGE_JPEG, SECOND_PAGE_JPEG)
UNKNOWN_PAGE_IDENTIFIER = "00000000000000ff"
DISK_FAILURE = DraftStorageUnavailableError("The internal disk failed")


class ObservedDraftRepository:
    """Delegates to the real repository, records the methods the store uses and fails the ones a test names."""

    def __init__(self, draft_repository: FileSystemDocumentDraftRepository) -> None:
        self._draft_repository = draft_repository
        self.used_method_names: list[str] = []
        self.failures_by_method_name: dict[str, Exception] = {}

    def __getattr__(self, method_name: str) -> Callable[..., object]:
        self.used_method_names.append(method_name)
        failure = self.failures_by_method_name.get(method_name)
        if failure is None:
            return getattr(self._draft_repository, method_name)
        return build_failing_method(failure)


def build_failing_method(failure: Exception) -> Callable[..., object]:
    def fail(*arguments: object) -> object:
        raise failure

    return fail


def add_pages(draft_store: DocumentDraftStore, page_count: int) -> None:
    for jpeg_content in PAGE_JPEGS[:page_count]:
        draft_store.append_page(build_captured_page(jpeg_content))


def reopen_manifest(drafts_folder: Path) -> DocumentDraft | None:
    return FileSystemDocumentDraftRepository(drafts_folder, ScriptedFileWriter({}), FixedClock(NOW)).load_manifest()


@pytest.fixture
def observed_repository(draft_repository: FileSystemDocumentDraftRepository) -> ObservedDraftRepository:
    return ObservedDraftRepository(draft_repository)


@pytest.fixture
def observed_store(
    observed_repository: ObservedDraftRepository, free_space_reader: RecordingFreeSpaceReader
) -> DocumentDraftStore:
    return build_store(observed_repository, free_space_reader)


def test_rename_keeps_the_clean_name(draft_store):
    add_pages(draft_store, 1)

    draft_store.rename("Recibo: março")

    assert draft_store.snapshot().draft.name == "Recibo- março"


def test_rename_returns_the_draft_of_the_new_snapshot(draft_store):
    add_pages(draft_store, 1)

    renamed_draft = draft_store.rename("Contrato")

    assert renamed_draft == draft_store.snapshot().draft


def test_rename_saves_the_clean_name_in_the_manifest(draft_store, drafts_folder):
    add_pages(draft_store, 1)

    draft_store.rename("Recibo: março")

    assert reopen_manifest(drafts_folder).name == "Recibo- março"


def test_accepted_edit_increases_the_revision_by_one(draft_store):
    add_pages(draft_store, 1)

    draft_store.rename("Contrato")

    assert draft_store.snapshot().revision == 2


def test_rename_without_a_draft_raises_no_open_document(draft_store):
    with pytest.raises(NoOpenDocumentError):
        draft_store.rename("Contrato")


def test_invalid_name_is_refused_before_looking_for_a_draft(draft_store):
    with pytest.raises(InvalidDocumentNameError):
        draft_store.rename("...")


def test_rename_to_the_same_clean_name_keeps_the_revision(draft_store):
    add_pages(draft_store, 1)
    draft_store.rename("Contrato")

    draft_store.rename("  Contrato  ")

    assert draft_store.snapshot().revision == 2


def test_rename_to_the_same_clean_name_writes_nothing(draft_store, file_writer):
    add_pages(draft_store, 1)
    draft_store.rename("Contrato")
    written_before = list(file_writer.written_file_names)

    draft_store.rename("  Contrato  ")

    assert file_writer.written_file_names == written_before


def test_rename_manifest_failure_keeps_the_previous_snapshot(observed_store, observed_repository):
    add_pages(observed_store, 1)
    snapshot_before = observed_store.snapshot()
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    with pytest.raises(DraftStorageUnavailableError):
        observed_store.rename("Contrato")

    assert observed_store.snapshot() == snapshot_before


def test_reorder_changes_the_page_order(draft_store):
    add_pages(draft_store, 2)

    draft_store.reorder([SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER])

    assert draft_store.snapshot().draft.page_identifiers == (SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER)


def test_reorder_saves_the_new_order_in_the_manifest(draft_store, drafts_folder):
    add_pages(draft_store, 2)

    draft_store.reorder([SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER])

    assert reopen_manifest(drafts_folder).page_identifiers == (SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER)


def test_reorder_that_is_not_a_permutation_raises_invalid_page_order(draft_store):
    add_pages(draft_store, 2)

    with pytest.raises(InvalidPageOrderError):
        draft_store.reorder([FIRST_PAGE_IDENTIFIER])


def test_reorder_with_the_current_order_keeps_the_revision(draft_store):
    add_pages(draft_store, 2)

    draft_store.reorder([FIRST_PAGE_IDENTIFIER, SECOND_PAGE_IDENTIFIER])

    assert draft_store.snapshot().revision == 2


def test_reorder_with_the_current_order_writes_nothing(draft_store, file_writer):
    add_pages(draft_store, 2)
    written_before = list(file_writer.written_file_names)

    draft_store.reorder([FIRST_PAGE_IDENTIFIER, SECOND_PAGE_IDENTIFIER])

    assert file_writer.written_file_names == written_before


def test_reorder_without_a_draft_raises_no_open_document(draft_store):
    with pytest.raises(NoOpenDocumentError):
        draft_store.reorder([])


def test_delete_page_removes_it_from_the_draft(draft_store):
    add_pages(draft_store, 2)

    draft_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert draft_store.snapshot().draft.page_identifiers == (SECOND_PAGE_IDENTIFIER,)


def test_delete_page_returns_the_draft_of_the_new_snapshot(draft_store):
    add_pages(draft_store, 2)

    remaining_draft = draft_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert remaining_draft == draft_store.snapshot().draft


def test_delete_page_removes_its_files(draft_store, draft_folder):
    add_pages(draft_store, 2)

    draft_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert list_file_names(draft_folder) == [MANIFEST_FILE_NAME, SECOND_PAGE_FILE_NAME, SECOND_THUMBNAIL_FILE_NAME]


def test_delete_page_saves_the_manifest_before_deleting_the_files(observed_store, observed_repository):
    add_pages(observed_store, 2)
    observed_repository.used_method_names.clear()

    observed_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert observed_repository.used_method_names == ["save_manifest", "delete_page_files"]


def test_delete_page_manifest_failure_keeps_the_page_files(observed_store, observed_repository, draft_folder):
    add_pages(observed_store, 2)
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    with pytest.raises(DraftStorageUnavailableError):
        observed_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert {FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME} <= set(list_file_names(draft_folder))


def test_delete_page_manifest_failure_keeps_the_previous_snapshot(observed_store, observed_repository):
    add_pages(observed_store, 2)
    snapshot_before = observed_store.snapshot()
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    with pytest.raises(DraftStorageUnavailableError):
        observed_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert observed_store.snapshot() == snapshot_before


def test_deleting_the_only_page_ends_the_draft(draft_store):
    add_pages(draft_store, 1)

    remaining_draft = draft_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert (remaining_draft, draft_store.snapshot().draft) == (None, None)


def test_deleting_the_only_page_removes_the_draft_folder(draft_store, draft_folder):
    add_pages(draft_store, 1)

    draft_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert not draft_folder.exists()


def test_failure_to_delete_the_only_page_keeps_the_draft(observed_store, observed_repository):
    add_pages(observed_store, 1)
    snapshot_before = observed_store.snapshot()
    observed_repository.failures_by_method_name["delete_draft"] = DISK_FAILURE

    with pytest.raises(DraftStorageUnavailableError):
        observed_store.delete_page(FIRST_PAGE_IDENTIFIER)

    assert observed_store.snapshot() == snapshot_before


@pytest.mark.parametrize("page_identifier", [UNKNOWN_PAGE_IDENTIFIER, "last", "../x"])
def test_delete_page_outside_the_draft_raises_page_not_found(draft_store, page_identifier):
    add_pages(draft_store, 1)

    with pytest.raises(PageNotFoundError):
        draft_store.delete_page(page_identifier)


def test_delete_page_without_a_draft_raises_no_open_document(draft_store):
    with pytest.raises(NoOpenDocumentError):
        draft_store.delete_page(FIRST_PAGE_IDENTIFIER)


def test_discard_last_page_removes_the_last_page(draft_store):
    add_pages(draft_store, 2)

    draft_store.discard_last_page()

    assert draft_store.snapshot().draft.page_identifiers == (FIRST_PAGE_IDENTIFIER,)


def test_discard_last_page_removes_its_files(draft_store, draft_folder):
    add_pages(draft_store, 2)

    draft_store.discard_last_page()

    assert list_file_names(draft_folder) == [MANIFEST_FILE_NAME, FIRST_PAGE_FILE_NAME, FIRST_THUMBNAIL_FILE_NAME]


def test_discarding_the_only_page_ends_the_draft(draft_store):
    add_pages(draft_store, 1)

    remaining_draft = draft_store.discard_last_page()

    assert (remaining_draft, draft_store.snapshot().draft) == (None, None)


def test_discard_last_page_without_a_draft_raises_no_open_document(draft_store):
    with pytest.raises(NoOpenDocumentError):
        draft_store.discard_last_page()


def test_discard_ends_the_draft(draft_store):
    add_pages(draft_store, 1)

    draft_store.discard()

    assert draft_store.snapshot().draft is None


def test_discard_deletes_the_draft_folder(draft_store, draft_folder):
    add_pages(draft_store, 1)

    draft_store.discard()

    assert not draft_folder.exists()


def test_discard_without_a_draft_changes_nothing(draft_store):
    snapshot_before = draft_store.snapshot()

    draft_store.discard()

    assert draft_store.snapshot() == snapshot_before


def test_discard_failure_to_delete_the_manifest_keeps_the_draft(observed_store, observed_repository):
    add_pages(observed_store, 1)
    snapshot_before = observed_store.snapshot()
    observed_repository.failures_by_method_name["delete_draft"] = DISK_FAILURE

    with pytest.raises(DraftStorageUnavailableError):
        observed_store.discard()

    assert observed_store.snapshot() == snapshot_before


def test_read_thumbnail_of_a_page_of_the_draft(draft_store):
    add_pages(draft_store, 1)

    assert draft_store.read_thumbnail(FIRST_PAGE_IDENTIFIER) == THUMBNAIL_JPEG


def test_read_thumbnail_of_a_page_outside_the_draft_is_none(draft_store, draft_folder):
    add_pages(draft_store, 1)
    (draft_folder / f"thumbnail-{UNKNOWN_PAGE_IDENTIFIER}.jpg").write_bytes(THUMBNAIL_JPEG)

    assert draft_store.read_thumbnail(UNKNOWN_PAGE_IDENTIFIER) is None


def test_read_thumbnail_without_a_draft_is_none(draft_store):
    assert draft_store.read_thumbnail(FIRST_PAGE_IDENTIFIER) is None


FINALIZED_AT = NOW + timedelta(minutes=5)
FINISHED_PDF_PATH = Path("/Volumes/Arquivo/Contrato.pdf")
FINALIZATION = DocumentFinalizationResult(
    result=ScanResult(
        output_path=FINISHED_PDF_PATH, output_format=OutputFormat.PDF, scanned_at=FINALIZED_AT, size_in_bytes=1234
    ),
    page_count=1,
)


def build_finished_draft(finished_pdf_path: Path) -> DocumentDraft:
    finished_document = ScanResult(
        output_path=finished_pdf_path, output_format=OutputFormat.PDF, scanned_at=FINALIZED_AT, size_in_bytes=3
    )
    return build_document_draft(1).marked_finished(finished_document)


def test_draft_with_the_finished_mark_and_its_pdf_is_finished(draft_store, tmp_path):
    (tmp_path / "Contrato.pdf").write_bytes(b"pdf")

    assert draft_store.is_finished_document_present(build_finished_draft(tmp_path / "Contrato.pdf")) is True


def test_draft_whose_finished_pdf_is_missing_is_not_finished(draft_store, tmp_path):
    assert draft_store.is_finished_document_present(build_finished_draft(tmp_path / "Contrato.pdf")) is False


def test_draft_without_the_finished_mark_is_not_finished(draft_store):
    assert draft_store.is_finished_document_present(build_document_draft(1)) is False


def test_verify_page_files_returns_the_page_paths_in_the_draft_order(draft_store, draft_folder):
    add_pages(draft_store, 2)
    reordered_draft = draft_store.snapshot().draft.reordered([SECOND_PAGE_IDENTIFIER, FIRST_PAGE_IDENTIFIER])

    assert draft_store.verify_page_files(reordered_draft) == [
        draft_folder / SECOND_PAGE_FILE_NAME,
        draft_folder / FIRST_PAGE_FILE_NAME,
    ]


def test_missing_page_file_raises_damaged_page_with_its_position(draft_store, draft_folder):
    add_pages(draft_store, 2)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    with pytest.raises(DamagedDocumentPageError) as raised:
        draft_store.verify_page_files(draft_store.snapshot().draft)

    assert (raised.value.page_identifier, raised.value.page_position) == (SECOND_PAGE_IDENTIFIER, 2)


def test_page_file_of_another_size_raises_damaged_page_with_its_position(draft_store, draft_folder):
    add_pages(draft_store, 2)
    (draft_folder / FIRST_PAGE_FILE_NAME).write_bytes(b"truncated")

    with pytest.raises(DamagedDocumentPageError) as raised:
        draft_store.verify_page_files(draft_store.snapshot().draft)

    assert (raised.value.page_identifier, raised.value.page_position) == (FIRST_PAGE_IDENTIFIER, 1)


def test_mark_finalization_started_writes_the_intention_in_the_manifest(draft_store, drafts_folder):
    add_pages(draft_store, 1)

    draft_store.mark_finalization_started(FINALIZED_AT)

    assert reopen_manifest(drafts_folder).finalization_started_at == FINALIZED_AT


def test_mark_finalization_started_keeps_the_snapshot(draft_store):
    add_pages(draft_store, 1)
    snapshot_before = draft_store.snapshot()

    draft_store.mark_finalization_started(FINALIZED_AT)

    assert draft_store.snapshot() == snapshot_before


def test_failure_to_mark_the_finalization_is_only_logged(observed_store, observed_repository, caplog):
    add_pages(observed_store, 1)
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    observed_store.mark_finalization_started(FINALIZED_AT)

    assert [record.levelname for record in caplog.records] == ["WARNING"]


def test_clear_finalization_marker_rewrites_the_manifest_of_the_snapshot(draft_store, drafts_folder):
    add_pages(draft_store, 1)
    draft_store.mark_finalization_started(FINALIZED_AT)

    draft_store.clear_finalization_marker()

    assert reopen_manifest(drafts_folder) == draft_store.snapshot().draft


def test_failure_to_clear_the_finalization_marker_is_only_logged(observed_store, observed_repository, caplog):
    add_pages(observed_store, 1)
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    observed_store.clear_finalization_marker()

    assert [record.levelname for record in caplog.records] == ["WARNING"]


def test_closing_a_finished_draft_ends_the_draft(draft_store):
    add_pages(draft_store, 1)

    draft_store.close_finished_draft(FINALIZATION)

    assert draft_store.snapshot().draft is None


def test_closing_a_finished_draft_deletes_the_draft_folder(draft_store, draft_folder):
    add_pages(draft_store, 1)

    draft_store.close_finished_draft(FINALIZATION)

    assert not draft_folder.exists()


def test_closing_a_finished_draft_remembers_the_finalization(draft_store):
    add_pages(draft_store, 1)

    draft_store.close_finished_draft(FINALIZATION)

    assert draft_store.snapshot().last_finished_document == FINALIZATION


def test_closing_a_finished_draft_counts_as_one_more_revision(draft_store):
    add_pages(draft_store, 1)

    draft_store.close_finished_draft(FINALIZATION)

    assert draft_store.snapshot().revision == 2


def test_closing_records_the_finished_mark_before_deleting_the_draft(observed_store, observed_repository):
    add_pages(observed_store, 1)
    observed_repository.used_method_names.clear()

    observed_store.close_finished_draft(FINALIZATION)

    assert observed_repository.used_method_names == ["save_manifest", "delete_draft"]


def test_closing_with_a_failed_finished_mark_still_deletes_the_draft(observed_store, observed_repository, draft_folder):
    add_pages(observed_store, 1)
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    observed_store.close_finished_draft(FINALIZATION)

    assert not draft_folder.exists()


def test_closing_with_the_mark_and_the_cleanup_failing_keeps_the_draft_marked_finished(
    observed_store, observed_repository
):
    add_pages(observed_store, 1)
    draft = observed_store.snapshot().draft
    observed_repository.failures_by_method_name.update(save_manifest=DISK_FAILURE, delete_draft=DISK_FAILURE)

    observed_store.close_finished_draft(FINALIZATION)

    assert observed_store.snapshot().draft == draft.marked_finished(FINALIZATION.result)


def test_closing_with_the_cleanup_failing_still_remembers_the_finalization(observed_store, observed_repository):
    add_pages(observed_store, 1)
    observed_repository.failures_by_method_name.update(save_manifest=DISK_FAILURE, delete_draft=DISK_FAILURE)

    observed_store.close_finished_draft(FINALIZATION)

    assert observed_store.snapshot().last_finished_document == FINALIZATION


def test_next_accepted_change_forgets_the_last_finished_document(draft_store):
    add_pages(draft_store, 1)
    draft_store.close_finished_draft(FINALIZATION)

    add_pages(draft_store, 1)

    assert draft_store.snapshot().last_finished_document is None


def test_capacity_check_accepts_exactly_enough_space(draft_store):
    assert draft_store.ensure_capacity_for_page(SETTINGS) is None


def test_describe_storage_estimates_the_pages_by_the_quality_alone(draft_repository):
    free_space = MINIMUM_FREE_SPACE_BYTES + 10 * estimated_page_bytes(SETTINGS)
    draft_store = build_store(draft_repository, RecordingFreeSpaceReader(free_space))

    assert draft_store.describe_storage(SETTINGS).estimated_pages_remaining == 10


def test_read_page_content_returns_the_page_its_position_and_its_file(draft_store):
    add_pages(draft_store, 2)

    stored_page = draft_store.read_page_content(SECOND_PAGE_IDENTIFIER)

    assert (stored_page.page.page_identifier, stored_page.position, stored_page.jpeg_content) == (
        SECOND_PAGE_IDENTIFIER,
        2,
        SECOND_PAGE_JPEG,
    )


def test_read_page_content_without_a_draft_raises_no_open_document(draft_store):
    with pytest.raises(NoOpenDocumentError):
        draft_store.read_page_content(FIRST_PAGE_IDENTIFIER)


def test_read_page_content_of_an_unknown_page_raises_page_not_found(draft_store):
    add_pages(draft_store, 1)

    with pytest.raises(PageNotFoundError):
        draft_store.read_page_content(UNKNOWN_PAGE_IDENTIFIER)


def test_read_page_content_of_a_missing_file_raises_damaged_document_page(draft_store, draft_folder):
    add_pages(draft_store, 2)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    with pytest.raises(DamagedDocumentPageError) as raised:
        draft_store.read_page_content(SECOND_PAGE_IDENTIFIER)

    assert (raised.value.page_identifier, raised.value.page_position) == (SECOND_PAGE_IDENTIFIER, 2)


def test_read_page_content_of_a_file_with_another_size_raises_damaged_document_page(draft_store, draft_folder):
    add_pages(draft_store, 1)
    (draft_folder / FIRST_PAGE_FILE_NAME).write_bytes(FIRST_PAGE_JPEG + b"!")

    with pytest.raises(DamagedDocumentPageError):
        draft_store.read_page_content(FIRST_PAGE_IDENTIFIER)


SAMPLE_CROP = rectangle(0.125, 0.115, 0.9, 0.925)
TURNED_SAMPLE_CROP = rectangle(0.075, 0.125, 0.885, 0.9)


def test_turning_a_page_adds_a_quarter_turn_to_its_rotation(draft_store):
    add_pages(draft_store, 2)

    draft_store.turn_page_clockwise(SECOND_PAGE_IDENTIFIER)

    assert [page.framing.rotation for page in draft_store.snapshot().draft.pages] == [
        PageRotation.NONE,
        PageRotation.CLOCKWISE_90,
    ]


def test_turning_a_page_turns_its_crop_with_it(draft_store):
    add_pages(draft_store, 1)
    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    assert draft_store.snapshot().draft.pages[0].framing.crops == (TURNED_SAMPLE_CROP,)


def test_turning_a_page_keeps_its_identifier_and_position(draft_store):
    add_pages(draft_store, 2)

    turned_draft = draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    assert turned_draft.page_identifiers == (FIRST_PAGE_IDENTIFIER, SECOND_PAGE_IDENTIFIER)


def test_turning_a_page_returns_the_draft_of_the_new_snapshot(draft_store):
    add_pages(draft_store, 1)

    assert draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER) == draft_store.snapshot().draft


def test_turning_a_page_increases_the_revision_by_one(draft_store):
    add_pages(draft_store, 1)

    draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    assert draft_store.snapshot().revision == 2


def test_turning_a_page_saves_the_rotation_in_the_manifest(draft_store, drafts_folder):
    add_pages(draft_store, 1)

    draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    assert reopen_manifest(drafts_folder).pages[0].framing.rotation is PageRotation.CLOCKWISE_90


def read_page_and_thumbnail_files(draft_folder: Path) -> dict[str, bytes]:
    return {entry.name: entry.read_bytes() for entry in draft_folder.iterdir() if entry.name != MANIFEST_FILE_NAME}


def test_turning_a_page_leaves_its_files_as_the_scanner_made_them(draft_store, draft_folder):
    add_pages(draft_store, 1)
    files_before = read_page_and_thumbnail_files(draft_folder)

    draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    assert read_page_and_thumbnail_files(draft_folder) == files_before


def test_turning_a_page_writes_only_the_manifest(draft_store, file_writer):
    add_pages(draft_store, 1)
    written_before = len(file_writer.written_file_names)

    draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    assert file_writer.written_file_names[written_before:] == [MANIFEST_FILE_NAME]


def test_turning_a_page_without_a_draft_raises_no_open_document(draft_store):
    with pytest.raises(NoOpenDocumentError):
        draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)


@pytest.mark.parametrize("page_identifier", [UNKNOWN_PAGE_IDENTIFIER, "last", "../x"])
def test_turning_a_page_outside_the_draft_raises_page_not_found(draft_store, page_identifier):
    add_pages(draft_store, 1)

    with pytest.raises(PageNotFoundError):
        draft_store.turn_page_clockwise(page_identifier)


def test_turning_a_page_manifest_failure_keeps_the_previous_snapshot(observed_store, observed_repository):
    add_pages(observed_store, 1)
    snapshot_before = observed_store.snapshot()
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    with pytest.raises(DraftStorageUnavailableError):
        observed_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    assert observed_store.snapshot() == snapshot_before


def test_setting_a_crop_stores_it_in_the_page(draft_store):
    add_pages(draft_store, 2)

    draft_store.set_page_crops(SECOND_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert [page.framing.crops for page in draft_store.snapshot().draft.pages] == [(), (SAMPLE_CROP,)]


def test_setting_two_crops_stores_them_in_reading_order(draft_store):
    add_pages(draft_store, 1)
    left_crop = rectangle(0.05, 0.1, 0.45, 0.9)
    right_crop = rectangle(0.55, 0.1, 0.95, 0.9)

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [right_crop, left_crop])

    assert draft_store.snapshot().draft.pages[0].framing.crops == (left_crop, right_crop)


def test_setting_three_crops_is_refused_and_changes_nothing(draft_store):
    add_pages(draft_store, 1)
    snapshot_before = draft_store.snapshot()

    with pytest.raises(InvalidCropError):
        draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP, SAMPLE_CROP, SAMPLE_CROP])

    assert draft_store.snapshot() == snapshot_before


def test_setting_a_crop_returns_the_draft_of_the_new_snapshot(draft_store):
    add_pages(draft_store, 1)

    assert draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP]) == draft_store.snapshot().draft


def test_setting_a_crop_increases_the_revision_by_one(draft_store):
    add_pages(draft_store, 1)

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert draft_store.snapshot().revision == 2


def test_setting_a_crop_saves_it_in_the_manifest(draft_store, drafts_folder):
    add_pages(draft_store, 1)

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert reopen_manifest(drafts_folder).pages[0].framing.crops == (SAMPLE_CROP,)


def test_setting_a_crop_keeps_the_rotation_of_the_page(draft_store):
    add_pages(draft_store, 1)
    draft_store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert draft_store.snapshot().draft.pages[0].framing.rotation is PageRotation.CLOCKWISE_90


def test_setting_no_crop_removes_the_crop(draft_store):
    add_pages(draft_store, 1)
    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [])

    assert draft_store.snapshot().draft.pages[0].framing.crops == ()


def test_setting_a_crop_of_the_whole_page_removes_the_crop(draft_store):
    add_pages(draft_store, 1)
    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [WHOLE_PAGE_CROP])

    assert draft_store.snapshot().draft.pages[0].framing.crops == ()


def test_setting_the_same_crop_keeps_the_revision(draft_store):
    add_pages(draft_store, 1)
    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert draft_store.snapshot().revision == 2


def test_setting_the_same_crop_writes_nothing(draft_store, file_writer):
    add_pages(draft_store, 1)
    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])
    written_before = list(file_writer.written_file_names)

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert file_writer.written_file_names == written_before


def test_removing_a_crop_that_is_not_there_keeps_the_revision(draft_store):
    add_pages(draft_store, 1)

    draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [])

    assert draft_store.snapshot().revision == 1


def test_setting_a_crop_without_a_draft_raises_no_open_document(draft_store):
    with pytest.raises(NoOpenDocumentError):
        draft_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])


@pytest.mark.parametrize("page_identifier", [UNKNOWN_PAGE_IDENTIFIER, "last", "../x"])
def test_setting_a_crop_outside_the_draft_raises_page_not_found(draft_store, page_identifier):
    add_pages(draft_store, 1)

    with pytest.raises(PageNotFoundError):
        draft_store.set_page_crops(page_identifier, [SAMPLE_CROP])


def test_setting_a_crop_manifest_failure_keeps_the_previous_snapshot(observed_store, observed_repository):
    add_pages(observed_store, 1)
    snapshot_before = observed_store.snapshot()
    observed_repository.failures_by_method_name["save_manifest"] = DISK_FAILURE

    with pytest.raises(DraftStorageUnavailableError):
        observed_store.set_page_crops(FIRST_PAGE_IDENTIFIER, [SAMPLE_CROP])

    assert observed_store.snapshot() == snapshot_before
