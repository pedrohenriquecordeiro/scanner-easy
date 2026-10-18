from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.imaging.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.output_format import OutputFormat


@dataclass(frozen=True)
class SavedScanFile:
    file_name: str
    size_in_bytes: int
    # What the application saw right after writing the file.
    modified_at_nanoseconds: int


@dataclass(frozen=True)
class LastScan:
    """The last quick scan: its files in the output folder and the framing the files were made with.

    There is one file per frame, in the reading order of the frames, or a single file when there is no frame."""

    scan_identifier: str
    scanned_at: datetime
    output_folder: Path
    output_format: OutputFormat
    saved_files: tuple[SavedScanFile, ...]
    framing: PageFraming = UNFRAMED
    # False when the master of the scanner could not be kept: the files were saved, but cannot be adjusted.
    is_editable: bool = True

    @property
    def total_size_in_bytes(self) -> int:
        return sum(saved_file.size_in_bytes for saved_file in self.saved_files)

    def saved_file_path(self, saved_file: SavedScanFile) -> Path:
        return self.output_folder / saved_file.file_name

    def with_framing(self, framing: PageFraming) -> "LastScan":
        return replace(self, framing=framing)

    def with_saved_files(self, saved_files: Sequence[SavedScanFile]) -> "LastScan":
        return replace(self, saved_files=tuple(saved_files))


@dataclass(frozen=True)
class QuickScanSlot:
    """What the slot of the last quick scan keeps next to its master: the density and the colour of the scan."""

    last_scan: LastScan
    dots_per_inch: int
    color_mode: ColorMode
    # A re-render started and has not been confirmed: the start-up finishes it from the master.
    render_pending: bool = False


@dataclass(frozen=True)
class QuickScanMasterFiles:
    scan_identifier: str
    master_jpeg: bytes
    thumbnail_jpeg: bytes
