from pathlib import Path

from digitalizadora.controllers.scan_result_body import describe_scan_result
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_result import ScanResult
from tests.fakes.stored_scans import STORED_SCAN_SCANNED_AT


def test_a_scan_result_is_described_for_the_page() -> None:
    output_path = Path("/Volumes/External/scans/2026-10-18_00001.jpg")
    result = ScanResult(output_path, OutputFormat.JPEG, STORED_SCAN_SCANNED_AT, 42)

    assert describe_scan_result(result) == {
        "file_name": "2026-10-18_00001.jpg",
        "output_folder": "/Volumes/External/scans",
        "output_format": "jpg",
        "size_in_bytes": 42,
        "scanned_at": "2026-10-13T15:30:12-03:00",
    }


def test_the_keys_come_in_the_documented_order() -> None:
    result = ScanResult(Path("/scans/a.pdf"), OutputFormat.PDF, STORED_SCAN_SCANNED_AT, 1)

    assert list(describe_scan_result(result)) == [
        "file_name",
        "output_folder",
        "output_format",
        "size_in_bytes",
        "scanned_at",
    ]
