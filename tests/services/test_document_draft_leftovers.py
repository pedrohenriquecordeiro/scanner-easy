import os
from collections.abc import Iterator, Sequence
from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.document_draft import DocumentDraft
from digitalizadora.domain.errors import DraftStorageUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_document_draft_repository import FileSystemDocumentDraftRepository
from digitalizadora.services.document_draft_store import CapturedPage, DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, build_document_page, page_identifier_at, write_draft_folder
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
NOW = DRAFT_CREATED_AT + timedelta(minutes=15)
MANIFEST_FILE_NAME = "manifest.json"
NEW_PAGE_IDENTIFIER = page_identifier_at(1)
NEW_DRAFT_FILE_NAMES = [MANIFEST_FILE_NAME, f"page-{NEW_PAGE_IDENTIFIER}.jpg", f"thumbnail-{NEW_PAGE_IDENTIFIER}.jpg"]
LEFTOVER_PAGE_IDENTIFIER = "00000000000000aa"
LEFTOVER_PAGE_FILE_NAME = f"page-{LEFTOVER_PAGE_IDENTIFIER}.jpg"
LEFTOVER_THUMBNAIL_FILE_NAME = f"thumbnail-{LEFTOVER_PAGE_IDENTIFIER}.jpg"
LEFTOVER_TEMPORARY_FILE_NAME = f".{LEFTOVER_PAGE_FILE_NAME}.4242-0a1b2c3d.part"
LEFTOVER_DRAFT_FILE_NAMES = [MANIFEST_FILE_NAME, LEFTOVER_PAGE_FILE_NAME, LEFTOVER_THUMBNAIL_FILE_NAME]
UNKNOWN_FILE_NAME = ".DS_Store"
LEFTOVER_DRAFT = DocumentDraft(
    name="Documento cancelado", created_at=DRAFT_CREATED_AT, pages=(build_document_page(LEFTOVER_PAGE_IDENTIFIER),)
)
CAPTURED_PAGE = CapturedPage(
    jpeg_content=b"new page jpeg",
    thumbnail_jpeg=b"new thumbnail jpeg",
    scanned_at=DRAFT_CREATED_AT,
    settings=ScanPreset.DOCUMENT.settings,
)
FREE_SPACE_IN_BYTES = 10 * 1024**3
READ_ONLY_FOLDER_MODE = 0o500
WRITABLE_FOLDER_MODE = 0o700
requires_permission_bits = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permission bits")


def write_leftover_files(draft_folder: Path, file_names: Sequence[str]) -> None:
    draft_folder.mkdir(parents=True)
    for file_name in file_names:
        (draft_folder / file_name).write_bytes(b"leftover")


def build_finished_leftover(finished_pdf_path: Path) -> DocumentDraft:
    finished_document = ScanResult(
        output_path=finished_pdf_path, output_format=OutputFormat.PDF, scanned_at=NOW, size_in_bytes=3
    )
    return LEFTOVER_DRAFT.marked_finished(finished_document)


def list_file_names(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.iterdir())


def list_set_aside_contents(drafts_folder: Path) -> list[list[str]]:
    return [list_file_names(folder) for folder in sorted(drafts_folder.glob("set-aside-*"))]


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def draft_folder(drafts_folder: Path) -> Path:
    return drafts_folder / "current"


@pytest.fixture
def draft_store(drafts_folder: Path) -> DocumentDraftStore:
    return DocumentDraftStore(
        FileSystemDocumentDraftRepository(drafts_folder, AtomicFileWriter(), FixedClock(NOW)),
        StorageGuardService(RecordingFreeSpaceReader(FREE_SPACE_IN_BYTES)),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )


@pytest.fixture
def read_only_drafts_folder(drafts_folder: Path) -> Iterator[Path]:
    write_draft_folder(drafts_folder, LEFTOVER_DRAFT)
    drafts_folder.chmod(READ_ONLY_FOLDER_MODE)
    yield drafts_folder
    drafts_folder.chmod(WRITABLE_FOLDER_MODE)


def test_leftover_files_without_a_manifest_are_deleted(draft_store, draft_folder):
    write_leftover_files(
        draft_folder, [LEFTOVER_PAGE_FILE_NAME, LEFTOVER_THUMBNAIL_FILE_NAME, LEFTOVER_TEMPORARY_FILE_NAME]
    )

    draft_store.append_page(CAPTURED_PAGE)

    assert list_file_names(draft_folder) == NEW_DRAFT_FILE_NAMES


def test_unknown_leftover_file_without_a_manifest_is_kept(draft_store, draft_folder):
    write_leftover_files(draft_folder, [LEFTOVER_PAGE_FILE_NAME, UNKNOWN_FILE_NAME])

    draft_store.append_page(CAPTURED_PAGE)

    assert list_file_names(draft_folder) == sorted([*NEW_DRAFT_FILE_NAMES, UNKNOWN_FILE_NAME])


def test_leftover_draft_whose_pdf_exists_is_deleted(draft_store, drafts_folder, tmp_path):
    (tmp_path / "Documento cancelado.pdf").write_bytes(b"pdf")
    write_draft_folder(drafts_folder, build_finished_leftover(tmp_path / "Documento cancelado.pdf"))

    draft_store.append_page(CAPTURED_PAGE)

    assert list_file_names(drafts_folder / "current") == NEW_DRAFT_FILE_NAMES


def test_leftover_draft_whose_pdf_exists_is_not_set_aside(draft_store, drafts_folder, tmp_path):
    (tmp_path / "Documento cancelado.pdf").write_bytes(b"pdf")
    write_draft_folder(drafts_folder, build_finished_leftover(tmp_path / "Documento cancelado.pdf"))

    draft_store.append_page(CAPTURED_PAGE)

    assert list_set_aside_contents(drafts_folder) == []


def test_valid_leftover_draft_without_a_finished_mark_is_set_aside(draft_store, drafts_folder):
    write_draft_folder(drafts_folder, LEFTOVER_DRAFT)

    draft_store.append_page(CAPTURED_PAGE)

    assert list_set_aside_contents(drafts_folder) == [LEFTOVER_DRAFT_FILE_NAMES]


def test_leftover_draft_whose_pdf_is_missing_is_set_aside(draft_store, drafts_folder, tmp_path):
    write_draft_folder(drafts_folder, build_finished_leftover(tmp_path / "Documento cancelado.pdf"))

    draft_store.append_page(CAPTURED_PAGE)

    assert list_set_aside_contents(drafts_folder) == [LEFTOVER_DRAFT_FILE_NAMES]


def test_unreadable_leftover_manifest_is_set_aside_with_all_its_files(draft_store, drafts_folder, draft_folder):
    write_leftover_files(draft_folder, [LEFTOVER_PAGE_FILE_NAME, UNKNOWN_FILE_NAME])
    (draft_folder / MANIFEST_FILE_NAME).write_bytes(b'{"format_version": 1, "name": "cut in the mid')

    draft_store.append_page(CAPTURED_PAGE)

    assert list_set_aside_contents(drafts_folder) == [[UNKNOWN_FILE_NAME, MANIFEST_FILE_NAME, LEFTOVER_PAGE_FILE_NAME]]


def test_new_draft_holds_only_the_new_page_after_a_leftover_was_set_aside(draft_store, drafts_folder):
    write_draft_folder(drafts_folder, LEFTOVER_DRAFT)

    page = draft_store.append_page(CAPTURED_PAGE)

    assert draft_store.snapshot().draft == DocumentDraft.start(page)


def test_second_page_leaves_files_outside_the_manifest_alone(draft_store, draft_folder):
    draft_store.append_page(CAPTURED_PAGE)
    (draft_folder / LEFTOVER_PAGE_FILE_NAME).write_bytes(b"leftover")

    draft_store.append_page(CAPTURED_PAGE)

    assert (draft_folder / LEFTOVER_PAGE_FILE_NAME).exists()


@requires_permission_bits
def test_failure_to_set_a_leftover_aside_raises_draft_storage_unavailable(draft_store, read_only_drafts_folder):
    with pytest.raises(DraftStorageUnavailableError):
        draft_store.append_page(CAPTURED_PAGE)


@requires_permission_bits
def test_failure_to_set_a_leftover_aside_adds_no_page(draft_store, read_only_drafts_folder):
    with pytest.raises(DraftStorageUnavailableError):
        draft_store.append_page(CAPTURED_PAGE)

    assert draft_store.snapshot().draft is None


@requires_permission_bits
def test_failure_to_set_a_leftover_aside_keeps_the_leftover_where_it_was(
    draft_store, read_only_drafts_folder, draft_folder
):
    with pytest.raises(DraftStorageUnavailableError):
        draft_store.append_page(CAPTURED_PAGE)

    assert list_file_names(draft_folder) == LEFTOVER_DRAFT_FILE_NAMES
