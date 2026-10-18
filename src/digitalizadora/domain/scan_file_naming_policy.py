from collections.abc import Iterator
from datetime import datetime

from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import Clock

TIMESTAMP_FORMAT = "%Y_%m_%d__%H_%M_%S"
NANOSECONDS_PER_SECOND = 1_000_000_000
NANOSECOND_DIGITS = 9
FIRST_COUNTER = 1
SINGLE_FILE_COUNT = 1


class ScanFileNamingPolicy:
    """AAAA_MM_DD__HH_MM_SS_NNNNNNNNN for one file; the same name followed by __1, __2... for several in one write."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def name_groups(self, output_format: OutputFormat, file_count: int) -> Iterator[tuple[str, ...]]:
        """The names of all the files of one write, from one reading of the clock.

        The first group is the moment of the first read; the next ones (when a name is taken) are one nanosecond
        later each, with the same counters: unique and sorted by time."""
        first_nanoseconds = self._clock.now_in_nanoseconds()
        time_zone = self._clock.now().tzinfo
        candidate_nanoseconds = first_nanoseconds
        while True:
            base_name = self._build_base_name(candidate_nanoseconds, time_zone)
            yield self._names_of_the_files(base_name, file_count, output_format)
            candidate_nanoseconds += 1

    def _names_of_the_files(self, base_name: str, file_count: int, output_format: OutputFormat) -> tuple[str, ...]:
        extension = output_format.file_extension
        if file_count == SINGLE_FILE_COUNT:
            return (f"{base_name}.{extension}",)
        counters = range(FIRST_COUNTER, FIRST_COUNTER + file_count)
        return tuple(f"{base_name}__{counter}.{extension}" for counter in counters)

    def _build_base_name(self, epoch_nanoseconds: int, time_zone) -> str:
        seconds, nanoseconds = divmod(epoch_nanoseconds, NANOSECONDS_PER_SECOND)
        timestamp_text = datetime.fromtimestamp(seconds, tz=time_zone).strftime(TIMESTAMP_FORMAT)
        return f"{timestamp_text}_{nanoseconds:0{NANOSECOND_DIGITS}d}"
