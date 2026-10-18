from dataclasses import dataclass

from digitalizadora.domain.imaging.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scanning.scan_settings import ScanSettings


@dataclass(frozen=True)
class ScanRequest:
    settings: ScanSettings
    output_format: OutputFormat
    # Last field with a default: every two-argument construction keeps working and means no adjustment.
    adjustment: ImageAdjustment = NO_ADJUSTMENT
