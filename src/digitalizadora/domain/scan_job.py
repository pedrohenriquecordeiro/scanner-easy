from dataclasses import dataclass
from datetime import datetime

from digitalizadora.domain.scan_request import ScanRequest


@dataclass(frozen=True)
class ScanJob:
    request: ScanRequest
    started_at: datetime
