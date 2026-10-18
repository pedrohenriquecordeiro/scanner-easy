import errno
import os
import secrets
from pathlib import Path

from digitalizadora.domain.errors import DigitalizadoraError, InsufficientStorageError, OutputFolderUnavailableError

WRITE_PROBE_FILE_PREFIX = ".digitalizadora-write-probe-"
PROBE_TOKEN_SIZE_IN_BYTES = 4
FULL_STORAGE_ERROR_NUMBERS = frozenset({errno.ENOSPC, errno.EDQUOT})


def translate_storage_error(error: OSError, description: str) -> DigitalizadoraError:
    if error.errno in FULL_STORAGE_ERROR_NUMBERS:
        return InsufficientStorageError(f"{description}: the disk is full ({error})")
    return OutputFolderUnavailableError(f"{description}: {error}")


def prepare_output_folder(folder: Path) -> None:
    """Create the folder when missing and prove that a file can be written in it."""
    unique_part = f"{os.getpid()}-{secrets.token_hex(PROBE_TOKEN_SIZE_IN_BYTES)}"
    probe_file = folder / f"{WRITE_PROBE_FILE_PREFIX}{unique_part}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        probe_file.write_bytes(b"")
        probe_file.unlink()
    except OSError as error:
        raise translate_storage_error(error, f"Cannot write to {folder}") from error
