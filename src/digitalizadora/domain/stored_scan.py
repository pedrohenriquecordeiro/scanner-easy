from dataclasses import dataclass

from digitalizadora.domain.scan_result import ScanResult


@dataclass(frozen=True)
class StoredScan:
    result: ScanResult
    thumbnail_jpeg: bytes
