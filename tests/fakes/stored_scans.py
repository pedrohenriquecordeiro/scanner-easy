from datetime import datetime, timedelta, timezone
from pathlib import Path

from digitalizadora.domain.last_scan import LastScan, SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import UNFRAMED, PageFraming
from digitalizadora.domain.stored_scan import StoredScan

STORED_SCAN_SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
STORED_SCAN_OUTPUT_FOLDER = Path("/Volumes/Scans")
STORED_SCAN_FILE_NAME = "2026-10-13_00001.pdf"
STORED_SCAN_OUTPUT_PATH = STORED_SCAN_OUTPUT_FOLDER / STORED_SCAN_FILE_NAME
STORED_SCAN_SIZE_IN_BYTES = 1234
STORED_SCAN_IDENTIFIER = "9f3c1a2b4d5e6f70"
SAMPLE_THUMBNAIL_JPEG = b"thumbnail-bytes"


def build_last_scan(
    saved_files: tuple[SavedScanFile, ...] | None = None, framing: PageFraming = UNFRAMED
) -> LastScan:
    default_files = (SavedScanFile(STORED_SCAN_FILE_NAME, STORED_SCAN_SIZE_IN_BYTES, 1),)
    return LastScan(
        scan_identifier=STORED_SCAN_IDENTIFIER,
        scanned_at=STORED_SCAN_SCANNED_AT,
        output_folder=STORED_SCAN_OUTPUT_FOLDER,
        output_format=OutputFormat.PDF,
        saved_files=default_files if saved_files is None else saved_files,
        framing=framing,
    )


def build_stored_scan(thumbnail_jpeg: bytes = SAMPLE_THUMBNAIL_JPEG) -> StoredScan:
    return StoredScan(last_scan=build_last_scan(), thumbnail_jpeg=thumbnail_jpeg)
