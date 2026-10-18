from collections import deque
from collections.abc import Sequence

from digitalizadora.domain.ports import ScannerGateway
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_status import ScannerState, ScannerStatus


def build_sample_capabilities() -> ScannerCapabilities:
    return ScannerCapabilities(
        make_and_model="HP DeskJet 2800 series",
        platen_maximum_width=2551,
        platen_maximum_height=3507,
        supported_resolutions=(75, 100, 150, 200, 300, 600),
        supported_color_modes=("RGB24", "Grayscale8"),
        supported_document_formats=("image/jpeg",),
    )


class ScriptedScannerGateway:
    """Scanner gateway whose scan_page returns scripted outcomes in order.

    An outcome that is an Exception instance is raised instead of returned.
    """

    def __init__(
        self,
        capabilities: ScannerCapabilities,
        scan_outcomes: Sequence[ScannedImage | Exception],
    ) -> None:
        self._capabilities = capabilities
        self._remaining_outcomes = deque(scan_outcomes)
        self.scan_requests: list[ScanSettings] = []

    async def read_capabilities(self) -> ScannerCapabilities:
        return self._capabilities

    async def read_status(self) -> ScannerStatus:
        return ScannerStatus(state=ScannerState.IDLE)

    async def scan_page(self, settings: ScanSettings) -> ScannedImage:
        self.scan_requests.append(settings)
        if not self._remaining_outcomes:
            raise AssertionError("ScriptedScannerGateway has no scripted outcome left")
        outcome = self._remaining_outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FixedGatewayProvider:
    """Scanner gateway provider that always hands out the same gateway."""

    def __init__(self, gateway: ScannerGateway) -> None:
        self._gateway = gateway

    async def acquire_gateway(self) -> ScannerGateway:
        return self._gateway
