from dataclasses import dataclass

from digitalizadora.domain.scanning.color_mode import ColorMode


@dataclass(frozen=True)
class ScanSettings:
    dots_per_inch: int
    color_mode: ColorMode
