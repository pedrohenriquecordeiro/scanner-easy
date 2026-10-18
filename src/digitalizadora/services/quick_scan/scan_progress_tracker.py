from dataclasses import replace

from digitalizadora.domain.errors import LastScanBusyError, ScanAlreadyRunningError
from digitalizadora.domain.ports import Clock
from digitalizadora.domain.quick_scan.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.quick_scan.stored_scan import StoredScan
from digitalizadora.domain.scanning.scan_job import ScanJob
from digitalizadora.domain.scanning.scan_request import ScanRequest

INITIAL_SNAPSHOT = ScanProgressSnapshot(phase=ScanPhase.IDLE, scans_completed=0, last_scan=None, last_error_code=None)


class ScanProgressTracker:
    """Holds the progress of the current scan and the outcome of the previous ones.

    Transitions run on the event loop thread only; the state endpoint may read from a worker
    thread. Each transition replaces the whole immutable snapshot in a single assignment, so a
    reader on another thread always sees a complete snapshot without any lock.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._snapshot = INITIAL_SNAPSHOT
        self._last_thumbnail_jpeg: bytes | None = None
        self._is_last_scan_edit_running = False

    def ensure_scan_can_start(self) -> None:
        if self._snapshot.phase is not ScanPhase.IDLE:
            raise ScanAlreadyRunningError("A scan is already in progress")
        if self._is_last_scan_edit_running:
            raise LastScanBusyError("The last scan is being adjusted")

    def begin_scan(self, request: ScanRequest) -> ScanJob:
        self.ensure_scan_can_start()
        self._snapshot = replace(self._snapshot, phase=ScanPhase.PREPARING, last_error_code=None)
        return ScanJob(request=request, started_at=self._clock.now())

    def mark_scanning(self) -> None:
        self._snapshot = replace(self._snapshot, phase=ScanPhase.SCANNING)

    def mark_saving(self) -> None:
        self._snapshot = replace(self._snapshot, phase=ScanPhase.SAVING)

    def mark_completed(self, stored_scan: StoredScan) -> None:
        # The thumbnail first: the page asks for it as soon as scans_completed changes.
        self._last_thumbnail_jpeg = stored_scan.thumbnail_jpeg
        self._snapshot = replace(
            self._snapshot,
            phase=ScanPhase.IDLE,
            scans_completed=self._snapshot.scans_completed + 1,
            last_scan=stored_scan.last_scan,
            last_result_revision=self._snapshot.last_result_revision + 1,
        )

    def replace_last_scan(self, expected_scan_identifier: str, replacement: StoredScan) -> None:
        """Swaps the last scan for its adjusted version, unless a newer scan took its place meanwhile."""
        last_scan = self._snapshot.last_scan
        if last_scan is None or last_scan.scan_identifier != expected_scan_identifier:
            return
        self._last_thumbnail_jpeg = replacement.thumbnail_jpeg
        self._snapshot = replace(
            self._snapshot,
            last_scan=replacement.last_scan,
            last_result_revision=self._snapshot.last_result_revision + 1,
        )

    def restore_last_scan(self, stored_scan: StoredScan) -> None:
        """Only at start-up: the last scan of a previous run comes back from its slot. It counts as no new scan."""
        self._last_thumbnail_jpeg = stored_scan.thumbnail_jpeg
        self._snapshot = replace(
            self._snapshot,
            last_scan=stored_scan.last_scan,
            last_result_revision=self._snapshot.last_result_revision + 1,
        )

    def mark_last_scan_edit_started(self) -> None:
        self._is_last_scan_edit_running = True

    def mark_last_scan_edit_ended(self) -> None:
        self._is_last_scan_edit_running = False

    def mark_failed(self, error_code: str) -> None:
        self._snapshot = replace(self._snapshot, phase=ScanPhase.IDLE, last_error_code=error_code)

    def snapshot(self) -> ScanProgressSnapshot:
        return self._snapshot

    def last_thumbnail_jpeg(self) -> bytes | None:
        return self._last_thumbnail_jpeg

    def mark_page_added(self) -> None:
        # A document page counts as a completed scan, but the quick-mode panel keeps its last file:
        # last_scan and the thumbnail stay, and begin_scan already cleared the error code.
        self._snapshot = replace(
            self._snapshot,
            phase=ScanPhase.IDLE,
            scans_completed=self._snapshot.scans_completed + 1,
        )
