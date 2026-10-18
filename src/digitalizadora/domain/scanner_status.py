from dataclasses import dataclass
from enum import Enum


class ScannerState(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    TESTING = "testing"
    STOPPED = "stopped"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ScannerStatus:
    state: ScannerState

    @property
    def is_ready(self) -> bool:
        return self.state is ScannerState.IDLE
