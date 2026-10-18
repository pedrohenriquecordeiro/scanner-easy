from datetime import timedelta
from pathlib import Path

import pytest

from digitalizadora.domain.errors import DamagedDocumentPageError, NoOpenDocumentError, PageNotFoundError
from digitalizadora.domain.imaging.page_rotation import PageRotation
from digitalizadora.repositories.documents.file_system_document_draft_repository import (
    CURRENT_DRAFT_FOLDER_NAME,
    FileSystemDocumentDraftRepository,
)
from digitalizadora.services.application.storage_guard_service import StorageGuardService
from digitalizadora.services.documents.document_draft_store import DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.documents.document_page_view_service import DocumentPageViewService
from digitalizadora.services.imaging.page_image_view_service import PageImageViewService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, page_identifier_at, seed_draft_folder
from tests.fakes.document_service_parts import InstantFileWriter
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, find_marker_corner, read_jpeg_size

PAGE_SIZE = (100, 200)
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
UNKNOWN_PAGE_IDENTIFIER = "00000000000000ff"
ABUNDANT_FREE_SPACE = 100 * 1024**3


def build_store(drafts_folder: Path) -> DocumentDraftStore:
    repository = FileSystemDocumentDraftRepository(
        drafts_folder, InstantFileWriter(), FixedClock(DRAFT_CREATED_AT + timedelta(minutes=1))
    )
    store = DocumentDraftStore(
        repository,
        StorageGuardService(RecordingFreeSpaceReader(ABUNDANT_FREE_SPACE)),
        DraftIdentitySource("5c0f9a2e7b1d4c38", SequentialPageIdentifiers()),
    )
    store.recover()
    return store


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def view_service(drafts_folder: Path) -> DocumentPageViewService:
    seed_draft_folder(drafts_folder, [build_marked_scan_jpeg(PAGE_SIZE)])
    return DocumentPageViewService(build_store(drafts_folder), PageImageViewService())


def test_the_thumbnail_without_rotation_is_the_stored_one_as_it_is(view_service, drafts_folder):
    thumbnail_file = drafts_folder / CURRENT_DRAFT_FOLDER_NAME / f"thumbnail-{FIRST_PAGE_IDENTIFIER}.jpg"
    stored_thumbnail = thumbnail_file.read_bytes()

    assert view_service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.NONE) == stored_thumbnail


def test_the_thumbnail_with_a_rotation_is_turned(view_service):
    thumbnail = view_service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.CLOCKWISE_90)

    assert (read_jpeg_size(thumbnail), find_marker_corner(thumbnail)) == (PAGE_SIZE[::-1], "top-right")


def test_the_thumbnail_of_a_page_outside_the_draft_is_none(view_service):
    assert view_service.read_thumbnail(UNKNOWN_PAGE_IDENTIFIER, PageRotation.CLOCKWISE_90) is None


def test_the_thumbnail_of_a_missing_draft_is_none(tmp_path):
    view_service = DocumentPageViewService(build_store(tmp_path / "empty"), PageImageViewService())

    assert view_service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.NONE) is None


def test_a_thumbnail_that_cannot_be_decoded_raises_damaged_document_page(view_service, drafts_folder):
    thumbnail_file = drafts_folder / CURRENT_DRAFT_FOLDER_NAME / f"thumbnail-{FIRST_PAGE_IDENTIFIER}.jpg"
    thumbnail_file.write_bytes(b"not a jpeg")

    with pytest.raises(DamagedDocumentPageError) as raised:
        view_service.read_thumbnail(FIRST_PAGE_IDENTIFIER, PageRotation.CLOCKWISE_90)

    assert (raised.value.page_identifier, raised.value.page_position) == (FIRST_PAGE_IDENTIFIER, 1)


def test_the_preview_is_the_page_as_it_is_displayed(view_service):
    preview = view_service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.CLOCKWISE_90)

    assert (read_jpeg_size(preview), find_marker_corner(preview)) == (PAGE_SIZE[::-1], "top-right")


def test_the_preview_is_limited_to_the_enlarged_view_size(drafts_folder):
    seed_draft_folder(drafts_folder, [build_marked_scan_jpeg((1700, 1200))])
    view_service = DocumentPageViewService(build_store(drafts_folder), PageImageViewService())

    preview = view_service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.NONE)

    assert max(read_jpeg_size(preview)) == 1600


def test_the_preview_of_a_page_outside_the_draft_raises_page_not_found(view_service):
    with pytest.raises(PageNotFoundError):
        view_service.read_preview(UNKNOWN_PAGE_IDENTIFIER, PageRotation.NONE)


def test_the_preview_without_a_draft_raises_no_open_document(tmp_path):
    view_service = DocumentPageViewService(build_store(tmp_path / "empty"), PageImageViewService())

    with pytest.raises(NoOpenDocumentError):
        view_service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.NONE)


def test_the_preview_of_a_missing_page_file_raises_damaged_document_page(view_service, drafts_folder):
    (drafts_folder / CURRENT_DRAFT_FOLDER_NAME / f"page-{FIRST_PAGE_IDENTIFIER}.jpg").unlink()

    with pytest.raises(DamagedDocumentPageError):
        view_service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.NONE)


def test_the_preview_of_a_page_file_of_another_size_raises_damaged_document_page(view_service, drafts_folder):
    page_file = drafts_folder / CURRENT_DRAFT_FOLDER_NAME / f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
    page_file.write_bytes(page_file.read_bytes() + b"!")

    with pytest.raises(DamagedDocumentPageError):
        view_service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.NONE)


def test_the_preview_of_a_page_that_cannot_be_decoded_raises_damaged_document_page(drafts_folder):
    seed_draft_folder(drafts_folder, [b"not a jpeg at all"])
    view_service = DocumentPageViewService(build_store(drafts_folder), PageImageViewService())

    with pytest.raises(DamagedDocumentPageError) as raised:
        view_service.read_preview(FIRST_PAGE_IDENTIFIER, PageRotation.NONE)

    assert raised.value.page_position == 1
