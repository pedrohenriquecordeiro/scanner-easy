from dataclasses import FrozenInstanceError, replace
from datetime import timedelta

import pytest

from digitalizadora.domain.errors import LastScanBusyError, ScanAlreadyRunningError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.stored_scan import StoredScan
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
    phase=ScanPhase.IDLE, scans_completed=0, last_scan=None, last_error_code=None
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


def test_mark_completed_stores_the_last_scan(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_completed(stored_scan)

    assert tracker.snapshot().last_scan == stored_scan.last_scan


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


def test_the_last_scan_survives_a_later_failure(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(stored_scan)
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().last_scan == stored_scan.last_scan


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


def test_mark_page_added_returns_to_idle(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_scanning()
    tracker.mark_saving()

    tracker.mark_page_added()

    assert tracker.snapshot().phase is ScanPhase.IDLE


def test_mark_page_added_counts_one_more_completed_scan(tracker: ScanProgressTracker) -> None:
    for _ in range(2):
        tracker.begin_scan(SCAN_REQUEST)
        tracker.mark_page_added()

    assert tracker.snapshot().scans_completed == 2


def test_mark_page_added_keeps_the_last_scan_of_the_quick_mode(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(stored_scan)
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_page_added()

    assert tracker.snapshot().last_scan == stored_scan.last_scan


def test_mark_page_added_keeps_the_thumbnail_of_the_quick_mode(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_page_added()

    assert tracker.last_thumbnail_jpeg() == SAMPLE_THUMBNAIL_JPEG


def test_mark_page_added_after_a_failure_leaves_no_error_code(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_failed("scan_failed")
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_page_added()

    assert tracker.snapshot().last_error_code is None


def test_begin_scan_is_accepted_again_after_a_page_was_added(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_page_added()

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_mark_page_added_does_not_change_an_earlier_snapshot(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    snapshot_before = tracker.snapshot()

    tracker.mark_page_added()

    assert snapshot_before.phase is ScanPhase.PREPARING


def complete_a_scan(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(build_stored_scan())


SCAN_IDENTIFIER = build_stored_scan().last_scan.scan_identifier


def build_turned_scan() -> StoredScan:
    stored_scan = build_stored_scan()
    return StoredScan(stored_scan.last_scan.with_framing(PageFraming().turned_clockwise()), b"turned-thumbnail")


def test_a_new_tracker_has_revision_zero_of_the_last_result(tracker: ScanProgressTracker) -> None:
    assert tracker.snapshot().last_result_revision == 0


def test_mark_completed_raises_the_revision_of_the_last_result(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)

    assert tracker.snapshot().last_result_revision == 1


def test_each_completed_scan_raises_the_revision_by_one(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)
    complete_a_scan(tracker)

    assert tracker.snapshot().last_result_revision == 2


def test_a_failed_scan_keeps_the_revision(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_failed("scan_failed")

    assert tracker.snapshot().last_result_revision == 0


def test_a_document_page_keeps_the_revision(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)
    tracker.begin_scan(SCAN_REQUEST)

    tracker.mark_page_added()

    assert tracker.snapshot().last_result_revision == 1


def test_replace_last_scan_swaps_the_scan(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)
    turned_scan = build_turned_scan()

    tracker.replace_last_scan(SCAN_IDENTIFIER, turned_scan)

    assert tracker.snapshot().last_scan == turned_scan.last_scan


def test_replace_last_scan_swaps_the_thumbnail(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)

    tracker.replace_last_scan(SCAN_IDENTIFIER, build_turned_scan())

    assert tracker.last_thumbnail_jpeg() == b"turned-thumbnail"


def test_replace_last_scan_raises_the_revision(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)

    tracker.replace_last_scan(SCAN_IDENTIFIER, build_turned_scan())

    assert tracker.snapshot().last_result_revision == 2


def test_replace_last_scan_does_not_count_a_new_scan(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)

    tracker.replace_last_scan(SCAN_IDENTIFIER, build_turned_scan())

    assert tracker.snapshot().scans_completed == 1


def test_replace_last_scan_keeps_the_phase_and_the_error(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_failed("scan_failed")

    tracker.replace_last_scan(SCAN_IDENTIFIER, build_turned_scan())

    assert (tracker.snapshot().phase, tracker.snapshot().last_error_code) == (ScanPhase.IDLE, "scan_failed")


def test_replace_last_scan_does_nothing_when_a_newer_scan_took_its_place(tracker: ScanProgressTracker) -> None:
    complete_a_scan(tracker)
    newer_last_scan = replace(build_stored_scan().last_scan, scan_identifier="0000000000000002")
    newer_scan = StoredScan(newer_last_scan, b"newer-thumbnail")
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_completed(newer_scan)
    snapshot_before = tracker.snapshot()

    tracker.replace_last_scan(SCAN_IDENTIFIER, build_turned_scan())

    assert (tracker.snapshot(), tracker.last_thumbnail_jpeg()) == (snapshot_before, b"newer-thumbnail")


def test_replace_last_scan_without_a_last_scan_does_nothing(tracker: ScanProgressTracker) -> None:
    tracker.replace_last_scan(SCAN_IDENTIFIER, build_turned_scan())

    assert tracker.snapshot() == EMPTY_SNAPSHOT


def test_restore_last_scan_gives_the_tracker_the_scan_of_the_previous_run(tracker: ScanProgressTracker) -> None:
    stored_scan = build_stored_scan()

    tracker.restore_last_scan(stored_scan)

    assert (tracker.snapshot().last_scan, tracker.last_thumbnail_jpeg()) == (
        stored_scan.last_scan,
        SAMPLE_THUMBNAIL_JPEG,
    )


def test_restore_last_scan_does_not_count_a_scan(tracker: ScanProgressTracker) -> None:
    tracker.restore_last_scan(build_stored_scan())

    assert tracker.snapshot().scans_completed == 0


def test_restore_last_scan_raises_the_revision(tracker: ScanProgressTracker) -> None:
    tracker.restore_last_scan(build_stored_scan())

    assert tracker.snapshot().last_result_revision == 1


def test_begin_scan_raises_while_the_last_scan_is_being_adjusted(tracker: ScanProgressTracker) -> None:
    tracker.mark_last_scan_edit_started()

    with pytest.raises(LastScanBusyError):
        tracker.begin_scan(SCAN_REQUEST)


def test_a_refused_begin_scan_during_an_edit_leaves_the_tracker_idle(tracker: ScanProgressTracker) -> None:
    tracker.mark_last_scan_edit_started()

    with pytest.raises(LastScanBusyError):
        tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot() == EMPTY_SNAPSHOT


def test_begin_scan_is_accepted_again_when_the_edit_ends(tracker: ScanProgressTracker) -> None:
    tracker.mark_last_scan_edit_started()
    tracker.mark_last_scan_edit_ended()

    tracker.begin_scan(SCAN_REQUEST)

    assert tracker.snapshot().phase is ScanPhase.PREPARING


def test_a_scan_running_is_reported_before_an_edit_running(tracker: ScanProgressTracker) -> None:
    tracker.begin_scan(SCAN_REQUEST)
    tracker.mark_last_scan_edit_started()

    with pytest.raises(ScanAlreadyRunningError):
        tracker.ensure_scan_can_start()


def test_ensure_scan_can_start_changes_nothing(tracker: ScanProgressTracker) -> None:
    tracker.ensure_scan_can_start()

    assert tracker.snapshot() == EMPTY_SNAPSHOT
