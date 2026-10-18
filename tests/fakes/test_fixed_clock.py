from datetime import datetime, timedelta, timezone

from tests.fakes.fixed_clock import FixedClock

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
