"""A crash while turning a page or changing its crop leaves the manifest of before or the one of after (6.5)."""

from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.documents.document_draft_reconciliation import page_file_name, thumbnail_file_name
from digitalizadora.domain.imaging.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_settings import ScanSettings
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.documents.file_system_document_draft_repository import (
    FileSystemDocumentDraftRepository,
)
from digitalizadora.services.documents.document_draft_store import CapturedPage, DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.page_crops import rectangle
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
NOW = DRAFT_CREATED_AT + timedelta(minutes=15)
ABUNDANT_FREE_SPACE = 100 * 1024**3
SETTINGS = ScanSettings(300, ColorMode.COLOR)
PAGE_IDENTIFIER = page_identifier_at(1)
PAGE_JPEG = b"first page jpeg"
THUMBNAIL_JPEG = b"thumbnail jpeg"
CROP = rectangle((0.125, 0.115, 0.9, 0.925))
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


def build_store(drafts_folder: Path, crashing_methods: set[str]) -> DocumentDraftStore:
    draft_repository = FileSystemDocumentDraftRepository(drafts_folder, AtomicFileWriter(), FixedClock(NOW))
    return DocumentDraftStore(
        CrashingRepository(draft_repository, crashing_methods),
        StorageGuardService(RecordingFreeSpaceReader(ABUNDANT_FREE_SPACE)),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def draft_folder(drafts_folder: Path) -> Path:
    return drafts_folder / "current"


@pytest.fixture
def store_with_one_page(drafts_folder: Path) -> DocumentDraftStore:
    store = build_store(drafts_folder, set())
    store.append_page(CapturedPage(PAGE_JPEG, THUMBNAIL_JPEG, DRAFT_CREATED_AT, SETTINGS))
    return store


def recover_in_a_new_process(drafts_folder: Path) -> DocumentDraftStore:
    restarted_store = build_store(drafts_folder, set())
    restarted_store.recover()
    return restarted_store


def crash_before_the_manifest_swap(drafts_folder: Path) -> None:
    crashing_store = build_store(drafts_folder, {"save_manifest"})
    crashing_store.recover()
    with pytest.raises(OSError):
        crashing_store.turn_page_clockwise(PAGE_IDENTIFIER)


def test_a_crash_before_the_manifest_swap_resumes_the_page_as_it_was(store_with_one_page, drafts_folder):
    crash_before_the_manifest_swap(drafts_folder)

    restarted_store = recover_in_a_new_process(drafts_folder)

    assert restarted_store.snapshot().draft.pages[0].framing == UNFRAMED


def test_a_crash_before_the_manifest_swap_leaves_the_page_files_whole(store_with_one_page, drafts_folder, draft_folder):
    crash_before_the_manifest_swap(drafts_folder)

    recover_in_a_new_process(drafts_folder)

    assert (draft_folder / page_file_name(PAGE_IDENTIFIER)).read_bytes() == PAGE_JPEG


def test_an_interrupted_manifest_write_leaves_a_temporary_file_that_the_restart_deletes(
    store_with_one_page, drafts_folder, draft_folder
):
    leftover = draft_folder / ".manifest.json.4242-0a1b2c3d.part"
    leftover.write_bytes(b'{"half a manifest')

    recover_in_a_new_process(drafts_folder)

    assert not leftover.exists()


def test_the_restart_after_an_interrupted_manifest_write_keeps_the_old_manifest(
    store_with_one_page, drafts_folder, draft_folder
):
    (draft_folder / ".manifest.json.4242-0a1b2c3d.part").write_bytes(b'{"half a manifest')

    restarted_store = recover_in_a_new_process(drafts_folder)

    assert restarted_store.snapshot().draft.page_identifiers == (PAGE_IDENTIFIER,)


def test_a_crash_after_the_manifest_swap_resumes_the_turned_page(store_with_one_page, drafts_folder):
    store_with_one_page.turn_page_clockwise(PAGE_IDENTIFIER)

    restarted_store = recover_in_a_new_process(drafts_folder)

    assert restarted_store.snapshot().draft.pages[0].framing.rotation is PageRotation.CLOCKWISE_90


def test_a_crash_after_a_crop_resumes_the_page_with_the_crop(store_with_one_page, drafts_folder):
    store_with_one_page.set_page_crops(PAGE_IDENTIFIER, [CROP])

    restarted_store = recover_in_a_new_process(drafts_folder)

    assert restarted_store.snapshot().draft.pages[0].framing == PageFraming(crops=(CROP,))


def test_a_crash_after_a_turn_and_a_crop_keeps_the_crop_turned(store_with_one_page, drafts_folder):
    store_with_one_page.set_page_crops(PAGE_IDENTIFIER, [CROP])
    store_with_one_page.turn_page_clockwise(PAGE_IDENTIFIER)

    restarted_store = recover_in_a_new_process(drafts_folder)

    assert restarted_store.snapshot().draft.pages[0].framing.crops == (CROP.turned_clockwise(),)


def test_the_page_size_of_the_manifest_still_matches_the_file_after_the_restart(
    store_with_one_page, drafts_folder, draft_folder
):
    store_with_one_page.turn_page_clockwise(PAGE_IDENTIFIER)

    restarted_store = recover_in_a_new_process(drafts_folder)

    page_file_size = (draft_folder / page_file_name(PAGE_IDENTIFIER)).stat().st_size
    assert restarted_store.snapshot().draft.pages[0].size_in_bytes == page_file_size


def test_no_page_or_thumbnail_is_created_or_lost_by_an_edit_of_the_framing(
    store_with_one_page, drafts_folder, draft_folder
):
    store_with_one_page.turn_page_clockwise(PAGE_IDENTIFIER)
    store_with_one_page.set_page_crops(PAGE_IDENTIFIER, [CROP])

    recover_in_a_new_process(drafts_folder)

    assert sorted(entry.name for entry in draft_folder.iterdir()) == sorted(
        ["manifest.json", page_file_name(PAGE_IDENTIFIER), thumbnail_file_name(PAGE_IDENTIFIER)]
    )
