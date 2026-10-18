import shutil
from collections.abc import Callable
from pathlib import Path

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError
from digitalizadora.domain.scan_settings import ScanSettings

BYTES_PER_KIBIBYTE = 1024
MINIMUM_FREE_SPACE_BYTES = BYTES_PER_KIBIBYTE**3
PLATEN_WIDTH_INCHES = 8.5
PLATEN_HEIGHT_INCHES = 11.69
ESTIMATED_BYTES_PER_PIXEL_COLOR = 0.12
ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE = 0.08
SAFETY_MARGIN_PAGES = 3

ESTIMATED_BYTES_PER_PIXEL = {
    ColorMode.COLOR: ESTIMATED_BYTES_PER_PIXEL_COLOR,
    ColorMode.GRAYSCALE: ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE,
}


def estimated_page_bytes(settings: ScanSettings) -> int:
    pixels_wide = round(PLATEN_WIDTH_INCHES * settings.dots_per_inch)
    pixels_high = round(PLATEN_HEIGHT_INCHES * settings.dots_per_inch)
    return round(pixels_wide * pixels_high * ESTIMATED_BYTES_PER_PIXEL[settings.color_mode])


def read_free_space_in_bytes(folder: Path) -> int:
    try:
        if not folder.is_dir():
            raise OutputFolderUnavailableError(f"The output folder {folder} does not exist or is not a folder")
        return shutil.disk_usage(folder).free
    except OSError as error:
        raise OutputFolderUnavailableError(f"Cannot read the free space of {folder}: {error}") from error


class StorageGuardService:
    def __init__(self, free_space_reader: Callable[[Path], int] = read_free_space_in_bytes) -> None:
        self._free_space_reader = free_space_reader

    def ensure_space_for_scan(self, folder: Path, settings: ScanSettings) -> None:
        free_space = self._free_space_reader(folder)
        required_space = MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * estimated_page_bytes(settings)
        if free_space < required_space:
            raise InsufficientStorageError(
                f"Only {free_space} bytes are free in {folder}; {required_space} bytes are required"
            )

    def estimate_pages_remaining(self, folder: Path, settings: ScanSettings) -> int:
        usable_space = self._free_space_reader(folder) - MINIMUM_FREE_SPACE_BYTES
        return max(0, usable_space // estimated_page_bytes(settings))

    def free_space_in_bytes(self, folder: Path) -> int:
        return self._free_space_reader(folder)
