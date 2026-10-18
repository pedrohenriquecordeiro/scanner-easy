from datetime import datetime, timedelta, timezone
from itertools import islice

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from tests.fakes.fixed_clock import FixedClock

TIME_ZONE = timezone(timedelta(hours=-3))
SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, 123456, tzinfo=TIME_ZONE)
LAST_NANOSECOND_OF_THE_SECOND = datetime(2026, 10, 13, 15, 30, 59, 999999, tzinfo=TIME_ZONE)


def first_names(moment: datetime, output_format: OutputFormat, count: int) -> list[str]:
    return list(islice(ScanFileNamingPolicy(FixedClock(moment)).file_names(output_format), count))


def test_name_has_local_date_time_and_nine_digit_nanoseconds_with_the_pdf_extension() -> None:
    assert first_names(SCANNED_AT, OutputFormat.PDF, 1) == ["2026-10-13_15-30-12-123456000.pdf"]


def test_name_takes_the_extension_of_the_output_format() -> None:
    assert first_names(SCANNED_AT, OutputFormat.JPEG, 1) == ["2026-10-13_15-30-12-123456000.jpg"]


def test_zero_nanoseconds_are_padded_to_nine_digits() -> None:
    assert first_names(SCANNED_AT.replace(microsecond=0), OutputFormat.PDF, 1) == ["2026-10-13_15-30-12-000000000.pdf"]


def test_following_candidates_advance_one_nanosecond_each() -> None:
    assert first_names(SCANNED_AT, OutputFormat.PDF, 2)[1] == "2026-10-13_15-30-12-123456001.pdf"


def test_candidates_cross_into_the_next_second_in_order() -> None:
    names = first_names(LAST_NANOSECOND_OF_THE_SECOND, OutputFormat.PDF, 2)

    assert names == ["2026-10-13_15-30-59-999999000.pdf", "2026-10-13_15-30-59-999999001.pdf"]


def test_candidates_are_unique_and_sorted() -> None:
    names = first_names(SCANNED_AT, OutputFormat.PDF, 50)

    assert names == sorted(set(names))


def test_each_iteration_reads_the_clock_when_the_first_name_is_requested() -> None:
    clock = FixedClock(SCANNED_AT)
    names = ScanFileNamingPolicy(clock).file_names(OutputFormat.PDF)
    clock.advance(1)

    assert next(names) == "2026-10-13_15-30-13-123456000.pdf"
