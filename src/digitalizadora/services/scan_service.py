import asyncio
import logging

from digitalizadora.domain.errors import DigitalizadoraError
from digitalizadora.domain.ports import ScannerGatewayProvider
from digitalizadora.domain.scan_job import ScanJob
from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.services.scan_output_service import ScanOutputService
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker

logger = logging.getLogger(__name__)


class ScanService:
    def __init__(
        self,
        gateway_provider: ScannerGatewayProvider,
        scan_output_service: ScanOutputService,
        progress_tracker: ScanProgressTracker,
    ) -> None:
        self._gateway_provider = gateway_provider
        self._scan_output_service = scan_output_service
        self._progress_tracker = progress_tracker

    def is_scan_in_progress(self) -> bool:
        return self._progress_tracker.snapshot().phase is not ScanPhase.IDLE

    async def scan_one_file(self, request: ScanRequest) -> ScanResult:
        # Outside the try: a rejected second scan must not touch the state of the running one.
        job = self._progress_tracker.begin_scan(request)
        try:
            return await self._scan_and_store(job)
        except DigitalizadoraError as error:
            self._progress_tracker.mark_failed(error.code)
            raise
        except Exception:
            logger.exception("Unexpected failure while scanning")
            self._progress_tracker.mark_failed(DigitalizadoraError.code)
            raise

    async def _scan_and_store(self, job: ScanJob) -> ScanResult:
        # Disk work runs in a thread: a sleeping external disk must not freeze the event loop.
        await asyncio.to_thread(self._scan_output_service.ensure_capacity, job.request)
        gateway = await self._gateway_provider.acquire_gateway()
        self._progress_tracker.mark_scanning()
        scanned_image = await gateway.scan_page(job.request.settings)
        self._progress_tracker.mark_saving()
        stored_scan = await asyncio.to_thread(self._scan_output_service.store, scanned_image, job)
        self._progress_tracker.mark_completed(stored_scan)
        return stored_scan.result
