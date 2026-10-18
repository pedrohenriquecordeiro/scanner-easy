from dataclasses import dataclass
from pathlib import Path

from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_request import ScanRequest
from digitalizadora.domain.scan_settings import ScanSettings


@dataclass(frozen=True)
class ApplicationSettings:
    output_folder: Path
    output_format: OutputFormat
    scan_settings: ScanSettings
    # Last fields with a default: every three-argument construction keeps working and means the quick mode.
    capture_mode: CaptureMode = CaptureMode.SINGLE
    adjustment: ImageAdjustment = NO_ADJUSTMENT

    def to_scan_request(self) -> ScanRequest:
        return ScanRequest(settings=self.scan_settings, output_format=self.output_format, adjustment=self.adjustment)
