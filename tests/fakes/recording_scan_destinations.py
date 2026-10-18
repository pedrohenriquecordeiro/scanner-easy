import threading
from dataclasses import replace

from digitalizadora.domain.documents.document_draft import DocumentPage
from digitalizadora.domain.quick_scan.last_scan import SavedScanFile
from digitalizadora.domain.quick_scan.scan_progress import ScanPhase
from digitalizadora.domain.quick_scan.stored_scan import StoredScan
from digitalizadora.domain.scanning.scan_job import ScanJob
from digitalizadora.domain.scanning.scan_request import ScanRequest
from digitalizadora.domain.scanning.scanned_image import ScannedImage
from digitalizadora.services.application.scan_progress_tracker import ScanProgressTracker
from tests.fakes.stored_scans import STORED_SCAN_OUTPUT_PATH, build_last_scan


class RecordingScanOutputService:
    """Duck-typed stand-in for ScanOutputService (same two methods)."""

    def __init__(self, progress_tracker: ScanProgressTracker) -> None:
        self._progress_tracker = progress_tracker
        self.capacity_failure: Exception | None = None
        self.store_failure: Exception | None = None
        self.capacity_requests: list[ScanRequest] = []
        self.stored_jobs: list[ScanJob] = []
        self.phase_during_capacity_check: ScanPhase | None = None
        self.phase_during_store: ScanPhase | None = None
        self.capacity_thread_identifier: int | None = None
        self.store_thread_identifier: int | None = None

    def ensure_capacity(self, request: ScanRequest) -> None:
        self.capacity_requests.append(request)
        self.phase_during_capacity_check = self._progress_tracker.snapshot().phase
        self.capacity_thread_identifier = threading.get_ident()
        if self.capacity_failure is not None:
            raise self.capacity_failure

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredScan:
        self._record_store(job)
        saved_file = SavedScanFile(STORED_SCAN_OUTPUT_PATH.name, len(scanned_image.content), 1)
        last_scan = replace(
            build_last_scan((saved_file,)), output_format=job.request.output_format, scanned_at=job.started_at
        )
        return StoredScan(last_scan=last_scan, thumbnail_jpeg=b"thumbnail")

    def _record_store(self, job: ScanJob) -> None:
        self.stored_jobs.append(job)
        self.phase_during_store = self._progress_tracker.snapshot().phase
        self.store_thread_identifier = threading.get_ident()
        if self.store_failure is not None:
            raise self.store_failure


class RecordingDocumentPageDestination(RecordingScanOutputService):
    """Duck-typed stand-in for DocumentPageCapture: same records, but store returns a DocumentPage."""

    def __init__(self, progress_tracker: ScanProgressTracker, stored_page: DocumentPage) -> None:
        super().__init__(progress_tracker)
        self._stored_page = stored_page

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> DocumentPage:
        self._record_store(job)
        return self._stored_page
