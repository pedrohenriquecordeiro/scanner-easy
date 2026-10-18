from collections.abc import Callable, Mapping
from pathlib import Path
from typing import BinaryIO

from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter


class ScriptedFileWriter(AtomicFileWriter):
    """Writes for real, but the first write of each configured file name raises the configured error.

    written_file_names lists, in order, the names of the writes that succeeded (write_new_file,
    write_new_file_from and replace_file); a scripted failure writes nothing and is not listed.
    """

    def __init__(self, failures_by_file_name: Mapping[str, OSError]) -> None:
        self._pending_failures = dict(failures_by_file_name)
        self.written_file_names: list[str] = []

    def write_new_file_from(self, destination: Path, write_content: Callable[[BinaryIO], None]) -> int:
        self._fail_once_when_scripted(destination)
        written_size = super().write_new_file_from(destination, write_content)
        self.written_file_names.append(destination.name)
        return written_size

    def replace_file(self, destination: Path, content: bytes) -> None:
        self._fail_once_when_scripted(destination)
        super().replace_file(destination, content)
        self.written_file_names.append(destination.name)

    def _fail_once_when_scripted(self, destination: Path) -> None:
        failure = self._pending_failures.pop(destination.name, None)
        if failure is not None:
            raise failure
