from dataclasses import replace

from digitalizadora.domain.errors import ScanAlreadyRunningError
from digitalizadora.domain.ports import Clock
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_progress import ScanPhase, ScanProgressSnapshot
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.stored_scan import StoredScan

INITIAL_SNAPSHOT = ScanProgressSnapshot(
    phase=ScanPhase.IDLE, scans_completed=0, last_result=None, last_error_code=None
)


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

    def begin_scan(self, request: ScanRequest) -> ScanJob:
        if self._snapshot.phase is not ScanPhase.IDLE:
            raise ScanAlreadyRunningError("A scan is already in progress")
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
            last_result=stored_scan.result,
        )

    def mark_failed(self, error_code: str) -> None:
        self._snapshot = replace(self._snapshot, phase=ScanPhase.IDLE, last_error_code=error_code)

    def snapshot(self) -> ScanProgressSnapshot:
        return self._snapshot

    def last_thumbnail_jpeg(self) -> bytes | None:
        return self._last_thumbnail_jpeg

    def mark_page_added(self) -> None:
        # A document page counts as a completed scan, but the quick-mode panel keeps its last file:
        # last_result and the thumbnail stay, and begin_scan already cleared the error code.
        self._snapshot = replace(
            self._snapshot,
            phase=ScanPhase.IDLE,
            scans_completed=self._snapshot.scans_completed + 1,
        )
