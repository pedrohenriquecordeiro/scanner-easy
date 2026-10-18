from collections.abc import Iterator
from datetime import datetime

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import Clock

TIMESTAMP_FORMAT = "%Y_%m_%d__%H_%M_%S"
NANOSECONDS_PER_SECOND = 1_000_000_000
NANOSECOND_DIGITS = 9


class ScanFileNamingPolicy:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def file_names(self, output_format: OutputFormat) -> Iterator[str]:
        """The name of the moment of the first read, then one nanosecond later each: unique and sorted by time."""
        first_nanoseconds = self._clock.now_in_nanoseconds()
        time_zone = self._clock.now().tzinfo
        candidate_nanoseconds = first_nanoseconds
        while True:
            yield self._build_file_name(candidate_nanoseconds, time_zone, output_format)
            candidate_nanoseconds += 1

    def _build_file_name(self, epoch_nanoseconds: int, time_zone, output_format: OutputFormat) -> str:
        seconds, nanoseconds = divmod(epoch_nanoseconds, NANOSECONDS_PER_SECOND)
        timestamp_text = datetime.fromtimestamp(seconds, tz=time_zone).strftime(TIMESTAMP_FORMAT)
        return f"{timestamp_text}_{nanoseconds:0{NANOSECOND_DIGITS}d}.{output_format.file_extension}"
