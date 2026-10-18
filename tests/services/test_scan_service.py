import asyncio
import logging
import threading
from dataclasses import replace

import pytest

from digitalizadora.domain.errors import (
    DigitalizadoraError,
    InsufficientStorageError,
    LastScanBusyError,
    LocalNetworkBlockedError,
    OutputFolderUnavailableError,
    ScanAlreadyRunningError,
    ScanFailedError,
    ScannerBusyError,
    ScannerUnreachableError,
    ScanRejectedError,
    ScanTimedOutError,
)
from digitalizadora.domain.last_scan import LastScan, SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ScannerGateway
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from digitalizadora.services.scan_service import ScanService
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.observing_scanner_gateway import ObservingScriptedScannerGateway
from tests.fakes.recording_scan_destinations import RecordingScanOutputService
from tests.fakes.scripted_scanner_gateway import FixedGatewayProvider, build_sample_capabilities
from tests.fakes.stored_scans import STORED_SCAN_OUTPUT_PATH, STORED_SCAN_SCANNED_AT, build_last_scan

STARTED_AT = STORED_SCAN_SCANNED_AT
SCAN_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT.settings, output_format=OutputFormat.PDF)
SCANNED_IMAGE = ScannedImage(content=b"jpeg-bytes", media_type="image/jpeg")
EXPECTED_LAST_SCAN = replace(
    build_last_scan((SavedScanFile(STORED_SCAN_OUTPUT_PATH.name, len(SCANNED_IMAGE.content), 1),)),
    scanned_at=STARTED_AT,
)
CAPACITY_ERROR_TYPES = [InsufficientStorageError, OutputFolderUnavailableError]
GATEWAY_ERROR_TYPES = [
    ScannerUnreachableError,
    LocalNetworkBlockedError,
    ScannerBusyError,
    ScanRejectedError,
    ScanFailedError,
    ScanTimedOutError,
]
STORE_ERROR_TYPES = [OutputFolderUnavailableError, InsufficientStorageError]
PROVIDER_ERROR_TYPES = [ScannerUnreachableError, LocalNetworkBlockedError]


def build_failed_snapshot(error_code: str) -> ScanProgressSnapshot:
    return ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=0, last_scan=None, last_error_code=error_code
    )


class FailingGatewayProvider:
    def __init__(self, failure: Exception) -> None:
        self._failure = failure

    async def acquire_gateway(self) -> ScannerGateway:
        raise self._failure


@pytest.fixture
def progress_tracker() -> ScanProgressTracker:
    return ScanProgressTracker(FixedClock(STARTED_AT))


@pytest.fixture
def output_service(progress_tracker: ScanProgressTracker) -> RecordingScanOutputService:
    return RecordingScanOutputService(progress_tracker)


@pytest.fixture
def gateway(progress_tracker: ScanProgressTracker) -> ObservingScriptedScannerGateway:
    return ObservingScriptedScannerGateway(
        build_sample_capabilities(), [SCANNED_IMAGE], progress_tracker
    )


@pytest.fixture
def scan_service(
    gateway: ObservingScriptedScannerGateway,
    output_service: RecordingScanOutputService,
    progress_tracker: ScanProgressTracker,
) -> ScanService:
    return ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)


@pytest.fixture(params=CAPACITY_ERROR_TYPES)
def capacity_failure(
    request: pytest.FixtureRequest, output_service: RecordingScanOutputService
) -> DigitalizadoraError:
    failure = request.param("disk almost full or disconnected")
    output_service.capacity_failure = failure
    return failure


@pytest.fixture(params=STORE_ERROR_TYPES)
def store_failure(
    request: pytest.FixtureRequest, output_service: RecordingScanOutputService
) -> DigitalizadoraError:
    failure = request.param("volume disconnected or full")
    output_service.store_failure = failure
    return failure


def build_scan_service_with_outcomes(
    scan_outcomes: list[ScannedImage | Exception],
    output_service: RecordingScanOutputService,
    progress_tracker: ScanProgressTracker,
) -> ScanService:
    gateway = ObservingScriptedScannerGateway(
        build_sample_capabilities(), scan_outcomes, progress_tracker
    )
    return ScanService(FixedGatewayProvider(gateway), output_service, progress_tracker)


def start_held_scan(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> "asyncio.Task[LastScan]":
    gateway.hold_scans_open()
    return asyncio.create_task(scan_service.scan_one_file(SCAN_REQUEST))


async def test_scan_one_file_returns_the_stored_scan(scan_service: ScanService) -> None:
    assert await scan_service.scan_one_file(SCAN_REQUEST) == EXPECTED_LAST_SCAN


async def test_a_successful_scan_ends_idle_with_its_result_and_no_error(
    scan_service: ScanService, progress_tracker: ScanProgressTracker
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot() == ScanProgressSnapshot(
        phase=ScanPhase.IDLE,
        scans_completed=1,
        last_scan=EXPECTED_LAST_SCAN,
        last_error_code=None,
        last_result_revision=1,
    )


async def test_gateway_receives_the_settings_of_the_request(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert gateway.scan_requests == [SCAN_REQUEST.settings]


async def test_capacity_is_checked_for_the_request(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.capacity_requests == [SCAN_REQUEST]


async def test_store_receives_the_job_started_by_the_tracker(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.stored_jobs == [ScanJob(request=SCAN_REQUEST, started_at=STARTED_AT)]


async def test_phase_is_preparing_during_the_capacity_check(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.phase_during_capacity_check is ScanPhase.PREPARING


async def test_phase_is_scanning_while_the_gateway_is_awaited(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert gateway.phase_during_scan is ScanPhase.SCANNING


async def test_phase_is_saving_while_the_image_is_stored(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.phase_during_store is ScanPhase.SAVING


async def test_capacity_check_runs_outside_the_event_loop_thread(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.capacity_thread_identifier != threading.get_ident()


async def test_store_runs_outside_the_event_loop_thread(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.store_thread_identifier != threading.get_ident()


async def test_capacity_failure_is_recorded_with_its_code(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    capacity_failure: DigitalizadoraError,
) -> None:
    with pytest.raises(type(capacity_failure)):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot() == build_failed_snapshot(capacity_failure.code)


async def test_capacity_failure_does_not_contact_the_gateway(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    capacity_failure: DigitalizadoraError,
) -> None:
    with pytest.raises(type(capacity_failure)):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert gateway.scan_requests == []


@pytest.mark.parametrize("error_type", GATEWAY_ERROR_TYPES)
async def test_every_gateway_error_records_its_own_code(
    progress_tracker: ScanProgressTracker,
    output_service: RecordingScanOutputService,
    error_type: type[DigitalizadoraError],
) -> None:
    scan_service = build_scan_service_with_outcomes(
        [error_type("failure")], output_service, progress_tracker
    )

    with pytest.raises(error_type):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot() == build_failed_snapshot(error_type.code)


async def test_a_gateway_failure_stores_nothing(
    progress_tracker: ScanProgressTracker, output_service: RecordingScanOutputService
) -> None:
    scan_service = build_scan_service_with_outcomes(
        [ScannerUnreachableError("offline")], output_service, progress_tracker
    )

    with pytest.raises(ScannerUnreachableError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert output_service.stored_jobs == []


@pytest.mark.parametrize("error_type", PROVIDER_ERROR_TYPES)
async def test_provider_failure_is_recorded_like_a_gateway_failure(
    output_service: RecordingScanOutputService,
    progress_tracker: ScanProgressTracker,
    error_type: type[DigitalizadoraError],
) -> None:
    provider = FailingGatewayProvider(error_type("not found"))
    scan_service = ScanService(provider, output_service, progress_tracker)

    with pytest.raises(error_type):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot() == build_failed_snapshot(error_type.code)


async def test_store_failure_records_the_code_of_that_error(
    scan_service: ScanService,
    progress_tracker: ScanProgressTracker,
    store_failure: DigitalizadoraError,
) -> None:
    with pytest.raises(type(store_failure)):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot() == build_failed_snapshot(store_failure.code)


async def test_unexpected_exception_is_reraised(
    progress_tracker: ScanProgressTracker, output_service: RecordingScanOutputService
) -> None:
    scan_service = build_scan_service_with_outcomes(
        [RuntimeError("boom")], output_service, progress_tracker
    )

    with pytest.raises(RuntimeError, match="boom"):
        await scan_service.scan_one_file(SCAN_REQUEST)


async def test_unexpected_exception_is_recorded_as_unexpected_error(
    progress_tracker: ScanProgressTracker, output_service: RecordingScanOutputService
) -> None:
    scan_service = build_scan_service_with_outcomes(
        [RuntimeError("boom")], output_service, progress_tracker
    )

    with pytest.raises(RuntimeError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot() == build_failed_snapshot("unexpected_error")


async def test_unexpected_exception_is_logged_with_its_traceback(
    progress_tracker: ScanProgressTracker,
    output_service: RecordingScanOutputService,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR)
    scan_service = build_scan_service_with_outcomes(
        [RuntimeError("boom")], output_service, progress_tracker
    )

    with pytest.raises(RuntimeError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert [record.exc_info is not None for record in caplog.records] == [True]


async def test_a_new_scan_succeeds_after_a_failure(
    progress_tracker: ScanProgressTracker, output_service: RecordingScanOutputService
) -> None:
    scan_service = build_scan_service_with_outcomes(
        [ScannerBusyError("busy"), SCANNED_IMAGE], output_service, progress_tracker
    )
    with pytest.raises(ScannerBusyError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    result = await scan_service.scan_one_file(SCAN_REQUEST)

    assert progress_tracker.snapshot() == ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=1, last_scan=result, last_error_code=None, last_result_revision=1
    )


async def test_second_call_during_a_scan_raises_scan_already_running(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    gateway.release_scan.set()
    await first_scan


async def test_second_call_leaves_the_running_scan_untouched(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    progress_tracker: ScanProgressTracker,
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()
    snapshot_before = progress_tracker.snapshot()

    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    snapshot_after = progress_tracker.snapshot()
    gateway.release_scan.set()
    await first_scan
    assert snapshot_after == snapshot_before


async def test_first_scan_completes_after_a_rejected_second_call(
    scan_service: ScanService,
    gateway: ObservingScriptedScannerGateway,
    progress_tracker: ScanProgressTracker,
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()
    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    gateway.release_scan.set()
    result = await first_scan

    assert progress_tracker.snapshot() == ScanProgressSnapshot(
        phase=ScanPhase.IDLE, scans_completed=1, last_scan=result, last_error_code=None, last_result_revision=1
    )


async def test_rejected_second_call_never_reaches_the_gateway(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()
    with pytest.raises(ScanAlreadyRunningError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    gateway.release_scan.set()
    await first_scan

    assert gateway.scan_requests == [SCAN_REQUEST.settings]


async def test_is_scan_in_progress_is_false_when_idle(scan_service: ScanService) -> None:
    assert scan_service.is_scan_in_progress() is False


async def test_is_scan_in_progress_is_true_while_scanning(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()

    in_progress = scan_service.is_scan_in_progress()

    gateway.release_scan.set()
    await first_scan
    assert in_progress is True


async def test_is_scan_in_progress_is_false_after_completion(scan_service: ScanService) -> None:
    await scan_service.scan_one_file(SCAN_REQUEST)

    assert scan_service.is_scan_in_progress() is False


async def test_is_scan_in_progress_is_false_after_a_failure(
    scan_service: ScanService, output_service: RecordingScanOutputService
) -> None:
    output_service.capacity_failure = InsufficientStorageError("disk almost full")
    with pytest.raises(InsufficientStorageError):
        await scan_service.scan_one_file(SCAN_REQUEST)

    assert scan_service.is_scan_in_progress() is False


async def test_ensure_scan_can_start_accepts_an_idle_service(scan_service: ScanService) -> None:
    scan_service.ensure_scan_can_start()


async def test_ensure_scan_can_start_refuses_during_a_scan(
    scan_service: ScanService, gateway: ObservingScriptedScannerGateway
) -> None:
    first_scan = start_held_scan(scan_service, gateway)
    await gateway.scan_started.wait()

    with pytest.raises(ScanAlreadyRunningError):
        scan_service.ensure_scan_can_start()

    gateway.release_scan.set()
    await first_scan


async def test_ensure_scan_can_start_refuses_while_the_last_scan_is_adjusted(
    scan_service: ScanService, progress_tracker: ScanProgressTracker
) -> None:
    progress_tracker.mark_last_scan_edit_started()

    with pytest.raises(LastScanBusyError):
        scan_service.ensure_scan_can_start()


async def test_a_scan_is_refused_while_the_last_scan_is_adjusted(
    scan_service: ScanService, progress_tracker: ScanProgressTracker
) -> None:
    progress_tracker.mark_last_scan_edit_started()

    with pytest.raises(LastScanBusyError):
        await scan_service.scan_one_file(SCAN_REQUEST)
