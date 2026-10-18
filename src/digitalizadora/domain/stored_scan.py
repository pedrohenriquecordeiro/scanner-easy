from dataclasses import dataclass

from digitalizadora.domain.last_scan import LastScan


@dataclass(frozen=True)
class StoredScan:
    last_scan: LastScan
    thumbnail_jpeg: bytes
