import time
from datetime import datetime


class SystemClock:
    def now(self) -> datetime:
        return datetime.now().astimezone()

    def now_in_nanoseconds(self) -> int:
        return time.time_ns()
