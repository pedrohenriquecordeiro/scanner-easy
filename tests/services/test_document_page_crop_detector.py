from pathlib import Path

import pytest

from digitalizadora.domain.errors import (
    DamagedDocumentPageError,
    ImageAdjustmentFailedError,
    NoOpenDocumentError,
    PageNotFoundError,
)
from digitalizadora.domain.page_crop import RectangleCrop
from digitalizadora.domain.page_framing import UNFRAMED
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.repositories.file_system_document_draft_repository import (
    CURRENT_DRAFT_FOLDER_NAME,
    FileSystemDocumentDraftRepository,
)
from digitalizadora.services.document_draft_store import DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.document_page_crop_detector import CropDetectionResult, DocumentPageCropDetector
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.storage_guard_service import StorageGuardService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, page_identifier_at, seed_draft_folder
from tests.fakes.document_service_parts import InstantFileWriter
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers
from tests.fakes.synthetic_scans import build_scan_jpeg

LID_SIZE = (200, 280)
DARK_LID = (30, 30, 30)
PAPER = (240, 240, 240)
PAPER_BOX = (40, 60, 159, 219)
SHEET_ON_DARK_LID = build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID)
WHITE_PAGE = build_scan_jpeg(LID_SIZE)
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
UNKNOWN_PAGE_IDENTIFIER = "00000000000000ff"
ABUNDANT_FREE_SPACE = 100 * 1024**3
SAMPLE_CROP = RectangleCrop(0.1, 0.1, 0.9, 0.9)


class StubCropDetectionService(PageCropDetectionService):
    def __init__(self, crop: RectangleCrop | None = None, failure: Exception | None = None) -> None:
        self._crop = crop
        self._failure = failure

    def detect_crop_to_suggest(self, jpeg_content: bytes) -> RectangleCrop | None:
        if self._failure is not None:
            raise self._failure
        return self._crop


def build_store(drafts_folder: Path) -> DocumentDraftStore:
    repository = FileSystemDocumentDraftRepository(drafts_folder, InstantFileWriter(), FixedClock(DRAFT_CREATED_AT))
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


def build_detector(drafts_folder: Path, page_content: bytes, service: PageCropDetectionService | None = None):
    seed_draft_folder(drafts_folder, [page_content])
    store = build_store(drafts_folder)
    return store, DocumentPageCropDetector(store, service or PageCropDetectionService())


def test_a_sheet_that_is_found_is_stored_as_the_frame_of_the_page(drafts_folder):
    store, detector = build_detector(drafts_folder, SHEET_ON_DARK_LID)

    result = detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert result.draft.pages[0].framing.crop is not None
    assert store.snapshot().draft == result.draft


def test_a_sheet_that_is_found_says_so(drafts_folder):
    _, detector = build_detector(drafts_folder, SHEET_ON_DARK_LID)

    assert detector.detect_for_page(FIRST_PAGE_IDENTIFIER).crop_detected is True


def test_a_found_frame_raises_the_revision(drafts_folder):
    store, detector = build_detector(drafts_folder, SHEET_ON_DARK_LID)
    revision_before = store.snapshot().revision

    detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert store.snapshot().revision == revision_before + 1


def test_nothing_found_says_so(drafts_folder):
    _, detector = build_detector(drafts_folder, WHITE_PAGE)

    assert detector.detect_for_page(FIRST_PAGE_IDENTIFIER).crop_detected is False


def test_nothing_found_leaves_the_frame_and_the_revision_alone(drafts_folder):
    store, detector = build_detector(drafts_folder, WHITE_PAGE)
    store.set_page_crop(FIRST_PAGE_IDENTIFIER, SAMPLE_CROP)
    snapshot_before = store.snapshot()

    result = detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert (store.snapshot(), result.draft) == (snapshot_before, snapshot_before.draft)


def test_a_frame_found_on_the_master_is_stored_in_the_displayed_orientation(drafts_folder):
    store, detector = build_detector(
        drafts_folder, WHITE_PAGE, StubCropDetectionService(crop=RectangleCrop(0.0, 0.0, 0.5, 1.0))
    )
    store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    result = detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert result.draft.pages[0].framing.crop == RectangleCrop(0.0, 0.0, 1.0, 0.5)


def test_a_found_frame_keeps_the_rotation_of_the_page(drafts_folder):
    store, detector = build_detector(drafts_folder, WHITE_PAGE, StubCropDetectionService(crop=SAMPLE_CROP))
    store.turn_page_clockwise(FIRST_PAGE_IDENTIFIER)

    result = detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert result.draft.pages[0].framing.rotation is PageRotation.CLOCKWISE_90


def test_a_found_frame_replaces_the_frame_of_before(drafts_folder):
    store, detector = build_detector(drafts_folder, WHITE_PAGE, StubCropDetectionService(crop=SAMPLE_CROP))
    store.set_page_crop(FIRST_PAGE_IDENTIFIER, RectangleCrop(0.3, 0.3, 0.6, 0.6))

    result = detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert result.draft.pages[0].framing.crop == SAMPLE_CROP


def test_the_same_frame_found_again_keeps_the_revision(drafts_folder):
    store, detector = build_detector(drafts_folder, WHITE_PAGE, StubCropDetectionService(crop=SAMPLE_CROP))
    store.set_page_crop(FIRST_PAGE_IDENTIFIER, SAMPLE_CROP)
    revision_before = store.snapshot().revision

    result = detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert (store.snapshot().revision, result.crop_detected) == (revision_before, True)


def test_the_detection_leaves_the_stored_page_as_it_was(drafts_folder):
    _, detector = build_detector(drafts_folder, SHEET_ON_DARK_LID)
    page_file = drafts_folder / CURRENT_DRAFT_FOLDER_NAME / f"page-{FIRST_PAGE_IDENTIFIER}.jpg"

    detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert page_file.read_bytes() == SHEET_ON_DARK_LID


def test_a_page_that_is_not_in_the_draft_raises_page_not_found(drafts_folder):
    _, detector = build_detector(drafts_folder, SHEET_ON_DARK_LID)

    with pytest.raises(PageNotFoundError):
        detector.detect_for_page(UNKNOWN_PAGE_IDENTIFIER)


def test_a_missing_draft_raises_no_open_document(tmp_path):
    detector = DocumentPageCropDetector(build_store(tmp_path / "empty"), PageCropDetectionService())

    with pytest.raises(NoOpenDocumentError):
        detector.detect_for_page(FIRST_PAGE_IDENTIFIER)


def test_a_page_file_that_is_missing_raises_damaged_document_page(drafts_folder):
    _, detector = build_detector(drafts_folder, SHEET_ON_DARK_LID)
    (drafts_folder / CURRENT_DRAFT_FOLDER_NAME / f"page-{FIRST_PAGE_IDENTIFIER}.jpg").unlink()

    with pytest.raises(DamagedDocumentPageError):
        detector.detect_for_page(FIRST_PAGE_IDENTIFIER)


def test_a_page_that_cannot_be_decoded_raises_damaged_document_page_with_its_position(drafts_folder):
    _, detector = build_detector(drafts_folder, b"not a jpeg at all")

    with pytest.raises(DamagedDocumentPageError) as raised:
        detector.detect_for_page(FIRST_PAGE_IDENTIFIER)

    assert (raised.value.page_identifier, raised.value.page_position) == (FIRST_PAGE_IDENTIFIER, 1)


def test_running_out_of_memory_raises_image_adjustment_failed(drafts_folder):
    _, detector = build_detector(
        drafts_folder, SHEET_ON_DARK_LID, StubCropDetectionService(failure=ImageAdjustmentFailedError("memory"))
    )

    with pytest.raises(ImageAdjustmentFailedError):
        detector.detect_for_page(FIRST_PAGE_IDENTIFIER)


def test_a_result_is_a_draft_and_a_boolean(drafts_folder):
    store, detector = build_detector(drafts_folder, WHITE_PAGE)

    assert detector.detect_for_page(FIRST_PAGE_IDENTIFIER) == CropDetectionResult(store.snapshot().draft, False)


def test_a_page_without_a_frame_stays_unframed_when_nothing_is_found(drafts_folder):
    _, detector = build_detector(drafts_folder, WHITE_PAGE)

    assert detector.detect_for_page(FIRST_PAGE_IDENTIFIER).draft.pages[0].framing == UNFRAMED
