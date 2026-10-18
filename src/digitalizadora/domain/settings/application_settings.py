from dataclasses import dataclass
from pathlib import Path

from digitalizadora.domain.imaging.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output.output_format import OutputFormat
from digitalizadora.domain.scanning.scan_request import ScanRequest
from digitalizadora.domain.scanning.scan_settings import ScanSettings
from digitalizadora.domain.settings.capture_mode import CaptureMode


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
