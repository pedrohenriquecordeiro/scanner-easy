from datetime import datetime, timedelta, timezone

from tests.fakes.fixed_clock import FixedClock, TickingClock

MOMENT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=timezone(timedelta(hours=-3)))


def test_now_returns_the_given_moment_until_advanced() -> None:
    clock = FixedClock(MOMENT)

    assert clock.now() == MOMENT
    assert clock.now() == MOMENT


def test_advance_moves_time_forward_by_the_given_seconds() -> None:
    clock = FixedClock(MOMENT)

    clock.advance(90.5)

    assert clock.now() == MOMENT + timedelta(seconds=90.5)


def test_advance_accumulates() -> None:
    clock = FixedClock(MOMENT)

    clock.advance(1)
    clock.advance(2)

    assert clock.now() == MOMENT + timedelta(seconds=3)


def test_nanoseconds_reading_follows_the_moment_with_microsecond_resolution() -> None:
    clock = FixedClock(MOMENT.replace(microsecond=250000))

    assert clock.now_in_nanoseconds() % 1_000_000_000 == 250_000_000


def test_nanoseconds_reading_advances_with_the_clock() -> None:
    clock = FixedClock(MOMENT)
    before = clock.now_in_nanoseconds()

    clock.advance(2)

    assert clock.now_in_nanoseconds() - before == 2_000_000_000


def test_a_ticking_clock_reads_one_nanosecond_later_each_time() -> None:
    clock = TickingClock(MOMENT)

    first_reading = clock.now_in_nanoseconds()

    assert clock.now_in_nanoseconds() - first_reading == 1
