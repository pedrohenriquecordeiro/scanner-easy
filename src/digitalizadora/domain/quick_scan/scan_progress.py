from dataclasses import dataclass
from enum import Enum

from digitalizadora.domain.quick_scan.last_scan import LastScan


class ScanPhase(str, Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    SCANNING = "scanning"
    SAVING = "saving"


@dataclass(frozen=True)
class ScanProgressSnapshot:
    phase: ScanPhase
    scans_completed: int
    last_scan: LastScan | None
    last_error_code: str | None
    # Rises when a quick scan ends and whenever an edit changes it: the page reloads the thumbnail by it.
    last_result_revision: int = 0
