import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager

from digitalizadora.domain.document_draft import DocumentPage
from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.domain.ports import ScannerGatewayProvider
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.stored_scan import StoredScan
from digitalizadora.services.scan_destination import ScanDestination
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker

logger = logging.getLogger(__name__)


class ScanService:
    """Runs one scan at a time through the single sequence shared by the quick and the document modes."""

    def __init__(
        self,
        gateway_provider: ScannerGatewayProvider,
        scan_output_service: ScanDestination[StoredScan],
        progress_tracker: ScanProgressTracker,
    ) -> None:
        self._gateway_provider = gateway_provider
        self._scan_output_service = scan_output_service
        self._progress_tracker = progress_tracker

    def is_scan_in_progress(self) -> bool:
        return self._progress_tracker.snapshot().phase is not ScanPhase.IDLE

    async def scan_one_file(self, request: ScanRequest) -> ScanResult:
        # Outside the with: a rejected second scan must not touch the state of the running one.
        job = self._progress_tracker.begin_scan(request)
        with self._recording_failures():
            stored_scan = await self._capture_and_store(job, self._scan_output_service)
            self._progress_tracker.mark_completed(stored_scan)
        return stored_scan.result

    async def scan_document_page(
        self, request: ScanRequest, page_capture: ScanDestination[DocumentPage]
    ) -> DocumentPage:
        # Same tracker as the quick mode: a page and a quick scan never run at the same time.
        job = self._progress_tracker.begin_scan(request)
        with self._recording_failures():
            page = await self._capture_and_store(job, page_capture)
            self._progress_tracker.mark_page_added()
        return page

    async def _capture_and_store[StoredOutcome](
        self, job: ScanJob, destination: ScanDestination[StoredOutcome]
    ) -> StoredOutcome:
        # Disk work runs in a thread: a sleeping external disk must not freeze the event loop.
        await asyncio.to_thread(destination.ensure_capacity, job.request)
        gateway = await self._gateway_provider.acquire_gateway()
        self._progress_tracker.mark_scanning()
        scanned_image = await gateway.scan_page(job.request.settings)
        self._progress_tracker.mark_saving()
        return await asyncio.to_thread(destination.store, scanned_image, job)

    @contextmanager
    def _recording_failures(self) -> Iterator[None]:
        try:
            yield
        except DigitalizadoraError as error:
            self._progress_tracker.mark_failed(error.code)
            raise
        except Exception:
            logger.exception("Unexpected failure while scanning")
            self._progress_tracker.mark_failed(DigitalizadoraError.code)
            raise
