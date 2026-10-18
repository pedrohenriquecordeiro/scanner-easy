from datetime import datetime, timedelta, timezone

import pytest

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy

SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))
OTHER_DAY = datetime(2026, 10, 14, 0, 0, 1, tzinfo=timezone(timedelta(hours=-3)))


@pytest.mark.parametrize(
    ("sequence_number", "output_format", "expected_name"),
    [
        (7, OutputFormat.PDF, "2026-10-13_00007.pdf"),
        (7, OutputFormat.JPEG, "2026-10-13_00007.jpg"),
        (1, OutputFormat.PDF, "2026-10-13_00001.pdf"),
        (99999, OutputFormat.PDF, "2026-10-13_99999.pdf"),
        (100000, OutputFormat.PDF, "2026-10-13_100000.pdf"),
    ],
)
def test_build_file_name(
    sequence_number: int, output_format: OutputFormat, expected_name: str
) -> None:
    policy = ScanFileNamingPolicy()

    assert policy.build_file_name(SCANNED_AT, sequence_number, output_format) == expected_name


@pytest.mark.parametrize(
    ("file_name", "expected_sequence_number"),
    [
        ("2026-10-13_00007.pdf", 7),
        ("2026-10-13_00007.jpg", 7),
        ("2026-10-13_00001.pdf", 1),
        ("2026-10-13_99999.jpg", 99999),
        ("2026-10-13_000007.jpg", 7),
        ("2026-10-13_100000.pdf", 100000),
    ],
)
def test_extract_sequence_number_of_a_name_from_the_same_day(
    file_name: str, expected_sequence_number: int
) -> None:
    assert ScanFileNamingPolicy().extract_sequence_number(file_name, SCANNED_AT) == (
        expected_sequence_number
    )


def test_extract_sequence_number_ignores_a_name_from_another_date() -> None:
    assert ScanFileNamingPolicy().extract_sequence_number("2026-10-13_00007.pdf", OTHER_DAY) is None


@pytest.mark.parametrize(
    "file_name",
    [
        "notes.txt",
        "",
        "2026-10-13_00007.png",
        "2026-10-13_00007.pdf.part",
        "2026-10-13_00007",
        "2026-10-13_0007.pdf",
        "2026-10-13_00000.pdf",
        "2026-10-13_abcde.pdf",
        "x2026-10-13_00007.pdf",
        "2026-10-13_00007.PDF",
        "2026-10-13_00007.JPG",
        "2026-10-13_00007.jpeg",
        "2026-10-13_00007.pdf\n",
        "2026-10-13_00007 .pdf",
    ],
)
def test_extract_sequence_number_rejects_names_outside_the_pattern(file_name: str) -> None:
    assert ScanFileNamingPolicy().extract_sequence_number(file_name, SCANNED_AT) is None
