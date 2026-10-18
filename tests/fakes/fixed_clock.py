from datetime import datetime, timedelta

NANOSECONDS_PER_MICROSECOND = 1000
NANOSECONDS_PER_SECOND = 1_000_000_000


class FixedClock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def now_in_nanoseconds(self) -> int:
        whole_seconds = int(self._moment.replace(microsecond=0).timestamp())
        return whole_seconds * NANOSECONDS_PER_SECOND + self._moment.microsecond * NANOSECONDS_PER_MICROSECOND

    def advance(self, seconds: float) -> None:
        self._moment = self._moment + timedelta(seconds=seconds)


class TickingClock(FixedClock):
    """A clock whose every reading in nanoseconds is one nanosecond later than the one before, as two writes are."""

    def __init__(self, moment: datetime) -> None:
        super().__init__(moment)
        self._readings = 0

    def now_in_nanoseconds(self) -> int:
        reading = super().now_in_nanoseconds() + self._readings
        self._readings += 1
        return reading
