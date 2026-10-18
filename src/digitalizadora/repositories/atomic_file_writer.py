import fcntl
import functools
import logging
import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

LOGGER = logging.getLogger(__name__)

TEMPORARY_FILE_PREFIX = "."
TEMPORARY_FILE_SUFFIX = ".part"
TEMPORARY_FILE_PERMISSIONS = 0o644
TEMPORARY_TOKEN_SIZE_IN_BYTES = 4


def temporary_path_for(destination: Path) -> Path:
    """Unique per write, so two writers racing for one name never share or delete each other's file."""
    unique_part = f"{os.getpid()}-{secrets.token_hex(TEMPORARY_TOKEN_SIZE_IN_BYTES)}"
    return destination.with_name(f"{TEMPORARY_FILE_PREFIX}{destination.name}.{unique_part}{TEMPORARY_FILE_SUFFIX}")


def remove_temporary_file(temporary: Path) -> None:
    try:
        temporary.unlink(missing_ok=True)
    except OSError:
        LOGGER.warning("Could not remove the temporary file %s", temporary)


def flush_to_disk(descriptor: int) -> None:
    """Ask the drive to empty its own cache; plain fsync on macOS only reaches the drive's buffer."""
    try:
        fcntl.fcntl(descriptor, fcntl.F_FULLFSYNC)
    except OSError:
        os.fsync(descriptor)


def write_bytes(content: bytes, stream: BinaryIO) -> None:
    stream.write(content)


class AtomicFileWriter:
    def write_new_file(self, destination: Path, content: bytes) -> None:
        self.write_new_file_from(destination, functools.partial(write_bytes, content))

    def write_new_file_from(self, destination: Path, write_content: Callable[[BinaryIO], None]) -> int:
        """Streams the content into a hidden temporary file and publishes it without overwriting.

        Returns the written size. An exception of the callback removes the temporary file and reaches
        the caller unchanged.
        """
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite {destination}")
        temporary = temporary_path_for(destination)
        try:
            written_size = self._write_temporary_file(temporary, write_content)
            self._publish_without_overwriting(temporary, destination)
        finally:
            remove_temporary_file(temporary)
        self._synchronise_directory(destination.parent)
        return written_size

    def replace_file(self, destination: Path, content: bytes) -> None:
        temporary = temporary_path_for(destination)
        try:
            self._write_temporary_file(temporary, functools.partial(write_bytes, content))
            os.replace(temporary, destination)
        finally:
            remove_temporary_file(temporary)
        self._synchronise_directory(destination.parent)

    def _write_temporary_file(self, temporary: Path, write_content: Callable[[BinaryIO], None]) -> int:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(temporary, flags, TEMPORARY_FILE_PERMISSIONS)
        with os.fdopen(descriptor, "wb") as stream:
            write_content(stream)
            written_size = stream.tell()
            stream.flush()
            flush_to_disk(stream.fileno())
        return written_size

    def _publish_without_overwriting(self, temporary: Path, destination: Path) -> None:
        try:
            os.link(temporary, destination)
        except FileExistsError:
            raise
        except OSError:
            # Volumes such as exFAT do not support hard links, so fall back to rename after checking again.
            if destination.exists():
                raise FileExistsError(f"Refusing to overwrite {destination}") from None
            os.rename(temporary, destination)

    def _synchronise_directory(self, directory: Path) -> None:
        try:
            descriptor = os.open(directory, os.O_RDONLY)
            try:
                flush_to_disk(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            LOGGER.warning("Could not synchronise the directory %s", directory)
