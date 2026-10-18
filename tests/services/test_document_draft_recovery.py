import errno
import json
import logging
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.document_draft import DocumentDraft, DraftRecoveryReport, DraftSnapshot, RecoveryOutcome
from digitalizadora.domain.errors import DraftStorageUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.repositories.document_manifest_codec import encode_manifest
from digitalizadora.repositories.file_system_document_draft_repository import FileSystemDocumentDraftRepository
from digitalizadora.services.document_draft_store import DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, build_document_draft, page_identifier_at, write_draft_folder
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.scripted_file_writer import ScriptedFileWriter
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
NOW = DRAFT_CREATED_AT + timedelta(minutes=15)
FREE_SPACE_IN_BYTES = 10 * 1024**3
STORE_LOGGER_NAME = "digitalizadora.services.document_draft_store"
CURRENT_FOLDER_NAME = "current"
MANIFEST_FILE_NAME = "manifest.json"
RECORDED_DRAFT = replace(build_document_draft(3), name="Contrato do apartamento")
RECORDED_DRAFT_FILE_NAMES = sorted(
    [MANIFEST_FILE_NAME]
    + [f"page-{page_identifier}.jpg" for page_identifier in RECORDED_DRAFT.page_identifiers]
    + [f"thumbnail-{page_identifier}.jpg" for page_identifier in RECORDED_DRAFT.page_identifiers]
)
ORPHAN_PAGE_IDENTIFIER = "00000000000000aa"
ORPHAN_PAGE_FILE_NAME = f"page-{ORPHAN_PAGE_IDENTIFIER}.jpg"
ORPHAN_THUMBNAIL_FILE_NAME = f"thumbnail-{ORPHAN_PAGE_IDENTIFIER}.jpg"
TEMPORARY_FILE_NAME = f".{ORPHAN_PAGE_FILE_NAME}.4242-0a1b2c3d.part"
UNKNOWN_FILE_NAME = ".DS_Store"
FINISHED_PDF_NAME = "Contrato do apartamento.pdf"
INITIAL_SNAPSHOT = DraftSnapshot(draft_session=DRAFT_SESSION, revision=0, draft=None)
SECOND_PAGE_IDENTIFIER = page_identifier_at(2)
SECOND_PAGE_FILE_NAME = f"page-{SECOND_PAGE_IDENTIFIER}.jpg"
SECOND_THUMBNAIL_FILE_NAME = f"thumbnail-{SECOND_PAGE_IDENTIFIER}.jpg"
DRAFT_WITHOUT_SECOND_PAGE = RECORDED_DRAFT.without_page(SECOND_PAGE_IDENTIFIER)
WRONG_SIZE_CONTENT = b"wrong size"
FULL_DISK_ERROR = OSError(errno.ENOSPC, "No space left on device")
CLOSED_FOLDER_MODE = 0o000
SETTINGS = ScanPreset.DOCUMENT.settings
UNLISTABLE_FOLDER_MODE = 0o300
UNREADABLE_FILE_MODE = 0o000
READ_ONLY_FOLDER_MODE = 0o500
FAILED_SNAPSHOT = replace(
    INITIAL_SNAPSHOT,
    recovery_report=DraftRecoveryReport(
        outcome=RecoveryOutcome.FAILED, kept_page_count=0, dropped_page_positions=(), set_aside_folder=None
    ),
)
requires_permission_bits = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permission bits")


def recorded_manifest_document() -> dict:
    return json.loads(encode_manifest(RECORDED_DRAFT))


def manifest_with_format_version_two() -> bytes:
    manifest_document = recorded_manifest_document()
    manifest_document["format_version"] = 2
    return json.dumps(manifest_document).encode()


def manifest_with_a_repeated_page() -> bytes:
    manifest_document = recorded_manifest_document()
    manifest_document["pages"].append(manifest_document["pages"][0])
    return json.dumps(manifest_document).encode()


UNREADABLE_MANIFESTS = {
    "cut JSON": encode_manifest(RECORDED_DRAFT)[:40],
    "empty file": b"",
    "format version 2": manifest_with_format_version_two(),
    "repeated page identifier": manifest_with_a_repeated_page(),
}


def build_finished_draft(finished_pdf_path: Path) -> DocumentDraft:
    finished_document = ScanResult(
        output_path=finished_pdf_path, output_format=OutputFormat.PDF, scanned_at=NOW, size_in_bytes=3
    )
    return RECORDED_DRAFT.with_finalization_started(NOW).marked_finished(finished_document)


def write_files(draft_folder: Path, file_names: list[str]) -> None:
    draft_folder.mkdir(parents=True, exist_ok=True)
    for file_name in file_names:
        (draft_folder / file_name).write_bytes(b"leftover")


def build_store(drafts_folder: Path, file_writer: ScriptedFileWriter) -> DocumentDraftStore:
    """A new store on the folder, as if the process had just reopened (6.6.2)."""
    return DocumentDraftStore(
        FileSystemDocumentDraftRepository(drafts_folder, file_writer, FixedClock(NOW)),
        StorageGuardService(RecordingFreeSpaceReader(FREE_SPACE_IN_BYTES)),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )


def list_file_names(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.iterdir())


def find_set_aside_folder(drafts_folder: Path) -> Path:
    [set_aside_folder] = drafts_folder.glob("set-aside-*")
    return set_aside_folder


def resumed_report(
    kept_page_count: int, dropped_page_positions: tuple[int, ...] = (), set_aside_folder: Path | None = None
) -> DraftRecoveryReport:
    return DraftRecoveryReport(
        outcome=RecoveryOutcome.RESUMED,
        kept_page_count=kept_page_count,
        dropped_page_positions=dropped_page_positions,
        set_aside_folder=set_aside_folder,
    )


@contextmanager
def permission_mode(path: Path, mode: int) -> Iterator[None]:
    """Changes the permission bits of path only inside the block, so tmp_path can always be cleaned."""
    original_mode = stat.S_IMODE(path.stat().st_mode)
    path.chmod(mode)
    try:
        yield
    finally:
        path.chmod(original_mode)


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def draft_folder(drafts_folder: Path) -> Path:
    return drafts_folder / CURRENT_FOLDER_NAME


@pytest.fixture
def file_writer() -> ScriptedFileWriter:
    return ScriptedFileWriter({})


@pytest.fixture
def draft_store(drafts_folder: Path, file_writer: ScriptedFileWriter) -> DocumentDraftStore:
    return build_store(drafts_folder, file_writer)


@pytest.fixture
def recorded_draft_folder(drafts_folder: Path, draft_folder: Path) -> Path:
    """The folder of RECORDED_DRAFT, written as the previous run left it: manifest, pages and thumbnails."""
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    return draft_folder


@pytest.fixture
def missing_finished_pdf(tmp_path: Path) -> Path:
    return tmp_path / FINISHED_PDF_NAME


@pytest.fixture
def existing_finished_pdf(tmp_path: Path) -> Path:
    finished_pdf_path = tmp_path / FINISHED_PDF_NAME
    finished_pdf_path.write_bytes(b"pdf")
    return finished_pdf_path


def test_missing_drafts_folder_recovers_no_draft_and_no_report(draft_store):
    draft_store.recover()

    assert draft_store.snapshot() == INITIAL_SNAPSHOT


def test_missing_drafts_folder_is_not_created(draft_store, drafts_folder):
    draft_store.recover()

    assert not drafts_folder.exists()


def test_files_without_a_manifest_are_deleted(draft_store, draft_folder):
    write_files(draft_folder, [ORPHAN_PAGE_FILE_NAME, ORPHAN_THUMBNAIL_FILE_NAME, TEMPORARY_FILE_NAME])

    draft_store.recover()

    assert list_file_names(draft_folder) == []


def test_files_without_a_manifest_recover_no_draft_and_no_report(draft_store, draft_folder):
    write_files(draft_folder, [ORPHAN_PAGE_FILE_NAME, ORPHAN_THUMBNAIL_FILE_NAME, TEMPORARY_FILE_NAME])

    draft_store.recover()

    assert draft_store.snapshot() == INITIAL_SNAPSHOT


def test_files_left_after_the_manifest_was_deleted_are_deleted(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / MANIFEST_FILE_NAME).unlink()

    draft_store.recover()

    assert list_file_names(draft_folder) == []


def test_unknown_file_without_a_manifest_is_kept(draft_store, draft_folder):
    write_files(draft_folder, [ORPHAN_PAGE_FILE_NAME, UNKNOWN_FILE_NAME])

    draft_store.recover()

    assert list_file_names(draft_folder) == [UNKNOWN_FILE_NAME]


def test_unknown_file_without_a_manifest_is_reported_with_a_warning(draft_store, draft_folder, caplog):
    write_files(draft_folder, [UNKNOWN_FILE_NAME])

    with caplog.at_level(logging.WARNING, logger=STORE_LOGGER_NAME):
        draft_store.recover()

    assert [(record.levelno, UNKNOWN_FILE_NAME in record.getMessage()) for record in caplog.records] == [
        (logging.WARNING, True)
    ]


@pytest.mark.parametrize("manifest_content", list(UNREADABLE_MANIFESTS.values()), ids=list(UNREADABLE_MANIFESTS))
def test_unreadable_manifest_is_reported_as_set_aside(draft_store, drafts_folder, manifest_content):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (drafts_folder / CURRENT_FOLDER_NAME / MANIFEST_FILE_NAME).write_bytes(manifest_content)

    draft_store.recover()

    assert draft_store.snapshot() == replace(
        INITIAL_SNAPSHOT,
        recovery_report=DraftRecoveryReport(
            outcome=RecoveryOutcome.SET_ASIDE,
            kept_page_count=0,
            dropped_page_positions=(),
            set_aside_folder=find_set_aside_folder(drafts_folder),
        ),
    )


def test_unreadable_manifest_sets_the_draft_folder_aside_with_all_its_files(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    write_files(draft_folder, [TEMPORARY_FILE_NAME, UNKNOWN_FILE_NAME])
    (draft_folder / MANIFEST_FILE_NAME).write_bytes(b"")

    draft_store.recover()

    assert list_file_names(find_set_aside_folder(drafts_folder)) == sorted(
        [*RECORDED_DRAFT_FILE_NAMES, TEMPORARY_FILE_NAME, UNKNOWN_FILE_NAME]
    )


def test_unreadable_manifest_leaves_no_current_draft_folder(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / MANIFEST_FILE_NAME).write_bytes(b"")

    draft_store.recover()

    assert not draft_folder.exists()


def test_draft_whose_pdf_exists_is_deleted(draft_store, drafts_folder, existing_finished_pdf):
    write_draft_folder(drafts_folder, build_finished_draft(existing_finished_pdf))

    draft_store.recover()

    assert not (drafts_folder / CURRENT_FOLDER_NAME).exists()


def test_draft_whose_pdf_exists_recovers_no_draft_and_no_report(draft_store, drafts_folder, existing_finished_pdf):
    write_draft_folder(drafts_folder, build_finished_draft(existing_finished_pdf))

    draft_store.recover()

    assert draft_store.snapshot() == INITIAL_SNAPSHOT


def test_draft_whose_pdf_exists_keeps_the_pdf_it_points_to(draft_store, drafts_folder, existing_finished_pdf):
    write_draft_folder(drafts_folder, build_finished_draft(existing_finished_pdf))

    draft_store.recover()

    assert existing_finished_pdf.read_bytes() == b"pdf"


def test_intact_draft_is_resumed_as_it_was(draft_store, drafts_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)

    draft_store.recover()

    assert draft_store.snapshot() == replace(INITIAL_SNAPSHOT, draft=RECORDED_DRAFT, recovery_report=resumed_report(3))


def test_intact_draft_does_not_rewrite_the_manifest(draft_store, drafts_folder, file_writer):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)

    draft_store.recover()

    assert file_writer.written_file_names == []


def test_page_files_outside_the_manifest_are_deleted(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    write_files(draft_folder, [ORPHAN_PAGE_FILE_NAME, ORPHAN_THUMBNAIL_FILE_NAME])

    draft_store.recover()

    assert list_file_names(draft_folder) == RECORDED_DRAFT_FILE_NAMES


def test_temporary_file_next_to_the_draft_is_deleted(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    write_files(draft_folder, [TEMPORARY_FILE_NAME])

    draft_store.recover()

    assert list_file_names(draft_folder) == RECORDED_DRAFT_FILE_NAMES


def test_unknown_file_next_to_the_draft_is_kept(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    write_files(draft_folder, [UNKNOWN_FILE_NAME])

    draft_store.recover()

    assert list_file_names(draft_folder) == sorted([*RECORDED_DRAFT_FILE_NAMES, UNKNOWN_FILE_NAME])


def test_unknown_file_next_to_the_draft_is_reported_with_a_warning(draft_store, recorded_draft_folder, caplog):
    write_files(recorded_draft_folder, [UNKNOWN_FILE_NAME])

    with caplog.at_level(logging.WARNING, logger=STORE_LOGGER_NAME):
        draft_store.recover()

    assert [(record.levelno, UNKNOWN_FILE_NAME in record.getMessage()) for record in caplog.records] == [
        (logging.WARNING, True)
    ]


def test_page_without_its_file_is_dropped_from_the_draft(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    draft_store.recover()

    assert draft_store.snapshot().draft == DRAFT_WITHOUT_SECOND_PAGE


def test_page_without_its_file_is_dropped_from_the_saved_manifest(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    draft_store.recover()

    reopened_repository = FileSystemDocumentDraftRepository(drafts_folder, ScriptedFileWriter({}), FixedClock(NOW))
    assert reopened_repository.load_manifest() == DRAFT_WITHOUT_SECOND_PAGE


def test_page_without_its_file_is_reported_with_its_position(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    draft_store.recover()

    assert draft_store.snapshot().recovery_report == resumed_report(2, (2,))


def test_page_with_an_unexpected_size_is_moved_to_a_set_aside_folder(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).write_bytes(WRONG_SIZE_CONTENT)

    draft_store.recover()

    assert list_file_names(find_set_aside_folder(drafts_folder)) == [SECOND_PAGE_FILE_NAME]


def test_page_with_an_unexpected_size_is_reported_with_its_position_and_folder(
    draft_store, drafts_folder, draft_folder
):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).write_bytes(WRONG_SIZE_CONTENT)

    draft_store.recover()

    assert draft_store.snapshot().recovery_report == resumed_report(2, (2,), find_set_aside_folder(drafts_folder))


def test_page_without_its_thumbnail_is_kept(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_THUMBNAIL_FILE_NAME).unlink()

    draft_store.recover()

    assert draft_store.snapshot().draft == RECORDED_DRAFT


def test_page_without_its_thumbnail_has_no_thumbnail_to_read(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_THUMBNAIL_FILE_NAME).unlink()

    draft_store.recover()

    assert draft_store.read_thumbnail(SECOND_PAGE_IDENTIFIER) is None


def test_draft_without_any_page_file_is_deleted(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    for page_identifier in RECORDED_DRAFT.page_identifiers:
        (draft_folder / f"page-{page_identifier}.jpg").unlink()

    draft_store.recover()

    assert not draft_folder.exists()


def test_draft_without_any_page_file_is_reported_as_pages_lost(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    for page_identifier in RECORDED_DRAFT.page_identifiers:
        (draft_folder / f"page-{page_identifier}.jpg").unlink()

    draft_store.recover()

    assert draft_store.snapshot() == replace(
        INITIAL_SNAPSHOT,
        recovery_report=DraftRecoveryReport(
            outcome=RecoveryOutcome.PAGES_LOST,
            kept_page_count=0,
            dropped_page_positions=(1, 2, 3),
            set_aside_folder=None,
        ),
    )


def test_pages_lost_report_names_the_folder_of_the_pages_set_aside(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    for page_identifier in RECORDED_DRAFT.page_identifiers:
        (draft_folder / f"page-{page_identifier}.jpg").write_bytes(WRONG_SIZE_CONTENT)

    draft_store.recover()

    assert draft_store.snapshot().recovery_report.set_aside_folder == find_set_aside_folder(drafts_folder)


def test_manifest_without_pages_is_deleted(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, replace(RECORDED_DRAFT, pages=()))

    draft_store.recover()

    assert not draft_folder.exists()


def test_manifest_without_pages_recovers_no_draft_and_no_report(draft_store, drafts_folder):
    write_draft_folder(drafts_folder, replace(RECORDED_DRAFT, pages=()))

    draft_store.recover()

    assert draft_store.snapshot() == INITIAL_SNAPSHOT


def test_draft_whose_pdf_is_missing_is_resumed_with_its_mark(draft_store, drafts_folder, missing_finished_pdf):
    finished_draft = build_finished_draft(missing_finished_pdf)
    write_draft_folder(drafts_folder, finished_draft)

    draft_store.recover()

    assert draft_store.snapshot() == replace(INITIAL_SNAPSHOT, draft=finished_draft, recovery_report=resumed_report(3))


def test_draft_whose_pdf_is_missing_does_not_rewrite_the_manifest(drafts_folder, file_writer, missing_finished_pdf):
    draft_store = build_store(drafts_folder, file_writer)
    write_draft_folder(drafts_folder, build_finished_draft(missing_finished_pdf))

    draft_store.recover()

    assert file_writer.written_file_names == []


@requires_permission_bits
def test_draft_whose_pdf_folder_is_closed_is_resumed_with_its_mark(draft_store, drafts_folder, tmp_path):
    output_folder = tmp_path / "saida"
    output_folder.mkdir()
    (output_folder / FINISHED_PDF_NAME).write_bytes(b"pdf")
    finished_draft = build_finished_draft(output_folder / FINISHED_PDF_NAME)
    write_draft_folder(drafts_folder, finished_draft)

    with permission_mode(output_folder, CLOSED_FOLDER_MODE):
        draft_store.recover()

    assert draft_store.snapshot().draft == finished_draft


def test_interrupted_finalization_is_resumed_with_its_intention_mark(draft_store, drafts_folder):
    interrupted_draft = RECORDED_DRAFT.with_finalization_started(NOW)
    write_draft_folder(drafts_folder, interrupted_draft)

    draft_store.recover()

    assert draft_store.snapshot() == replace(
        INITIAL_SNAPSHOT, draft=interrupted_draft, recovery_report=resumed_report(3)
    )


def test_manifest_that_cannot_be_rewritten_keeps_the_draft_without_the_dropped_page(drafts_folder, draft_folder):
    draft_store = build_store(drafts_folder, ScriptedFileWriter({MANIFEST_FILE_NAME: FULL_DISK_ERROR}))
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    draft_store.recover()

    assert draft_store.snapshot().draft == DRAFT_WITHOUT_SECOND_PAGE


def test_manifest_that_cannot_be_rewritten_stays_as_it_was_on_disk(drafts_folder, draft_folder):
    draft_store = build_store(drafts_folder, ScriptedFileWriter({MANIFEST_FILE_NAME: FULL_DISK_ERROR}))
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    draft_store.recover()

    assert (draft_folder / MANIFEST_FILE_NAME).read_bytes() == encode_manifest(RECORDED_DRAFT)


def test_manifest_that_cannot_be_rewritten_still_reports_the_draft_as_resumed(drafts_folder, draft_folder):
    draft_store = build_store(drafts_folder, ScriptedFileWriter({MANIFEST_FILE_NAME: FULL_DISK_ERROR}))
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()

    draft_store.recover()

    assert draft_store.snapshot().recovery_report == resumed_report(2, (2,))


def test_accepted_change_after_the_recovery_clears_the_recovery_report(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).unlink()
    draft_store.recover()

    draft_store.rename("Contrato assinado")

    assert draft_store.snapshot().recovery_report is None


@requires_permission_bits
def test_draft_folder_that_cannot_be_listed_fails_the_recovery(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)

    with permission_mode(draft_folder, UNLISTABLE_FOLDER_MODE):
        draft_store.recover()

    assert draft_store.snapshot() == FAILED_SNAPSHOT


@requires_permission_bits
def test_manifest_that_cannot_be_read_fails_the_recovery(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)

    with permission_mode(draft_folder / MANIFEST_FILE_NAME, UNREADABLE_FILE_MODE):
        draft_store.recover()

    assert draft_store.snapshot() == FAILED_SNAPSHOT


@requires_permission_bits
def test_failed_recovery_leaves_the_draft_folder_as_it_was(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    write_files(draft_folder, [ORPHAN_PAGE_FILE_NAME, TEMPORARY_FILE_NAME])
    file_names_before = list_file_names(draft_folder)

    with permission_mode(draft_folder / MANIFEST_FILE_NAME, UNREADABLE_FILE_MODE):
        draft_store.recover()

    assert list_file_names(draft_folder) == file_names_before


@requires_permission_bits
def test_failed_recovery_is_logged_with_its_traceback(draft_store, recorded_draft_folder, caplog):
    with caplog.at_level(logging.WARNING, logger=STORE_LOGGER_NAME):
        with permission_mode(recorded_draft_folder, UNLISTABLE_FOLDER_MODE):
            draft_store.recover()

    assert [(record.levelno, record.exc_info is not None) for record in caplog.records] == [(logging.ERROR, True)]


@requires_permission_bits
def test_failed_recovery_blocks_new_pages_with_draft_storage_unavailable(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    with permission_mode(draft_folder / MANIFEST_FILE_NAME, UNREADABLE_FILE_MODE):
        draft_store.recover()

    with pytest.raises(DraftStorageUnavailableError):
        draft_store.ensure_capacity_for_page(SETTINGS)


def test_successful_recovery_lets_new_pages_in(draft_store, drafts_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    draft_store.recover()

    assert draft_store.ensure_capacity_for_page(SETTINGS) is None


@requires_permission_bits
def test_failure_to_set_an_unreadable_draft_aside_fails_the_recovery(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / MANIFEST_FILE_NAME).write_bytes(b"")

    with permission_mode(drafts_folder, READ_ONLY_FOLDER_MODE):
        draft_store.recover()

    assert draft_store.snapshot() == FAILED_SNAPSHOT


@requires_permission_bits
def test_failure_to_set_an_unreadable_draft_aside_leaves_its_files_in_place(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / MANIFEST_FILE_NAME).write_bytes(b"")

    with permission_mode(drafts_folder, READ_ONLY_FOLDER_MODE):
        draft_store.recover()

    assert list_file_names(draft_folder) == RECORDED_DRAFT_FILE_NAMES


@requires_permission_bits
def test_failure_to_set_a_wrong_size_page_aside_fails_the_recovery(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).write_bytes(WRONG_SIZE_CONTENT)

    with permission_mode(drafts_folder, READ_ONLY_FOLDER_MODE):
        draft_store.recover()

    assert draft_store.snapshot() == FAILED_SNAPSHOT


@requires_permission_bits
def test_failure_to_set_a_wrong_size_page_aside_deletes_nothing(draft_store, drafts_folder, draft_folder):
    write_draft_folder(drafts_folder, RECORDED_DRAFT)
    (draft_folder / SECOND_PAGE_FILE_NAME).write_bytes(WRONG_SIZE_CONTENT)
    write_files(draft_folder, [TEMPORARY_FILE_NAME])

    with permission_mode(drafts_folder, READ_ONLY_FOLDER_MODE):
        draft_store.recover()

    assert list_file_names(draft_folder) == sorted([*RECORDED_DRAFT_FILE_NAMES, TEMPORARY_FILE_NAME])
