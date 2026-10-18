from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError, ScanFailedError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_output_service import ScanOutputService
from digitalizadora.services.storage_guard_service import (
    MINIMUM_FREE_SPACE_BYTES,
    SAFETY_MARGIN_PAGES,
    StorageGuardService,
    estimated_page_bytes,
)
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader

OUTPUT_FOLDER = Path("/Volumes/Archive/Scans")
SAVED_PATH = OUTPUT_FOLDER / "2026-10-13_00001.pdf"
STARTED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
SETTINGS = ScanSettings(300, ColorMode.COLOR)
REQUEST = ScanRequest(SETTINGS, OutputFormat.PDF)
JOB = ScanJob(REQUEST, STARTED_AT)
SCANNED_IMAGE = ScannedImage(b"scanned jpeg", "image/jpeg")
ENCODED_SCAN = EncodedScan(
    content=b"final pdf content",
    output_format=OutputFormat.PDF,
    created_at=STARTED_AT,
    thumbnail_jpeg=b"thumbnail jpeg",
)
ENOUGH_FREE_SPACE = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(SETTINGS)


class RecordingScanOutputRepository:
    """Implements ScanOutputRepository; a test assigns preparation_failure or save_failure to make it fail."""

    def __init__(self) -> None:
        self.preparation_failure: Exception | None = None
        self.save_failure: Exception | None = None
        self.preparation_count = 0
        self.saved_scans: list[EncodedScan] = []

    def output_folder(self) -> Path:
        return OUTPUT_FOLDER

    def ensure_output_folder_ready(self) -> None:
        self.preparation_count += 1
        if self.preparation_failure is not None:
            raise self.preparation_failure

    def save(self, encoded_scan: EncodedScan) -> Path:
        if self.save_failure is not None:
            raise self.save_failure
        self.saved_scans.append(encoded_scan)
        return SAVED_PATH


class StubScanEncoder:
    def __init__(self) -> None:
        self.encoded_requests: list[tuple[ScannedImage, ScanJob]] = []

    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        self.encoded_requests.append((scanned_image, job))
        return ENCODED_SCAN


class FailingScanEncoder:
    def encode(self, scanned_image: ScannedImage, job: ScanJob) -> EncodedScan:
        raise ScanFailedError("The scanner returned an unexpected image")


def build_service(
    scan_encoder, scan_output_repository: RecordingScanOutputRepository, free_space_reader: RecordingFreeSpaceReader
) -> ScanOutputService:
    return ScanOutputService(scan_encoder, scan_output_repository, StorageGuardService(free_space_reader))


def test_capacity_check_prepares_the_output_folder():
    repository = RecordingScanOutputRepository()
    service = build_service(StubScanEncoder(), repository, RecordingFreeSpaceReader(ENOUGH_FREE_SPACE))

    service.ensure_capacity(REQUEST)

    assert repository.preparation_count == 1


def test_capacity_check_asks_about_the_folder_of_the_repository():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE)
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader)

    service.ensure_capacity(REQUEST)

    assert reader.requested_folders == [OUTPUT_FOLDER]


def test_capacity_check_passes_with_exactly_the_required_space():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE)

    build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader).ensure_capacity(REQUEST)


def test_capacity_check_refuses_one_byte_less_than_the_required_space():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE - 1)
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader)

    with pytest.raises(InsufficientStorageError):
        service.ensure_capacity(REQUEST)


def test_unavailable_folder_is_reported_before_the_free_space_is_read():
    repository = RecordingScanOutputRepository()
    repository.preparation_failure = OutputFolderUnavailableError("The external disk was disconnected")
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE)
    service = build_service(StubScanEncoder(), repository, reader)

    with pytest.raises(OutputFolderUnavailableError):
        service.ensure_capacity(REQUEST)

    assert reader.requested_folders == []


def test_folder_that_vanishes_before_the_space_check_is_reported_as_unavailable():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE)
    reader.failure = OutputFolderUnavailableError("The external disk was disconnected")
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader)

    with pytest.raises(OutputFolderUnavailableError):
        service.ensure_capacity(REQUEST)


def test_store_gives_the_scanned_image_and_the_job_to_the_encoder():
    scan_encoder = StubScanEncoder()
    service = build_service(scan_encoder, RecordingScanOutputRepository(), RecordingFreeSpaceReader(0))

    service.store(SCANNED_IMAGE, JOB)

    assert scan_encoder.encoded_requests == [(SCANNED_IMAGE, JOB)]


def test_store_saves_the_encoded_scan_in_the_repository():
    repository = RecordingScanOutputRepository()
    service = build_service(StubScanEncoder(), repository, RecordingFreeSpaceReader(0))

    service.store(SCANNED_IMAGE, JOB)

    assert repository.saved_scans == [ENCODED_SCAN]


def test_store_describes_the_saved_file_in_the_result():
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), RecordingFreeSpaceReader(0))

    stored_scan = service.store(SCANNED_IMAGE, JOB)

    assert stored_scan.result == ScanResult(
        output_path=SAVED_PATH,
        output_format=OutputFormat.PDF,
        scanned_at=STARTED_AT,
        size_in_bytes=len(b"final pdf content"),
    )


def test_store_returns_the_thumbnail_of_the_encoded_scan():
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), RecordingFreeSpaceReader(0))

    stored_scan = service.store(SCANNED_IMAGE, JOB)

    assert isinstance(stored_scan, StoredScan)
    assert stored_scan.thumbnail_jpeg == b"thumbnail jpeg"


def test_encoder_error_propagates_and_nothing_is_saved():
    repository = RecordingScanOutputRepository()
    service = build_service(FailingScanEncoder(), repository, RecordingFreeSpaceReader(0))

    with pytest.raises(ScanFailedError):
        service.store(SCANNED_IMAGE, JOB)

    assert repository.saved_scans == []


def test_repository_error_propagates():
    repository = RecordingScanOutputRepository()
    repository.save_failure = OutputFolderUnavailableError("The external disk was disconnected")
    service = build_service(StubScanEncoder(), repository, RecordingFreeSpaceReader(0))

    with pytest.raises(OutputFolderUnavailableError):
        service.store(SCANNED_IMAGE, JOB)


ADJUSTED_REQUEST = ScanRequest(SETTINGS, OutputFormat.PDF, ImageAdjustment(auto_crop=True))
ENOUGH_FREE_SPACE_FOR_AN_ADJUSTED_PAGE = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(
    SETTINGS, ADJUSTED_REQUEST.adjustment
)


def test_capacity_check_counts_the_adjustment_of_the_request():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE_FOR_AN_ADJUSTED_PAGE - 1)
    service = build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader)

    with pytest.raises(InsufficientStorageError):
        service.ensure_capacity(ADJUSTED_REQUEST)


def test_capacity_check_accepts_exactly_the_space_of_an_adjusted_page():
    reader = RecordingFreeSpaceReader(ENOUGH_FREE_SPACE_FOR_AN_ADJUSTED_PAGE)

    build_service(StubScanEncoder(), RecordingScanOutputRepository(), reader).ensure_capacity(ADJUSTED_REQUEST)
