from datetime import datetime, timedelta, timezone
from pathlib import Path

from digitalizadora.domain.last_scan import LastScan, SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.page_framing import PageFraming
from digitalizadora.domain.page_rotation import PageRotation
from tests.fakes.page_crops import rectangle

MOMENT = datetime(2026, 10, 18, 12, 41, 3, tzinfo=timezone(timedelta(hours=-3)))
FIRST_FILE = SavedScanFile("2026-10-18_00007.pdf", 1000, 1)
SECOND_FILE = SavedScanFile("2026-10-18_00008.pdf", 234, 2)
LAST_SCAN = LastScan(
    scan_identifier="9f3c1a2b4d5e6f70",
    scanned_at=MOMENT,
    output_folder=Path("/Users/pedro/Pictures/Digitalizadora"),
    output_format=OutputFormat.PDF,
    saved_files=(FIRST_FILE, SECOND_FILE),
)


def test_the_total_size_adds_up_the_files():
    assert LAST_SCAN.total_size_in_bytes == 1234


def test_a_saved_file_lives_in_the_output_folder():
    assert LAST_SCAN.saved_file_path(SECOND_FILE) == Path("/Users/pedro/Pictures/Digitalizadora/2026-10-18_00008.pdf")


def test_a_new_scan_is_unframed_and_editable():
    assert (LAST_SCAN.framing, LAST_SCAN.is_editable) == (PageFraming(), True)


def test_with_framing_replaces_only_the_framing():
    framing = PageFraming(PageRotation.CLOCKWISE_90).with_crops([rectangle((0.1, 0.1, 0.5, 0.5))])

    framed = LAST_SCAN.with_framing(framing)

    assert (framed.framing, framed.saved_files, framed.scan_identifier) == (
        framing,
        LAST_SCAN.saved_files,
        LAST_SCAN.scan_identifier,
    )


def test_with_saved_files_replaces_only_the_files():
    replaced = LAST_SCAN.with_saved_files([SECOND_FILE])

    assert (replaced.saved_files, replaced.framing) == ((SECOND_FILE,), LAST_SCAN.framing)


def test_with_saved_files_takes_any_sequence():
    assert isinstance(LAST_SCAN.with_saved_files([FIRST_FILE]).saved_files, tuple)
