from datetime import UTC, datetime, timedelta

from digitalizadora.infrastructure.system_clock import SystemClock

MAXIMUM_CLOCK_DIFFERENCE = timedelta(seconds=5)
NANOSECONDS_PER_SECOND = 1_000_000_000


def test_now_is_timezone_aware() -> None:
    assert SystemClock().now().utcoffset() is not None


def test_now_is_the_current_moment() -> None:
    difference = abs(SystemClock().now() - datetime.now(UTC))

    assert difference < MAXIMUM_CLOCK_DIFFERENCE


def test_nanoseconds_reading_is_the_current_moment_since_the_epoch() -> None:
    seconds = SystemClock().now_in_nanoseconds() / NANOSECONDS_PER_SECOND

    assert abs(seconds - datetime.now(UTC).timestamp()) < MAXIMUM_CLOCK_DIFFERENCE.total_seconds()


def test_nanoseconds_reading_never_goes_backwards_between_two_calls() -> None:
    clock = SystemClock()

    assert clock.now_in_nanoseconds() <= clock.now_in_nanoseconds()
