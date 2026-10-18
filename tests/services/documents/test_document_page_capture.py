import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.documents.document_draft import DocumentPage
from digitalizadora.domain.errors import ImageAdjustmentFailedError, InsufficientDraftStorageError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import UNFRAMED
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.documents.file_system_document_draft_repository import (
    FileSystemDocumentDraftRepository,
)
from digitalizadora.services.documents.document_draft_store import DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.documents.document_page_capture import DocumentPageCapture
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.page_crop_detection_service import DetectedCrops, PageCropDetectionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.scan_encoder import EncodedMaster, ScanEncoder
from digitalizadora.services.storage_guard_service import (
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
)
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.document_drafts import page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.photo_scenes import PlacedPhoto, build_photo_scene_jpeg
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers
from tests.fakes.synthetic_scans import build_scan_jpeg, read_jpeg_size

DRAFT_SESSION = "5c0f9a2e7b1d4c38"
STARTED_AT = datetime(2026, 10, 17, 10, 0, 41, tzinfo=timezone(timedelta(hours=-3)))
PAGE_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT_ECONOMY.settings, output_format=OutputFormat.JPEG)
PAGE_JOB = ScanJob(request=PAGE_REQUEST, started_at=STARTED_AT)
SCANNED_IMAGE = ScannedImage(content=build_sample_jpeg(), media_type="image/jpeg")
FIRST_PAGE_IDENTIFIER = page_identifier_at(1)
FREE_SPACE_FOR_A_DOCUMENT_PAGE = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(
    ScanPreset.DOCUMENT.settings
)


@pytest.fixture
def drafts_folder(tmp_path: Path) -> Path:
    return tmp_path / "drafts"


@pytest.fixture
def free_space_reader() -> RecordingFreeSpaceReader:
    return RecordingFreeSpaceReader(FREE_SPACE_FOR_A_DOCUMENT_PAGE)


@pytest.fixture
def scan_encoder() -> ScanEncoder:
    return ScanEncoder(JpegResolutionService(), PdfAssemblyService(), ThumbnailService())


@pytest.fixture
def expected_encoded_scan(scan_encoder: ScanEncoder) -> EncodedMaster:
    return scan_encoder.encode_master(SCANNED_IMAGE, PAGE_JOB)


@pytest.fixture
def draft_store(drafts_folder: Path, free_space_reader: RecordingFreeSpaceReader) -> DocumentDraftStore:
    return DocumentDraftStore(
        FileSystemDocumentDraftRepository(drafts_folder, AtomicFileWriter(), FixedClock(STARTED_AT)),
        StorageGuardService(free_space_reader),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )


@pytest.fixture
def page_capture(scan_encoder: ScanEncoder, draft_store: DocumentDraftStore) -> DocumentPageCapture:
    return DocumentPageCapture(scan_encoder, draft_store, PageCropDetectionService())


def test_ensure_capacity_checks_the_drafts_disk_with_the_request_settings(page_capture):
    photo_request = ScanRequest(settings=ScanPreset.PHOTO.settings, output_format=OutputFormat.JPEG)

    with pytest.raises(InsufficientDraftStorageError):
        page_capture.ensure_capacity(photo_request)


def test_ensure_capacity_does_not_count_the_adjustment_of_the_request(page_capture):
    adjusted_request = ScanRequest(
        settings=ScanPreset.DOCUMENT.settings,
        output_format=OutputFormat.JPEG,
        adjustment=ImageAdjustment(auto_crop=True),
    )

    assert page_capture.ensure_capacity(adjusted_request) is None


def test_ensure_capacity_accepts_a_page_that_fits_on_the_drafts_disk(page_capture, free_space_reader, drafts_folder):
    page_capture.ensure_capacity(PAGE_REQUEST)

    assert free_space_reader.requested_folders == [drafts_folder]


def test_store_returns_the_page_with_the_job_time_and_settings(page_capture, expected_encoded_scan):
    page = page_capture.store(SCANNED_IMAGE, PAGE_JOB)

    assert page == DocumentPage(
        page_identifier=FIRST_PAGE_IDENTIFIER,
        scanned_at=STARTED_AT,
        dots_per_inch=200,
        color_mode=ColorMode.GRAYSCALE,
        size_in_bytes=len(expected_encoded_scan.jpeg_content),
    )


def test_store_appends_the_page_to_the_draft(page_capture, draft_store):
    page = page_capture.store(SCANNED_IMAGE, PAGE_JOB)

    assert draft_store.snapshot().draft.pages == (page,)


def test_store_keeps_the_encoded_jpeg_as_the_page_file(page_capture, drafts_folder, expected_encoded_scan):
    page_capture.store(SCANNED_IMAGE, PAGE_JOB)

    page_file = drafts_folder / "current" / f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
    assert page_file.read_bytes() == expected_encoded_scan.jpeg_content


def test_store_keeps_the_encoded_thumbnail(page_capture, draft_store, expected_encoded_scan):
    page_capture.store(SCANNED_IMAGE, PAGE_JOB)

    assert draft_store.read_thumbnail(FIRST_PAGE_IDENTIFIER) == expected_encoded_scan.thumbnail_jpeg


def test_store_of_an_image_that_is_not_jpeg_raises_scan_failed(page_capture):
    with pytest.raises(ScanFailedError):
        page_capture.store(ScannedImage(content=b"%PDF-1.4", media_type="application/pdf"), PAGE_JOB)


def test_store_of_an_image_that_is_not_jpeg_adds_no_page(page_capture, draft_store):
    with pytest.raises(ScanFailedError):
        page_capture.store(ScannedImage(content=b"%PDF-1.4", media_type="application/pdf"), PAGE_JOB)

    assert draft_store.snapshot().draft is None


LID_SIZE = (200, 280)
DARK_LID = (30, 30, 30)
PAPER = (240, 240, 240)
PAPER_BOX = (40, 60, 159, 219)
SHEET_ON_DARK_LID = ScannedImage(build_scan_jpeg(LID_SIZE, [(PAPER_BOX, PAPER)], background=DARK_LID), "image/jpeg")
CROPPING_JOB = ScanJob(
    request=ScanRequest(
        ScanPreset.DOCUMENT_ECONOMY.settings, OutputFormat.JPEG, ImageAdjustment(auto_crop=True)
    ),
    started_at=STARTED_AT,
)


def test_a_page_without_the_automatic_crop_has_no_frame(page_capture):
    page = page_capture.store(SHEET_ON_DARK_LID, PAGE_JOB)

    assert page.framing == UNFRAMED


def test_a_page_with_the_automatic_crop_gets_the_frame_of_the_sheet(page_capture):
    page = page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    assert len(page.framing.crops) == 1
    edges = page.framing.crops[0].bounding_edges
    assert (edges.left, edges.right) == pytest.approx((0.18, 0.82), abs=0.05)


TWO_PHOTOS = ScannedImage(
    build_photo_scene_jpeg(
        (582, 800), [PlacedPhoto((150.0, 260.0), (240, 300), 10.0), PlacedPhoto((430.0, 540.0), (240, 300), -6.0, 2)]
    ),
    "image/jpeg",
)


def test_a_page_with_two_photos_and_the_automatic_crop_gets_two_frames(page_capture):
    page = page_capture.store(TWO_PHOTOS, CROPPING_JOB)

    assert len(page.framing.crops) == 2


def test_a_page_with_the_automatic_crop_has_no_rotation(page_capture):
    page = page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    assert page.framing.rotation is PageRotation.NONE


def test_the_stored_page_keeps_the_scanner_image_when_a_frame_is_found(page_capture, drafts_folder):
    page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    page_file = drafts_folder / "current" / f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
    assert read_jpeg_size(page_file.read_bytes()) == LID_SIZE


def test_the_stored_page_is_the_unadjusted_master_whatever_the_request_asks(
    page_capture, scan_encoder, drafts_folder
):
    page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    unadjusted_master = scan_encoder.encode_master(SHEET_ON_DARK_LID, PAGE_JOB).jpeg_content
    page_file = drafts_folder / "current" / f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
    assert page_file.read_bytes() == unadjusted_master


def test_the_size_of_the_manifest_is_the_size_of_the_stored_page(page_capture, drafts_folder):
    page = page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    page_file = drafts_folder / "current" / f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
    assert page.size_in_bytes == page_file.stat().st_size


def test_a_white_page_with_the_automatic_crop_has_no_frame(page_capture):
    page = page_capture.store(SCANNED_IMAGE, CROPPING_JOB)

    assert page.framing == UNFRAMED


class FailingCropDetectionService(PageCropDetectionService):
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    def detect_crops(self, jpeg_content: bytes) -> DetectedCrops:
        raise self._failure


def test_a_detection_that_fails_still_adds_the_page(scan_encoder, draft_store):
    page_capture = DocumentPageCapture(scan_encoder, draft_store, FailingCropDetectionService(ScanFailedError("x")))

    page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    assert draft_store.snapshot().draft.page_count == 1


def test_a_detection_that_fails_leaves_the_page_without_a_frame(scan_encoder, draft_store):
    page_capture = DocumentPageCapture(
        scan_encoder, draft_store, FailingCropDetectionService(ImageAdjustmentFailedError("memory"))
    )

    page = page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    assert page.framing == UNFRAMED


def test_a_detection_that_fails_is_reported_in_the_log(scan_encoder, draft_store, caplog):
    page_capture = DocumentPageCapture(scan_encoder, draft_store, FailingCropDetectionService(ScanFailedError("x")))

    with caplog.at_level(logging.WARNING):
        page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    assert "automatic crop of the page failed" in caplog.text


class CountingCropDetectionService(PageCropDetectionService):
    def __init__(self) -> None:
        self.detection_count = 0

    def detect_crops(self, jpeg_content: bytes) -> DetectedCrops:
        self.detection_count += 1
        return DetectedCrops((), 0)


def test_the_detection_is_not_run_without_the_automatic_crop(scan_encoder, draft_store):
    counting_service = CountingCropDetectionService()
    page_capture = DocumentPageCapture(scan_encoder, draft_store, counting_service)

    page_capture.store(SHEET_ON_DARK_LID, PAGE_JOB)

    assert counting_service.detection_count == 0


def test_the_detection_runs_once_on_the_stored_master_with_the_automatic_crop(scan_encoder, draft_store):
    counting_service = CountingCropDetectionService()
    page_capture = DocumentPageCapture(scan_encoder, draft_store, counting_service)

    page_capture.store(SHEET_ON_DARK_LID, CROPPING_JOB)

    assert counting_service.detection_count == 1
