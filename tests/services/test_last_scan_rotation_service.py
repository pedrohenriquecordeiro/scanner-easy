import asyncio
import errno
import io
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pikepdf
import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import (
    InsufficientStorageError,
    LastScanFileMissingError,
    NoLastScanError,
    SavedScanUnreadableError,
    ScanAlreadyRunningError,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.services.last_scan_rotation_service import LastScanRotationService, LastScanRotators
from digitalizadora.services.page_image_view_service import PageImageViewService
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentSpecification
from digitalizadora.services.scan_content_rotator import ScanContentRotator
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.scripted_file_writer import ScriptedFileWriter
from tests.fakes.synthetic_scans import build_marked_scan_jpeg, find_marker_corner, read_jpeg_size

JPEG_QUALITY = 90
PAGE_SIZE = (100, 200)
SCANNED_AT = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone(timedelta(hours=-3)))
JPEG_NAME = "2026-10-18_00001.jpg"
PDF_NAME = "2026-10-18_00001.pdf"
REQUEST = ScanRequest(ScanPreset.DOCUMENT.settings, OutputFormat.JPEG)


class ThreadRecordingRepository(FileSystemScanOutputRepository):
    """The real repository, noting the thread that touches the disk and optionally running a hook after a replace."""

    def __init__(self, *arguments: object) -> None:
        super().__init__(*arguments)
        self.thread_identifiers: list[int] = []
        self.after_replacement = lambda: None

    def read_saved_scan(self, scan_path: Path) -> bytes | None:
        self.thread_identifiers.append(threading.get_ident())
        return super().read_saved_scan(scan_path)

    def replace_saved_scan(self, scan_path: Path, content: bytes) -> None:
        super().replace_saved_scan(scan_path, content)
        self.after_replacement()


def build_repository(output_folder: Path, file_writer: AtomicFileWriter | None = None) -> ThreadRecordingRepository:
    settings = ApplicationSettings(output_folder, OutputFormat.JPEG, ScanPreset.DOCUMENT.settings)
    return ThreadRecordingRepository(
        InMemoryApplicationSettingsRepository(settings), ScanFileNamingPolicy(), file_writer or AtomicFileWriter()
    )


def build_service(
    tracker: ScanProgressTracker, repository: FileSystemScanOutputRepository
) -> LastScanRotationService:
    return LastScanRotationService(tracker, repository, LastScanRotators(ScanContentRotator(), PageImageViewService()))


def build_scan_content(output_format: OutputFormat) -> bytes:
    marked_jpeg = build_marked_scan_jpeg(PAGE_SIZE, dpi=(300, 300))
    if output_format is OutputFormat.JPEG:
        return marked_jpeg
    specification = PdfDocumentSpecification(300, "Digitalização", SCANNED_AT)
    return PdfAssemblyService().build_pdf([marked_jpeg], specification)


def record_last_scan(tracker: ScanProgressTracker, output_path: Path, output_format: OutputFormat) -> ScanResult:
    result = ScanResult(output_path, output_format, SCANNED_AT, output_path.stat().st_size)
    tracker.begin_scan(REQUEST)
    tracker.mark_completed(StoredScan(result, build_marked_scan_jpeg((50, 100))))
    return result


def save_scan(output_folder: Path, output_format: OutputFormat) -> Path:
    scan_path = output_folder / (JPEG_NAME if output_format is OutputFormat.JPEG else PDF_NAME)
    scan_path.write_bytes(build_scan_content(output_format))
    return scan_path


@pytest.fixture
def tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(SCANNED_AT))


@pytest.fixture
def repository(tmp_path: Path) -> ThreadRecordingRepository:
    return build_repository(tmp_path)


@pytest.fixture
def service(tracker: ScanProgressTracker, repository: ThreadRecordingRepository) -> LastScanRotationService:
    return build_service(tracker, repository)


@pytest.fixture
def last_jpeg(tmp_path: Path, tracker: ScanProgressTracker) -> ScanResult:
    return record_last_scan(tracker, save_scan(tmp_path, OutputFormat.JPEG), OutputFormat.JPEG)


@pytest.fixture
def last_pdf(tmp_path: Path, tracker: ScanProgressTracker) -> ScanResult:
    return record_last_scan(tracker, save_scan(tmp_path, OutputFormat.PDF), OutputFormat.PDF)


def read_pdf_rotation(pdf_path: Path) -> int:
    with pikepdf.open(io.BytesIO(pdf_path.read_bytes())) as document:
        return int(document.pages[0].obj.get("/Rotate", 0)) % 360


async def test_a_jpg_is_turned_in_its_own_file(service, last_jpeg):
    await service.rotate_clockwise(JPEG_QUALITY)

    turned = last_jpeg.output_path.read_bytes()
    assert (read_jpeg_size(turned), find_marker_corner(turned)) == (PAGE_SIZE[::-1], "top-right")


async def test_a_pdf_gets_a_quarter_turn_in_its_own_file(service, last_pdf):
    await service.rotate_clockwise(JPEG_QUALITY)

    assert read_pdf_rotation(last_pdf.output_path) == 90


async def test_the_turned_file_keeps_its_name(service, last_jpeg, tmp_path):
    await service.rotate_clockwise(JPEG_QUALITY)

    assert [entry.name for entry in tmp_path.iterdir()] == [JPEG_NAME]


async def test_the_answer_is_the_last_result_with_the_new_size(service, last_jpeg):
    result = await service.rotate_clockwise(JPEG_QUALITY)

    assert result == ScanResult(
        last_jpeg.output_path, OutputFormat.JPEG, SCANNED_AT, last_jpeg.output_path.stat().st_size
    )


async def test_the_tracker_holds_the_turned_result(service, tracker, last_jpeg):
    result = await service.rotate_clockwise(JPEG_QUALITY)

    assert tracker.snapshot().last_result == result


async def test_the_revision_of_the_last_result_rises(service, tracker, last_jpeg):
    revision_before = tracker.snapshot().last_result_revision

    await service.rotate_clockwise(JPEG_QUALITY)

    assert tracker.snapshot().last_result_revision == revision_before + 1


async def test_the_thumbnail_of_the_last_scan_is_turned(service, tracker, last_jpeg):
    await service.rotate_clockwise(JPEG_QUALITY)

    assert read_jpeg_size(tracker.last_thumbnail_jpeg()) == (100, 50)


async def test_a_turn_does_not_count_as_a_new_scan(service, tracker, last_jpeg):
    await service.rotate_clockwise(JPEG_QUALITY)

    assert tracker.snapshot().scans_completed == 1


async def test_two_turns_in_a_row_make_a_half_turn(service, last_jpeg):
    await service.rotate_clockwise(JPEG_QUALITY)
    await service.rotate_clockwise(JPEG_QUALITY)

    turned = last_jpeg.output_path.read_bytes()
    assert (read_jpeg_size(turned), find_marker_corner(turned)) == (PAGE_SIZE, "bottom-right")


async def test_two_turns_asked_at_once_are_done_one_after_the_other(service, last_jpeg):
    await asyncio.gather(service.rotate_clockwise(JPEG_QUALITY), service.rotate_clockwise(JPEG_QUALITY))

    turned = last_jpeg.output_path.read_bytes()
    assert (read_jpeg_size(turned), find_marker_corner(turned)) == (PAGE_SIZE, "bottom-right")


async def test_without_a_scan_of_this_run_raises_no_last_scan(service):
    with pytest.raises(NoLastScanError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_a_scan_in_progress_raises_scan_already_running(service, tracker, last_jpeg):
    tracker.begin_scan(REQUEST)

    with pytest.raises(ScanAlreadyRunningError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_a_scan_in_progress_leaves_the_file_alone(service, tracker, last_jpeg):
    file_before = last_jpeg.output_path.read_bytes()
    tracker.begin_scan(REQUEST)

    with pytest.raises(ScanAlreadyRunningError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert last_jpeg.output_path.read_bytes() == file_before


async def test_a_file_that_is_gone_raises_last_scan_file_missing(service, last_jpeg):
    last_jpeg.output_path.unlink()

    with pytest.raises(LastScanFileMissingError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_a_file_that_is_gone_leaves_the_tracker_as_it_was(service, tracker, last_jpeg):
    last_jpeg.output_path.unlink()
    snapshot_before = tracker.snapshot()

    with pytest.raises(LastScanFileMissingError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert tracker.snapshot() == snapshot_before


async def test_a_file_that_is_not_an_image_raises_saved_scan_unreadable(service, last_jpeg):
    last_jpeg.output_path.write_bytes(b"not a jpeg")

    with pytest.raises(SavedScanUnreadableError):
        await service.rotate_clockwise(JPEG_QUALITY)


async def test_a_file_that_is_not_readable_is_left_as_it_is(service, last_jpeg):
    last_jpeg.output_path.write_bytes(b"not a jpeg")

    with pytest.raises(SavedScanUnreadableError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert last_jpeg.output_path.read_bytes() == b"not a jpeg"


async def test_a_full_disk_leaves_the_original_file_and_the_tracker(tmp_path, tracker):
    scan_path = save_scan(tmp_path, OutputFormat.JPEG)
    record_last_scan(tracker, scan_path, OutputFormat.JPEG)
    file_before = scan_path.read_bytes()
    snapshot_before = tracker.snapshot()
    writer = ScriptedFileWriter({JPEG_NAME: OSError(errno.ENOSPC, "No space left on device")})
    service = build_service(tracker, build_repository(tmp_path, writer))

    with pytest.raises(InsufficientStorageError):
        await service.rotate_clockwise(JPEG_QUALITY)

    assert (scan_path.read_bytes(), tracker.snapshot()) == (file_before, snapshot_before)


async def test_the_disk_work_runs_off_the_event_loop(service, repository, last_jpeg):
    await service.rotate_clockwise(JPEG_QUALITY)

    assert threading.get_ident() not in repository.thread_identifiers


async def test_a_scan_that_ends_during_the_turn_keeps_its_place_in_the_tracker(
    service, tracker, repository, last_jpeg
):
    newer_result = ScanResult(last_jpeg.output_path.with_name("2026-10-18_00002.jpg"), OutputFormat.JPEG, SCANNED_AT, 7)

    def finish_a_newer_scan() -> None:
        tracker.begin_scan(REQUEST)
        tracker.mark_completed(StoredScan(newer_result, b"newer-thumbnail"))

    repository.after_replacement = finish_a_newer_scan

    await service.rotate_clockwise(JPEG_QUALITY)

    assert (tracker.snapshot().last_result, tracker.last_thumbnail_jpeg()) == (newer_result, b"newer-thumbnail")


async def test_a_scan_that_ends_during_the_turn_does_not_undo_the_turn_of_the_file(
    service, tracker, repository, last_jpeg
):
    newer_result = ScanResult(last_jpeg.output_path.with_name("2026-10-18_00002.jpg"), OutputFormat.JPEG, SCANNED_AT, 7)

    def finish_a_newer_scan() -> None:
        tracker.begin_scan(REQUEST)
        tracker.mark_completed(StoredScan(newer_result, b"newer-thumbnail"))

    repository.after_replacement = finish_a_newer_scan

    await service.rotate_clockwise(JPEG_QUALITY)

    assert read_jpeg_size(last_jpeg.output_path.read_bytes()) == PAGE_SIZE[::-1]


async def test_the_tracker_is_idle_after_a_turn(service, tracker, last_jpeg):
    await service.rotate_clockwise(JPEG_QUALITY)

    assert tracker.snapshot().phase is ScanPhase.IDLE
