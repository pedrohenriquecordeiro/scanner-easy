from datetime import datetime, timedelta, timezone
from pathlib import Path

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.domain.stored_scan import StoredScan

STORED_SCAN_SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
STORED_SCAN_OUTPUT_PATH = Path("/Volumes/Scans/2026-10-13_00001.pdf")
STORED_SCAN_SIZE_IN_BYTES = 1234
SAMPLE_THUMBNAIL_JPEG = b"thumbnail-bytes"


def build_stored_scan(thumbnail_jpeg: bytes = SAMPLE_THUMBNAIL_JPEG) -> StoredScan:
    result = ScanResult(
        output_path=STORED_SCAN_OUTPUT_PATH,
        output_format=OutputFormat.PDF,
        scanned_at=STORED_SCAN_SCANNED_AT,
        size_in_bytes=STORED_SCAN_SIZE_IN_BYTES,
    )
    return StoredScan(result=result, thumbnail_jpeg=thumbnail_jpeg)
