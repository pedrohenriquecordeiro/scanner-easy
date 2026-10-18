from dataclasses import dataclass

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_settings import ScanSettings


@dataclass(frozen=True)
class ScanRequest:
    settings: ScanSettings
    output_format: OutputFormat
