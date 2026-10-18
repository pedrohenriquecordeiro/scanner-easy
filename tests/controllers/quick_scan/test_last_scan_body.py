from dataclasses import replace
from pathlib import Path

from digitalizadora.controllers.quick_scan.last_scan_body import describe_last_scan
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from digitalizadora.domain.quick_scan.last_scan import SavedScanFile
from tests.fakes.page_crops import quadrilateral
from tests.fakes.stored_scans import build_last_scan

FIRST_FILE = SavedScanFile("2026_10_18__16_14_03_000000000__1.jpg", 42, 1)
SECOND_FILE = SavedScanFile("2026_10_18__16_14_03_000000000__2.jpg", 100, 2)
TILTED_CROP = quadrilateral((0.039, 0.28), (0.65, 0.019), (0.894, 0.321), (0.282, 0.582))


def test_a_last_scan_is_described_for_the_page() -> None:
    last_scan = replace(
        build_last_scan((FIRST_FILE,)), output_folder=Path("/Volumes/External/scans"), output_format=OutputFormat.JPEG
    )

    assert describe_last_scan(last_scan) == {
        "scan_identifier": "9f3c1a2b4d5e6f70",
        "file_names": ["2026_10_18__16_14_03_000000000__1.jpg"],
        "output_folder": "/Volumes/External/scans",
        "output_format": "jpg",
        "total_size_in_bytes": 42,
        "scanned_at": "2026-10-13T15:30:12-03:00",
        "rotation_degrees": 0,
        "crops": [],
        "is_editable": True,
    }


def test_the_keys_come_in_the_documented_order() -> None:
    assert list(describe_last_scan(build_last_scan())) == [
        "scan_identifier",
        "file_names",
        "output_folder",
        "output_format",
        "total_size_in_bytes",
        "scanned_at",
        "rotation_degrees",
        "crops",
        "is_editable",
    ]


def test_two_files_are_listed_in_order_and_their_sizes_add_up() -> None:
    body = describe_last_scan(build_last_scan((FIRST_FILE, SECOND_FILE)))

    expected_names = ["2026_10_18__16_14_03_000000000__1.jpg", "2026_10_18__16_14_03_000000000__2.jpg"]
    assert (body["file_names"], body["total_size_in_bytes"]) == (expected_names, 142)


def test_the_rotation_and_the_crops_of_the_framing_are_described() -> None:
    framing = PageFraming(PageRotation.CLOCKWISE_90, (TILTED_CROP,))

    body = describe_last_scan(build_last_scan(framing=framing))

    assert body["rotation_degrees"] == 90
    assert body["crops"] == [
        {
            "top_left": {"x": 0.039, "y": 0.28},
            "top_right": {"x": 0.65, "y": 0.019},
            "bottom_right": {"x": 0.894, "y": 0.321},
            "bottom_left": {"x": 0.282, "y": 0.582},
        }
    ]


def test_a_scan_without_a_master_says_it_cannot_be_edited() -> None:
    body = describe_last_scan(replace(build_last_scan(), is_editable=False))

    assert body["is_editable"] is False
