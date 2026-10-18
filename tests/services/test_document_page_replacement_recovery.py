"""A crash in the middle of turning a page never leaves the manifest pointing at a file of another size (6.4)."""

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft_reconciliation import page_file_name, thumbnail_file_name
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_document_draft_repository import FileSystemDocumentDraftRepository
from digitalizadora.services.document_draft_store import CapturedPage, DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
NOW = DRAFT_CREATED_AT + timedelta(minutes=15)
ABUNDANT_FREE_SPACE = 100 * 1024**3
SETTINGS = ScanSettings(300, ColorMode.COLOR)
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
TURNED_PAGE_IDENTIFIER = page_identifier_at(2)
FIRST_PAGE_JPEG = b"first page jpeg"
TURNED_PAGE_JPEG = b"turned page jpeg, a different size"
THUMBNAIL_JPEG = b"thumbnail jpeg"
CRASH = OSError("the power went out")


class CrashingRepository:
    """Delegates to the real repository; the named methods fail like a process that died at that point."""

    def __init__(self, draft_repository: FileSystemDocumentDraftRepository, crashing_methods: set[str]) -> None:
        self._draft_repository = draft_repository
        self._crashing_methods = crashing_methods

    def __getattr__(self, method_name: str) -> Callable[..., object]:
        if method_name in self._crashing_methods:

            def crash(*arguments: object) -> object:
                raise CRASH

            return crash
        return getattr(self._draft_repository, method_name)


def build_store(
    drafts_folder: Path, crashing_methods: set[str], page_identifiers: SequentialPageIdentifiers | None = None
) -> DocumentDraftStore:
    draft_repository = FileSystemDocumentDraftRepository(drafts_folder, AtomicFileWriter(), FixedClock(NOW))
    return DocumentDraftStore(
        CrashingRepository(draft_repository, crashing_methods),
        StorageGuardService(RecordingFreeSpaceReader(ABUNDANT_FREE_SPACE)),
        DraftIdentitySource(DRAFT_SESSION, page_identifiers or SequentialPageIdentifiers()),
    )


def build_page(jpeg_content: bytes) -> CapturedPage:
    return CapturedPage(jpeg_content, THUMBNAIL_JPEG, DRAFT_CREATED_AT, SETTINGS)


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def draft_folder(drafts_folder: Path) -> Path:
    return drafts_folder / "current"


@pytest.fixture
def store_with_one_page(drafts_folder: Path) -> Callable[[set[str]], DocumentDraftStore]:
    def build_store_with_one_page(crashing_methods: set[str]) -> DocumentDraftStore:
        page_identifiers = SequentialPageIdentifiers()
        build_store(drafts_folder, set(), page_identifiers).append_page(build_page(FIRST_PAGE_JPEG))
        return build_store(drafts_folder, crashing_methods, page_identifiers)

    return build_store_with_one_page


def crash_before_the_manifest_swap(store_with_one_page: Callable[[set[str]], DocumentDraftStore]) -> None:
    crashing_store = store_with_one_page({"save_manifest", "delete_page_files"})
    crashing_store.recover()
    with pytest.raises(OSError):
        crashing_store.replace_page(FIRST_PAGE_IDENTIFIER, build_page(TURNED_PAGE_JPEG))


def crash_after_the_manifest_swap(store_with_one_page: Callable[[set[str]], DocumentDraftStore]) -> None:
    crashing_store = store_with_one_page({"delete_page_files"})
    crashing_store.recover()
    with pytest.raises(OSError):
        crashing_store.replace_page(FIRST_PAGE_IDENTIFIER, build_page(TURNED_PAGE_JPEG))


def test_a_crash_before_the_manifest_swap_leaves_the_new_files_without_an_owner(store_with_one_page, draft_folder):
    crash_before_the_manifest_swap(store_with_one_page)

    assert {page_file_name(TURNED_PAGE_IDENTIFIER), thumbnail_file_name(TURNED_PAGE_IDENTIFIER)} <= {
        entry.name for entry in draft_folder.iterdir()
    }


def test_the_restart_after_a_crash_before_the_swap_resumes_the_old_page(store_with_one_page, drafts_folder):
    crash_before_the_manifest_swap(store_with_one_page)
    restarted_store = build_store(drafts_folder, set())

    restarted_store.recover()

    assert restarted_store.snapshot().draft.page_identifiers == (FIRST_PAGE_IDENTIFIER,)


def test_the_restart_after_a_crash_before_the_swap_deletes_the_new_files(
    store_with_one_page, drafts_folder, draft_folder
):
    crash_before_the_manifest_swap(store_with_one_page)

    build_store(drafts_folder, set()).recover()

    assert not (draft_folder / page_file_name(TURNED_PAGE_IDENTIFIER)).exists()
    assert not (draft_folder / thumbnail_file_name(TURNED_PAGE_IDENTIFIER)).exists()


def test_the_restart_after_a_crash_before_the_swap_keeps_the_old_page_whole(
    store_with_one_page, drafts_folder, draft_folder
):
    crash_before_the_manifest_swap(store_with_one_page)

    build_store(drafts_folder, set()).recover()

    assert (draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)).read_bytes() == FIRST_PAGE_JPEG


def test_the_restart_after_a_crash_after_the_swap_resumes_the_turned_page(store_with_one_page, drafts_folder):
    crash_after_the_manifest_swap(store_with_one_page)
    restarted_store = build_store(drafts_folder, set())

    restarted_store.recover()

    assert restarted_store.snapshot().draft.page_identifiers == (TURNED_PAGE_IDENTIFIER,)


def test_the_restart_after_a_crash_after_the_swap_keeps_the_size_of_the_manifest_equal_to_the_file(
    store_with_one_page, drafts_folder, draft_folder
):
    crash_after_the_manifest_swap(store_with_one_page)
    restarted_store = build_store(drafts_folder, set())

    restarted_store.recover()

    turned_page = restarted_store.snapshot().draft.pages[0]
    assert turned_page.size_in_bytes == (draft_folder / page_file_name(TURNED_PAGE_IDENTIFIER)).stat().st_size


def test_the_restart_after_a_crash_after_the_swap_deletes_the_old_files(
    store_with_one_page, drafts_folder, draft_folder
):
    crash_after_the_manifest_swap(store_with_one_page)

    build_store(drafts_folder, set()).recover()

    assert not (draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)).exists()
    assert not (draft_folder / thumbnail_file_name(FIRST_PAGE_IDENTIFIER)).exists()
