from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_settings import ScanSettings

DOCUMENT_DOTS_PER_INCH = 300
DOCUMENT_ECONOMY_DOTS_PER_INCH = 200
# Gate 0 (2026-10-17) measured 600 dots per inch in colour on the real printer: about 72 s per A4 page.
PHOTO_DOTS_PER_INCH = 600


class ScanPreset(str, Enum):
    DOCUMENT = "document"
    DOCUMENT_ECONOMY = "document_economy"
    PHOTO = "photo"

    @property
    def settings(self) -> ScanSettings:
        return SETTINGS_BY_PRESET[self]


SETTINGS_BY_PRESET: Mapping[ScanPreset, ScanSettings] = MappingProxyType(
    {
        ScanPreset.DOCUMENT: ScanSettings(DOCUMENT_DOTS_PER_INCH, ColorMode.COLOR),
        ScanPreset.DOCUMENT_ECONOMY: ScanSettings(
            DOCUMENT_ECONOMY_DOTS_PER_INCH, ColorMode.GRAYSCALE
        ),
        ScanPreset.PHOTO: ScanSettings(PHOTO_DOTS_PER_INCH, ColorMode.COLOR),
    }
)
