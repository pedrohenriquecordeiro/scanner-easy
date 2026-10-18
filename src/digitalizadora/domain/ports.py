from datetime import datetime
from pathlib import Path
from typing import Protocol

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.domain.scanned_image import ScannedImage
from digitalizadora.domain.scanner_capabilities import ScannerCapabilities
from digitalizadora.domain.scanner_endpoint import ScannerEndpoint
from digitalizadora.domain.scanner_status import ScannerStatus


class Clock(Protocol):
    def now(self) -> datetime: ...


class ScannerGateway(Protocol):
    async def read_capabilities(self) -> ScannerCapabilities: ...

    async def read_status(self) -> ScannerStatus: ...

    async def scan_page(self, settings: ScanSettings) -> ScannedImage: ...


class ScannerGatewayProvider(Protocol):
    async def acquire_gateway(self) -> ScannerGateway: ...


class ScannerDiscovery(Protocol):
    async def discover(self, timeout_seconds: float) -> list[ScannerEndpoint]: ...


class ScannerEndpointRepository(Protocol):
    def load(self) -> ScannerEndpoint | None: ...

    def save(self, endpoint: ScannerEndpoint) -> None: ...

    def clear(self) -> None: ...


class ApplicationSettingsRepository(Protocol):
    def load(self) -> ApplicationSettings: ...

    def save(self, settings: ApplicationSettings) -> None: ...


class ScanOutputRepository(Protocol):
    def output_folder(self) -> Path: ...

    def ensure_output_folder_ready(self) -> None: ...

    def save(self, encoded_scan: EncodedScan) -> Path: ...
