from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.document_draft import DocumentPage
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import InsufficientDraftStorageError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_document_draft_repository import FileSystemDocumentDraftRepository
from digitalizadora.services.document_draft_store import DocumentDraftStore, DraftIdentitySource
from digitalizadora.services.document_page_capture import DocumentPageCapture
from digitalizadora.services.image_adjustment_service import ImageAdjustmentService
from digitalizadora.services.jpeg_resolution_service import JpegResolutionService
from digitalizadora.services.master_jpeg_service import MasterJpegService
from digitalizadora.services.page_crop_detection_service import PageCropDetectionService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService
from digitalizadora.services.scan_encoder import ScanEncoder
from digitalizadora.services.storage_guard_service import (
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
)
from digitalizadora.services.thumbnail_service import ThumbnailService
from tests.fakes.document_drafts import page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.sequential_page_identifiers import SequentialPageIdentifiers

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
    master_jpeg_service = MasterJpegService(ImageAdjustmentService(PageCropDetectionService()), JpegResolutionService())
    return ScanEncoder(master_jpeg_service, PdfAssemblyService(), ThumbnailService())


@pytest.fixture
def expected_encoded_scan(scan_encoder: ScanEncoder) -> EncodedScan:
    return scan_encoder.encode(SCANNED_IMAGE, PAGE_JOB)


@pytest.fixture
def draft_store(drafts_folder: Path, free_space_reader: RecordingFreeSpaceReader) -> DocumentDraftStore:
    return DocumentDraftStore(
        FileSystemDocumentDraftRepository(drafts_folder, AtomicFileWriter(), FixedClock(STARTED_AT)),
        StorageGuardService(free_space_reader),
        DraftIdentitySource(DRAFT_SESSION, SequentialPageIdentifiers()),
    )


@pytest.fixture
def page_capture(scan_encoder: ScanEncoder, draft_store: DocumentDraftStore) -> DocumentPageCapture:
    return DocumentPageCapture(scan_encoder, draft_store)


def test_ensure_capacity_checks_the_drafts_disk_with_the_request_settings(page_capture):
    photo_request = ScanRequest(settings=ScanPreset.PHOTO.settings, output_format=OutputFormat.JPEG)

    with pytest.raises(InsufficientDraftStorageError):
        page_capture.ensure_capacity(photo_request)


def test_ensure_capacity_counts_the_adjustment_of_the_request(page_capture):
    adjusted_request = ScanRequest(
        settings=ScanPreset.DOCUMENT.settings,
        output_format=OutputFormat.JPEG,
        adjustment=ImageAdjustment(auto_crop=True),
    )

    with pytest.raises(InsufficientDraftStorageError):
        page_capture.ensure_capacity(adjusted_request)


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
        size_in_bytes=len(expected_encoded_scan.content),
    )


def test_store_appends_the_page_to_the_draft(page_capture, draft_store):
    page = page_capture.store(SCANNED_IMAGE, PAGE_JOB)

    assert draft_store.snapshot().draft.pages == (page,)


def test_store_keeps_the_encoded_jpeg_as_the_page_file(page_capture, drafts_folder, expected_encoded_scan):
    page_capture.store(SCANNED_IMAGE, PAGE_JOB)

    page_file = drafts_folder / "current" / f"page-{FIRST_PAGE_IDENTIFIER}.jpg"
    assert page_file.read_bytes() == expected_encoded_scan.content


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
