from datetime import datetime, timedelta, timezone
from itertools import islice

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from tests.fakes.fixed_clock import FixedClock

TIME_ZONE = timezone(timedelta(hours=-3))
SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, 123456, tzinfo=TIME_ZONE)
LAST_NANOSECOND_OF_THE_SECOND = datetime(2026, 10, 13, 15, 30, 59, 999999, tzinfo=TIME_ZONE)


def first_name_groups(
    moment: datetime, output_format: OutputFormat, file_count: int, group_count: int
) -> list[tuple[str, ...]]:
    return list(islice(ScanFileNamingPolicy(FixedClock(moment)).name_groups(output_format, file_count), group_count))


def first_names(moment: datetime, output_format: OutputFormat, count: int) -> list[str]:
    return [group[0] for group in first_name_groups(moment, output_format, 1, count)]


def test_name_has_local_date_time_and_nine_digit_nanoseconds_with_the_pdf_extension() -> None:
    assert first_names(SCANNED_AT, OutputFormat.PDF, 1) == ["2026_10_13__15_30_12_123456000.pdf"]


def test_name_takes_the_extension_of_the_output_format() -> None:
    assert first_names(SCANNED_AT, OutputFormat.JPEG, 1) == ["2026_10_13__15_30_12_123456000.jpg"]


def test_zero_nanoseconds_are_padded_to_nine_digits() -> None:
    assert first_names(SCANNED_AT.replace(microsecond=0), OutputFormat.PDF, 1) == ["2026_10_13__15_30_12_000000000.pdf"]


def test_following_candidates_advance_one_nanosecond_each() -> None:
    assert first_names(SCANNED_AT, OutputFormat.PDF, 2)[1] == "2026_10_13__15_30_12_123456001.pdf"


def test_candidates_cross_into_the_next_second_in_order() -> None:
    names = first_names(LAST_NANOSECOND_OF_THE_SECOND, OutputFormat.PDF, 2)

    assert names == ["2026_10_13__15_30_59_999999000.pdf", "2026_10_13__15_30_59_999999001.pdf"]


def test_candidates_are_unique_and_sorted() -> None:
    names = first_names(SCANNED_AT, OutputFormat.PDF, 50)

    assert names == sorted(set(names))


def test_each_iteration_reads_the_clock_when_the_first_name_is_requested() -> None:
    clock = FixedClock(SCANNED_AT)
    names = ScanFileNamingPolicy(clock).name_groups(OutputFormat.PDF, 1)
    clock.advance(1)

    assert next(names) == ("2026_10_13__15_30_13_123456000.pdf",)


def test_two_files_share_the_timestamp_and_take_a_counter_from_one() -> None:
    assert first_name_groups(SCANNED_AT, OutputFormat.JPEG, 2, 1) == [
        ("2026_10_13__15_30_12_123456000__1.jpg", "2026_10_13__15_30_12_123456000__2.jpg")
    ]


def test_the_counter_is_a_plain_integer_and_grows_beyond_nine() -> None:
    names = first_name_groups(SCANNED_AT, OutputFormat.JPEG, 10, 1)[0]

    assert names[9] == "2026_10_13__15_30_12_123456000__10.jpg"


def test_a_single_file_has_no_counter() -> None:
    assert first_name_groups(SCANNED_AT, OutputFormat.JPEG, 1, 1) == [("2026_10_13__15_30_12_123456000.jpg",)]


def test_the_next_group_advances_the_timestamp_by_one_nanosecond_and_keeps_the_counters() -> None:
    groups = first_name_groups(SCANNED_AT, OutputFormat.PDF, 2, 2)

    assert groups[1] == ("2026_10_13__15_30_12_123456001__1.pdf", "2026_10_13__15_30_12_123456001__2.pdf")


def test_a_group_reads_the_clock_once() -> None:
    clock = FixedClock(SCANNED_AT)
    groups = ScanFileNamingPolicy(clock).name_groups(OutputFormat.JPEG, 2)
    first_group = next(groups)
    clock.advance(5)

    assert next(groups)[0] == first_group[0].replace("123456000", "123456001")
