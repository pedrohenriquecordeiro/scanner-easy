from typing import Protocol

from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scanned_image import ScannedImage


class ScanDestination[StoredOutcome](Protocol):
    """Where the single scan sequence of ScanService keeps the scanned image.

    A service protocol, not an infrastructure port: ScanOutputService is a ScanDestination[StoredScan]
    (the quick mode) and DocumentPageCapture is a ScanDestination[DocumentPage] (the document mode).
    Both methods touch the disk and run in a worker thread.
    """

    def ensure_capacity(self, request: ScanRequest) -> None: ...

    def store(self, scanned_image: ScannedImage, job: ScanJob) -> StoredOutcome: ...
