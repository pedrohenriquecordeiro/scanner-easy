import asyncio

from digitalizadora.domain.scan_progress import ScanPhase
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.services.scan_progress_tracker import ScanProgressTracker
from tests.fakes.scripted_scanner_gateway import ScriptedScannerGateway


class ObservingScriptedScannerGateway(ScriptedScannerGateway):
    """Scripted gateway that can hold a scan open and reports the phase it ran in."""

    def __init__(
        self,
        capabilities: ScannerCapabilities,
        scan_outcomes: list[ScannedImage | Exception],
        progress_tracker: ScanProgressTracker,
    ) -> None:
        super().__init__(capabilities, scan_outcomes)
        self._progress_tracker = progress_tracker
        self.scan_started = asyncio.Event()
        self.release_scan = asyncio.Event()
        self.release_scan.set()
        self.phase_during_scan: ScanPhase | None = None

    def hold_scans_open(self) -> None:
        self.release_scan.clear()

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        self.phase_during_scan = self._progress_tracker.snapshot().phase
        self.scan_started.set()
        await self.release_scan.wait()
        return await super().scan_page(settings)
