from datetime import UTC, datetime, timedelta

from digitalizadora.infrastructure.system_clock import SystemClock

MAXIMUM_CLOCK_DIFFERENCE = timedelta(seconds=5)


def test_now_is_timezone_aware() -> None:
    assert SystemClock().now().utcoffset() is not None


def test_now_is_the_current_moment() -> None:
    difference = abs(SystemClock().now() - datetime.now(UTC))

    assert difference < MAXIMUM_CLOCK_DIFFERENCE
