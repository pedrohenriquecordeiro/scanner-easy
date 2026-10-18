from dataclasses import dataclass

from digitalizadora.domain.scanner.scanner_route import ScannerRoute


@dataclass(frozen=True)
class ScannerEndpoint:
    base_address: str
    display_name: str
    universally_unique_identifier: str | None = None
    route: ScannerRoute = ScannerRoute.NETWORK
