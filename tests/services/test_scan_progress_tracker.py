from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest

from digitalizadora.domain.errors import ScanAlreadyRunningError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from tests.fakes.fixed_clock import FixedClock
from tests.fakes.stored_scans import (
    SAMPLE_THUMBNAIL_JPEG,
    STORED_SCAN_SCANNED_AT,
    build_stored_scan,
)

STARTED_AT = STORED_SCAN_SCANNED_AT
SCAN_REQUEST = ScanRequest(settings=ScanPreset.DOCUMENT.settings, output_format=OutputFormat.PDF)
EMPTY_SNAPSHOT = ScanProgressSnapshot(
    phase=ScanPhase.IDLE, scans_completed=0, last_result=None, last_error_code=None
)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(STARTED_AT)


@pytest.fixture
def tracker(clock: FixedClock) -> ScanProgressTracker:
    return ScanProgressTracker(clock)


def test_new_tracker_is_idle_without_history(tracker: ScanProgressTracker) -> None:
    assert tracker.snapshot() == EMPTY_SNAPSHOT


def test_new_tracker_has_no_thumbnail(tracker: ScanProgressTracker) -> None:
    assert tracker.last_thumbnail_jpeg() is None


def test_begin_scan_moves_to_preparing(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_begin_scan_returns_job_with_request_and_clock_time(
    tracker: ScanProgressTracker, clock: FixedClock
) -> None:
    clock.advance(90)

    job = tracker.begin_scan(SCAN_REQUEST)

    assert (job.request, job.started_at) == (SCAN_REQUEST, STARTED_AT + timedelta(seconds=90))


def test_begin_scan_clears_the_previous_error_code(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_failed("scanner_unreachable")

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().last_error_code is None


def test_mark_scanning_moves_to_scanning(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_scanning()

    assert tracker.snapshot().phase is ScanPhase.SCANNING


def test_mark_saving_moves_to_saving(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()

    tracker.mark_saving()

    assert tracker.snapshot().phase is ScanPhase.SAVING


def test_mark_completed_returns_to_idle(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(build_stored_scan())

    assert tracker.snapshot().phase is ScanPhase.IDLE


def test_mark_completed_increments_scans_completed(tracker: ScanProgressTracker) -> None:
    for _ in range(2):
        tracker.begin_scan(SCAN_REQUEST)
        tracker.mark_completed(build_stored_scan())

    assert tracker.snapshot().scans_completed == 2


def test_mark_completed_stores_the_last_result(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(stored_scan)

    assert tracker.snapshot().last_result == stored_scan.result


def test_mark_completed_stores_the_thumbnail(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(build_stored_scan())

    assert tracker.last_thumbnail_jpeg() == SAMPLE_THUMBNAIL_JPEG


def test_mark_failed_stores_the_error_code(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().last_error_code == "scan_failed"


def test_mark_failed_returns_to_idle(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().phase is ScanPhase.IDLE


def test_mark_failed_does_not_count_a_completed_scan(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().scans_completed == 0


def test_thumbnail_survives_a_later_failure(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.last_thumbnail_jpeg() == SAMPLE_THUMBNAIL_JPEG


def test_last_result_survives_a_later_failure(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(stored_scan)
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().last_result == stored_scan.result


def test_a_new_thumbnail_replaces_the_previous_one(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan(b"first"))
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(build_stored_scan(b"second"))

    assert tracker.last_thumbnail_jpeg() == b"second"


def test_begin_scan_raises_while_preparing(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    with pytest.raises(ScanAlreadyRunningError):
        tracker.begin_scan(SCAN_REQUEST)


@pytest.mark.parametrize("transition_name", ["mark_scanning", "mark_saving"])
def test_begin_scan_raises_while_scanning_or_saving(
    tracker: ScanProgressTracker, transition_name: str
) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    getattr(tracker, transition_name)()

    with pytest.raises(ScanAlreadyRunningError):
        tracker.begin_scan(SCAN_REQUEST)


def test_rejected_begin_scan_leaves_the_running_scan_untouched(
    tracker: ScanProgressTracker,
) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()
    snapshot_before = tracker.snapshot()

    with pytest.raises(ScanAlreadyRunningError):
        tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot() == snapshot_before


def test_begin_scan_is_accepted_again_after_completion(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_begin_scan_is_accepted_again_after_failure(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_failed("scan_failed")

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_snapshot_is_not_changed_by_later_transitions(tracker: ScanProgressTracker) -> None:
    snapshot_before = tracker.snapshot()

    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())

    assert snapshot_before == EMPTY_SNAPSHOT


def test_snapshot_rejects_attribute_assignment(tracker: ScanProgressTracker) -> None:
    snapshot = tracker.snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.scans_completed = 99
