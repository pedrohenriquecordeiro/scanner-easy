import io
from datetime import timedelta
from pathlib import Path

import pytest
from PIL import Image

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft_reconciliation import page_file_name, thumbnail_file_name
from digitalizadora.domain.errors import (
    DamagedDocumentPageError,
    ImageAdjustmentFailedError,
    InsufficientDraftStorageError,
    NoOpenDocumentError,
    PageNotFoundError,
)
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_document_draft_repository import FileSystemDocumentDraftRepository
from digitalizadora.services.document_draft_store import CapturedPage, DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.document_page_rotator import DocumentPageRotator
from digitalizadora.services.image_adjustment_service import ImageAdjustmentService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.master_jpeg_service import MasterJpegService
from digitalizadora.services.storage_guard_service import MINIMUM_FREE_SPACE_BYTES, StorageGuardService
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, find_marker_corner, read_jpeg_size

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
NOW = DRAFT_CREATED_AT + timedelta(minutes=15)
ABUNDANT_FREE_SPACE = 100 * 1024**3
PAGE_SIZE = (80, 120)
PAGE_SETTINGS = ScanSettings(200, ColorMode.GRAYSCALE)
SCANNED_AT = DRAFT_CREATED_AT + timedelta(seconds=7)
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
SECOND_PAGE_IDENTIFIER = page_identifier_at(2)
TURNED_PAGE_IDENTIFIER = page_identifier_at(3)
UNKNOWN_PAGE_IDENTIFIER = "00000000000000ff"
NOT_AN_IMAGE = b"not an image, but of the recorded size"


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def draft_folder(drafts_folder: Path) -> Path:
    return drafts_folder / "current"


def build_draft_store(drafts_folder: Path, free_space_in_bytes: int = ABUNDANT_FREE_SPACE) -> DocumentDraftStore:
    return DocumentDraftStore(
        FileSystemDocumentDraftRepository(drafts_folder, AtomicFileWriter(), FixedClock(NOW)),
        StorageGuardService(RecordingFreeSpaceReader(free_space_in_bytes)),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )


def build_rotator(draft_store: DocumentDraftStore) -> DocumentPageRotator:
    master_jpeg_service = MasterJpegService(ImageAdjustmentService(), JpegResolutionService())
    return DocumentPageRotator(draft_store, master_jpeg_service, ThumbnailService())


def add_marked_page(draft_store: DocumentDraftStore, jpeg_content: bytes | None = None) -> None:
    page_jpeg = jpeg_content if jpeg_content is not None else build_marked_scan_jpeg(PAGE_SIZE, dpi=(200, 200))
    draft_store.append_page(CapturedPage(page_jpeg, build_marked_scan_jpeg(PAGE_SIZE), SCANNED_AT, PAGE_SETTINGS))


@pytest.fixture
def draft_store(drafts_folder: Path) -> DocumentDraftStore:
    draft_store = build_draft_store(drafts_folder)
    add_marked_page(draft_store)
    add_marked_page(draft_store)
    return draft_store


def read_page_file(draft_folder: Path, page_identifier: str) -> bytes:
    return (draft_folder / page_file_name(page_identifier)).read_bytes()


def test_the_page_is_turned_a_quarter_clockwise(draft_store, draft_folder):
    build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    turned_page = read_page_file(draft_folder, TURNED_PAGE_IDENTIFIER)
    assert (find_marker_corner(turned_page), read_jpeg_size(turned_page)) == ("top-right", (120, 80))


def test_the_page_gets_a_new_identifier_at_the_same_position(draft_store):
    new_draft = build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    assert new_draft.page_identifiers == (TURNED_PAGE_IDENTIFIER, SECOND_PAGE_IDENTIFIER)


def test_the_turned_page_keeps_the_details_of_the_scan(draft_store):
    new_draft = build_rotator(draft_store).rotate_clockwise(SECOND_PAGE_IDENTIFIER)

    turned_page = new_draft.pages[1]
    assert (turned_page.scanned_at, turned_page.dots_per_inch, turned_page.color_mode) == (
        SCANNED_AT,
        200,
        ColorMode.GRAYSCALE,
    )


def test_the_turned_page_records_the_size_of_its_new_file(draft_store, draft_folder):
    new_draft = build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    assert new_draft.pages[0].size_in_bytes == len(read_page_file(draft_folder, TURNED_PAGE_IDENTIFIER))


def test_the_turned_page_keeps_the_density_of_the_scan(draft_store, draft_folder):
    build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    with Image.open(io.BytesIO(read_page_file(draft_folder, TURNED_PAGE_IDENTIFIER))) as image:
        assert image.info["dpi"] == (200, 200)


def test_the_thumbnail_is_made_from_the_turned_page(draft_store, draft_folder):
    build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    thumbnail = (draft_folder / thumbnail_file_name(TURNED_PAGE_IDENTIFIER)).read_bytes()
    width, height = read_jpeg_size(thumbnail)
    assert width > height


def test_the_old_files_of_the_page_are_deleted(draft_store, draft_folder):
    build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    assert not (draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)).exists()
    assert not (draft_folder / thumbnail_file_name(FIRST_PAGE_IDENTIFIER)).exists()


def test_four_turns_bring_the_page_back_to_its_orientation(draft_store, draft_folder):
    rotator = build_rotator(draft_store)
    page_identifier = FIRST_PAGE_IDENTIFIER
    for _ in range(4):
        page_identifier = rotator.rotate_clockwise(page_identifier).page_identifiers[0]

    page_file = read_page_file(draft_folder, page_identifier)
    assert (find_marker_corner(page_file), read_jpeg_size(page_file)) == ("top-left", PAGE_SIZE)


def test_a_page_that_is_not_in_the_draft_raises_page_not_found(draft_store):
    with pytest.raises(PageNotFoundError):
        build_rotator(draft_store).rotate_clockwise(UNKNOWN_PAGE_IDENTIFIER)


def test_without_a_draft_the_rotation_raises_no_open_document(drafts_folder):
    with pytest.raises(NoOpenDocumentError):
        build_rotator(build_draft_store(drafts_folder)).rotate_clockwise(FIRST_PAGE_IDENTIFIER)


def test_a_page_file_that_does_not_decode_raises_damaged_document_page_with_its_position(drafts_folder):
    draft_store = build_draft_store(drafts_folder)
    add_marked_page(draft_store)
    add_marked_page(draft_store, NOT_AN_IMAGE)

    with pytest.raises(DamagedDocumentPageError) as raised:
        build_rotator(draft_store).rotate_clockwise(SECOND_PAGE_IDENTIFIER)

    assert (raised.value.page_identifier, raised.value.page_position) == (SECOND_PAGE_IDENTIFIER, 2)


def test_a_damaged_page_stays_as_it_was(drafts_folder, draft_folder):
    draft_store = build_draft_store(drafts_folder)
    add_marked_page(draft_store, NOT_AN_IMAGE)
    snapshot_before = draft_store.snapshot()

    with pytest.raises(DamagedDocumentPageError):
        build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    assert draft_store.snapshot() == snapshot_before
    assert not (draft_folder / page_file_name(TURNED_PAGE_IDENTIFIER)).exists()


def test_a_missing_page_file_raises_damaged_document_page(draft_store, draft_folder):
    (draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)).unlink()

    with pytest.raises(DamagedDocumentPageError):
        build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)


def test_not_enough_space_for_the_new_file_refuses_before_reading_anything(drafts_folder, draft_folder):
    draft_store = build_draft_store(drafts_folder, MINIMUM_FREE_SPACE_BYTES)
    add_marked_page(draft_store)

    with pytest.raises(InsufficientDraftStorageError):
        build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    assert not (draft_folder / page_file_name(TURNED_PAGE_IDENTIFIER)).exists()


def test_running_out_of_memory_raises_image_adjustment_failed_and_keeps_the_page(
    draft_store, draft_folder, monkeypatch
):
    def out_of_memory(self: Image.Image, method: Image.Transpose) -> Image.Image:
        raise MemoryError

    monkeypatch.setattr(Image.Image, "transpose", out_of_memory)
    snapshot_before = draft_store.snapshot()

    with pytest.raises(ImageAdjustmentFailedError):
        build_rotator(draft_store).rotate_clockwise(FIRST_PAGE_IDENTIFIER)

    assert draft_store.snapshot() == snapshot_before
    assert (draft_folder / page_file_name(FIRST_PAGE_IDENTIFIER)).exists()
