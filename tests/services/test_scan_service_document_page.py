import asyncio
import logging

import pytest

from digitalizadora.domain.documents.document_draft import DocumentPage
from digitalizadora.domain.errors import (
    DigitalizadoraError,
    DraftStorageUnavailableError,
    InsufficientDraftStorageError,
    ScanAlreadyRunningError,
    ScannerUnreachableError,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.scan_service import ScanService
from tests.fakes.document_drafts import build_document_page, page_identifier_at
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.observing_scanner_gateway import ObservingScriptedScannerGateway
from tests.fakes.recording_scan_destinations import (
    RecordingDocumentPageDestination,
    RecordingScanOutputService,
)
from tests.fakes.scripted_scanner_gateway import FixedGatewayProvider, build_sample_capabilities
from tests.fakes.stored_scans import STORED_SCAN_SCANNED_AT

STARTED_AT = STORED_SCAN_SCANNED_AT
PAGE_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT.settings, output_format=OutputFormat.PDF)
SCANNED_IMAGE = ScannedImage(content=b"jpeg-bytes", media_type="image/jpeg")
STORED_PAGE = build_document_page(page_identifier_at(1))
QUICK_MODE_THUMBNAIL_JPEG = b"thumbnail"


@pytest.fixture
def progress_tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(STARTED_AT))


@pytest.fixture
def output_service(progress_tracker: ScanProgressTracker) -> RecordingScanOutputService:
    return RecordingScanOutputService(progress_tracker)


@pytest.fixture
def page_destination(progress_tracker: ScanProgressTracker) -> RecordingDocumentPageDestination:
    return RecordingDocumentPageDestination(progress_tracker, STORED_PAGE)


@pytest.fixture
def gateway(progress_tracker: ScanProgressTracker) -> ObservingScriptedScannerGateway:
    return ObservingScriptedScannerGateway(
        build_sample_capabilities(), [SCANNED_IMAGE, SCANNED_IMAGE], progress_tracker
    )


@pytest.fixture
def scan_service(
    gateway: ObservingScriptedScannerGateway,
    output_service: RecordingScanOutputService,
    progress_tracker: ScanProgressTracker,
) -> ScanService:
    return ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)


def start_held_page(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> "asyncio.Task[DocumentPage]":
    gateway.hold_scans_open()
    return asyncio.create_task(scan_service.scan_document_page(PAGE_REQUEST, page_destination))


def start_held_quick_scan(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> "asyncio.Task[ScanResult]":
    gateway.hold_scans_open()
    return asyncio.create_task(scan_service.scan_one_file(PAGE_REQUEST))


async def test_scan_document_page_returns_the_page_stored_by_the_destination(
    scan_service: ScanService, page_destination: RecordingDocumentPageDestination
) -> None:
    assert await scan_service.scan_document_page(PAGE_REQUEST, page_destination) == STORED_PAGE


async def test_the_destination_stores_the_job_started_by_the_tracker(
    scan_service: ScanService, page_destination: RecordingDocumentPageDestination
) -> None:
    await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert page_destination.stored_jobs == [ScanJob(request=PAGE_REQUEST, started_at=STARTED_AT)]


async def test_the_destination_checks_the_capacity_for_the_request(
    scan_service: ScanService, page_destination: RecordingDocumentPageDestination
) -> None:
    await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert page_destination.capacity_requests == [PAGE_REQUEST]


async def test_a_page_never_reaches_the_quick_mode_output_service(
    scan_service: ScanService,
    output_service: RecordingScanOutputService,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert (output_service.capacity_requests, output_service.stored_jobs) == ([], [])


async def test_a_page_ends_idle_with_one_more_scan_and_no_quick_mode_result(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.snapshot() == ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=1, last_scan=None, last_error_code=None
    )


async def test_a_page_after_a_quick_scan_counts_both_scans(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    await scan_service.scan_one_file(PAGE_REQUEST)

    await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.snapshot().scans_completed == 2


async def test_a_page_after_a_quick_scan_keeps_the_quick_mode_result(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    quick_scan = await scan_service.scan_one_file(PAGE_REQUEST)

    await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.snapshot().last_scan == quick_scan


async def test_a_page_after_a_quick_scan_keeps_the_quick_mode_thumbnail(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    await scan_service.scan_one_file(PAGE_REQUEST)

    await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.last_thumbnail_jpeg() == QUICK_MODE_THUMBNAIL_JPEG


async def test_destination_capacity_failure_is_recorded_with_its_code(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    page_destination.capacity_failure = InsufficientDraftStorageError("internal disk almost full")

    with pytest.raises(InsufficientDraftStorageError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.snapshot().last_error_code == "insufficient_draft_storage"


async def test_destination_capacity_failure_does_not_contact_the_gateway(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    page_destination.capacity_failure = InsufficientDraftStorageError("internal disk almost full")

    with pytest.raises(InsufficientDraftStorageError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert gateway.scan_requests == []


async def test_destination_store_failure_is_recorded_with_its_code(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    page_destination.store_failure = DraftStorageUnavailableError("drafts folder unreadable")

    with pytest.raises(DraftStorageUnavailableError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.snapshot() == ScanProgressSnapshot(
        phase=ScanPhase.IDLE,
        scans_completed=0,
        last_scan=None,
        last_error_code="draft_storage_unavailable",
    )


async def test_gateway_failure_during_a_page_is_recorded_with_its_code(
    progress_tracker: ScanProgressTracker,
    output_service: RecordingScanOutputService,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    gateway = ObservingScriptedScannerGateway(
        build_sample_capabilities(), [ScannerUnreachableError("offline")], progress_tracker
    )
    scan_service = ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)

    with pytest.raises(ScannerUnreachableError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.snapshot().last_error_code == "scanner_unreachable"


async def test_unexpected_destination_failure_is_recorded_as_unexpected_error(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    page_destination.store_failure = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert progress_tracker.snapshot().last_error_code == DigitalizadoraError.code


async def test_unexpected_destination_failure_is_logged_with_its_traceback(
    scan_service: ScanService,
    page_destination: RecordingDocumentPageDestination,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    page_destination.store_failure = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    assert [record.exc_info is not None for record in caplog.records] == [True]


async def test_second_page_during_a_page_raises_scan_already_running(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    first_page = start_held_page(scan_service, gateway, page_destination)
    await gateway.scan_started.wait()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    gateway.release_scan.set()
    await first_page


async def test_rejected_second_page_leaves_the_running_page_untouched(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    progress_tracker: ScanProgressTracker,
) -> None:
    page_destination = RecordingDocumentPageDestination(progress_tracker, STORED_PAGE)
    first_page = start_held_page(scan_service, gateway, page_destination)
    await gateway.scan_started.wait()
    snapshot_before = progress_tracker.snapshot()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    snapshot_after = progress_tracker.snapshot()
    gateway.release_scan.set()
    await first_page
    assert snapshot_after == snapshot_before


async def test_rejected_second_page_never_reaches_the_destination(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    first_page = start_held_page(scan_service, gateway, page_destination)
    await gateway.scan_started.wait()
    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    gateway.release_scan.set()
    await first_page

    assert page_destination.capacity_requests == [PAGE_REQUEST]


async def test_quick_scan_is_refused_while_a_page_is_scanned(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    first_page = start_held_page(scan_service, gateway, page_destination)
    await gateway.scan_started.wait()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(PAGE_REQUEST)

    gateway.release_scan.set()
    await first_page


async def test_page_is_refused_while_a_quick_scan_runs(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    quick_scan = start_held_quick_scan(scan_service, gateway)
    await gateway.scan_started.wait()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    gateway.release_scan.set()
    await quick_scan


async def test_page_refused_during_a_quick_scan_never_reaches_the_destination(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    quick_scan = start_held_quick_scan(scan_service, gateway)
    await gateway.scan_started.wait()
    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_document_page(PAGE_REQUEST, page_destination)

    gateway.release_scan.set()
    await quick_scan

    assert page_destination.capacity_requests == []


async def test_is_scan_in_progress_is_true_while_a_page_is_scanned(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    page_destination: RecordingDocumentPageDestination,
) -> None:
    first_page = start_held_page(scan_service, gateway, page_destination)
    await gateway.scan_started.wait()

    in_progress = scan_service.is_scan_in_progress()

    gateway.release_scan.set()
    await first_page
    assert in_progress is True
