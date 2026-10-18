from dataclasses import dataclass
from pathlib import Path

from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_request import ScanRequest


@dataclass(frozen=True)
class ApplicationSettings:
    output_folder: Path
    output_format: OutputFormat
    scan_preset: ScanPreset
    # Last field with a default: every three-argument construction keeps working and means the quick mode.
    capture_mode: CaptureMode = CaptureMode.SINGLE

    def to_scan_request(self) -> ScanRequest:
        return ScanRequest(settings=self.scan_preset.settings, output_format=self.output_format)
