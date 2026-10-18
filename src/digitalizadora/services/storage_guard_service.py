import shutil
from collections.abc import Callable
from pathlib import Path

from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError
from digitalizadora.domain.imaging.image_adjustment import NO_ADJUSTMENT, RENDERED_SIZE_FACTOR, ImageAdjustment
from digitalizadora.domain.scan_quality import pixels_per_page
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_settings import ScanSettings

BYTES_PER_KIBIBYTE = 1024
MINIMUM_FREE_SPACE_BYTES = BYTES_PER_KIBIBYTE**3
ESTIMATED_BYTES_PER_PIXEL_COLOR = 0.12
ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE = 0.08
SAFETY_MARGIN_PAGES = 3

ESTIMATED_BYTES_PER_PIXEL = {
    ColorMode.COLOR: ESTIMATED_BYTES_PER_PIXEL_COLOR,
    ColorMode.GRAYSCALE: ESTIMATED_BYTES_PER_PIXEL_GRAYSCALE,
}


def estimated_page_bytes(settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT) -> int:
    unadjusted_bytes = round(pixels_per_page(settings.dots_per_inch) * ESTIMATED_BYTES_PER_PIXEL[settings.color_mode])
    if not adjustment.is_active:
        return unadjusted_bytes
    return unadjusted_bytes * RENDERED_SIZE_FACTOR


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

    def ensure_space_for_scan(
        self, folder: Path, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT
    ) -> None:
        page_bytes = estimated_page_bytes(settings, adjustment)
        self._ensure_free_space(folder, MINIMUM_FREE_SPACE_BYTES + SAFETY_MARGIN_PAGES * page_bytes)

    def ensure_space_for_file(self, folder: Path, file_size_in_bytes: int) -> None:
        self._ensure_free_space(folder, MINIMUM_FREE_SPACE_BYTES + file_size_in_bytes)

    def estimate_pages_remaining(
        self, folder: Path, settings: ScanSettings, adjustment: ImageAdjustment = NO_ADJUSTMENT
    ) -> int:
        usable_space = self._free_space_reader(folder) - MINIMUM_FREE_SPACE_BYTES
        return max(0, usable_space // estimated_page_bytes(settings, adjustment))

    def free_space_in_bytes(self, folder: Path) -> int:
        return self._free_space_reader(folder)

    def _ensure_free_space(self, folder: Path, required_space: int) -> None:
        free_space = self._free_space_reader(folder)
        if free_space < required_space:
            raise InsufficientStorageError(
                f"Only {free_space} bytes are free in {folder}; {required_space} bytes are required"
            )
