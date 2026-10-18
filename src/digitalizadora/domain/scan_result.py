from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from digitalizadora.domain.output_format import OutputFormat


@dataclass(frozen=True)
class ScanResult:
    output_path: Path
    output_format: OutputFormat
    scanned_at: datetime
    size_in_bytes: int
