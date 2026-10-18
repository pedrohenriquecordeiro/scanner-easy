import errno
import os
from pathlib import Path

import pytest

from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError
from digitalizadora.repositories.output_folder_preparer import WRITE_PROBE_FILE_PREFIX, prepare_output_folder

READ_ONLY_FOLDER_MODE = 0o500
WRITABLE_FOLDER_MODE = 0o700


def test_creates_missing_parent_folders(tmp_path: Path) -> None:
    folder = tmp_path / "external" / "scans"

    prepare_output_folder(folder)

    assert folder.is_dir()


def test_accepts_an_existing_folder(tmp_path: Path) -> None:
    prepare_output_folder(tmp_path)

    assert tmp_path.is_dir()


def test_leaves_no_probe_file_behind(tmp_path: Path) -> None:
    prepare_output_folder(tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_keeps_existing_files(tmp_path: Path) -> None:
    existing_file = tmp_path / "2026-10-13_00001.pdf"
    existing_file.write_bytes(b"pdf")

    prepare_output_folder(tmp_path)

    assert existing_file.read_bytes() == b"pdf"


def test_rejects_a_regular_file(tmp_path: Path) -> None:
    regular_file = tmp_path / "scans"
    regular_file.write_bytes(b"x")

    with pytest.raises(OutputFolderUnavailableError):
        prepare_output_folder(regular_file)


def test_rejects_a_path_below_a_regular_file(tmp_path: Path) -> None:
    blocking_file = tmp_path / "not-a-folder"
    blocking_file.write_bytes(b"x")

    with pytest.raises(OutputFolderUnavailableError):
        prepare_output_folder(blocking_file / "scans")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permission bits")
def test_rejects_a_read_only_folder(tmp_path: Path) -> None:
    folder = tmp_path / "scans"
    folder.mkdir()
    folder.chmod(READ_ONLY_FOLDER_MODE)
    try:
        with pytest.raises(OutputFolderUnavailableError):
            prepare_output_folder(folder)
    finally:
        folder.chmod(WRITABLE_FOLDER_MODE)


def test_turns_permission_error_into_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_mkdir(self: Path, *arguments: object, **options: object) -> None:
        raise PermissionError("read-only volume")

    monkeypatch.setattr(Path, "mkdir", deny_mkdir)

    with pytest.raises(OutputFolderUnavailableError):
        prepare_output_folder(tmp_path / "scans")


def test_rejects_a_folder_that_cannot_be_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_write(self: Path, content: bytes) -> int:
        raise PermissionError("read-only volume")

    monkeypatch.setattr(Path, "write_bytes", deny_write)

    with pytest.raises(OutputFolderUnavailableError):
        prepare_output_folder(tmp_path)


def test_probe_file_is_hidden() -> None:
    assert WRITE_PROBE_FILE_PREFIX.startswith(".")


def test_each_preparation_uses_its_own_probe_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    probe_names: list[str] = []
    original_write_bytes = Path.write_bytes

    def recording_write_bytes(self: Path, content: bytes) -> int:
        probe_names.append(self.name)
        return original_write_bytes(self, content)

    monkeypatch.setattr(Path, "write_bytes", recording_write_bytes)

    prepare_output_folder(tmp_path)
    prepare_output_folder(tmp_path)

    assert len(set(probe_names)) == 2
    assert all(name.startswith(WRITE_PROBE_FILE_PREFIX) for name in probe_names)


@pytest.mark.parametrize("error_number", [errno.ENOSPC, errno.EDQUOT])
def test_full_disk_while_writing_the_probe_raises_insufficient_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_number: int
) -> None:
    def full_disk_write(self: Path, content: bytes) -> int:
        raise OSError(error_number, os.strerror(error_number))

    monkeypatch.setattr(Path, "write_bytes", full_disk_write)

    with pytest.raises(InsufficientStorageError):
        prepare_output_folder(tmp_path)
