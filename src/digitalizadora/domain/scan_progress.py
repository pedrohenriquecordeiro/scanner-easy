from dataclasses import dataclass
from enum import Enum

from digitalizadora.domain.scan_result import ScanResult


class ScanPhase(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    SCANNING = "scanning"
    SAVING = "saving"


@dataclass(frozen=True)
class ScanProgressSnapshot:
    phase: ScanPhase
    scans_completed: int
    last_result: ScanResult | None
    last_error_code: str | None
