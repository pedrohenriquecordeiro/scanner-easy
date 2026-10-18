from datetime import datetime, timedelta


class FixedClock:
    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment

    def advance(self, seconds: float) -> None:
        self._moment = self._moment + timedelta(seconds=seconds)
