import errno
import fcntl
import os
import stat
from pathlib import Path

import pytest

from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

STALE_TEMPORARY_FILE_NAME = ".report.pdf.part"


def list_file_names(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.iterdir())


def test_write_new_file_creates_the_file_with_the_exact_bytes(tmp_path):
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"%PDF-1.4 content")

    assert destination.read_bytes() == b"%PDF-1.4 content"


def test_write_new_file_accepts_empty_content(tmp_path):
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"")

    assert destination.read_bytes() == b""


def test_write_new_file_refuses_to_overwrite_an_existing_file(tmp_path):
    destination = tmp_path / "report.pdf"
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(destination, b"replacement")


def test_refused_write_leaves_the_original_untouched(tmp_path):
    destination = tmp_path / "report.pdf"
    destination.write_bytes(b"original")

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(destination, b"replacement")

    assert destination.read_bytes() == b"original"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_write_new_file_leaves_no_temporary_file_behind(tmp_path):
    AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == ["report.pdf"]


def test_stale_temporary_file_does_not_change_the_result_of_a_new_write(tmp_path):
    stale_file = tmp_path / STALE_TEMPORARY_FILE_NAME
    stale_file.write_bytes(b"stale bytes from an interrupted write, longer than the content")
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"
    assert list_file_names(tmp_path) == [STALE_TEMPORARY_FILE_NAME, "report.pdf"]


def test_each_write_uses_its_own_hidden_temporary_file(tmp_path, monkeypatch):
    opened_names: list[str] = []
    original_open = os.open

    def recording_open(path, flags, *arguments):
        opened_names.append(Path(path).name)
        return original_open(path, flags, *arguments)

    monkeypatch.setattr(os, "open", recording_open)
    destination = tmp_path / "settings.json"

    AtomicFileWriter().replace_file(destination, b"{}")
    AtomicFileWriter().replace_file(destination, b"{}")

    temporary_names = [name for name in opened_names if name.endswith(".part")]
    assert len(set(temporary_names)) == 2
    assert all(name.startswith(".settings.json.") for name in temporary_names)


def test_writer_that_loses_a_concurrent_race_never_touches_the_winner(tmp_path, monkeypatch):
    destination = tmp_path / "report.pdf"
    original_link = os.link
    competitor_has_written: list[bool] = []

    def link_after_a_competitor_wins(source: Path, target: Path) -> None:
        if not competitor_has_written:
            competitor_has_written.append(True)
            AtomicFileWriter().write_new_file(destination, b"complete content of the competitor")
        original_link(source, target)

    monkeypatch.setattr(os, "link", link_after_a_competitor_wins)

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"complete content of the competitor"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_write_new_file_in_a_missing_folder_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        AtomicFileWriter().write_new_file(tmp_path / "missing" / "report.pdf", b"content")


def test_replace_file_creates_a_file_that_does_not_exist_yet(tmp_path):
    destination = tmp_path / "settings.json"

    AtomicFileWriter().replace_file(destination, b"{}")

    assert destination.read_bytes() == b"{}"


def test_replace_file_replaces_the_previous_content(tmp_path):
    destination = tmp_path / "settings.json"
    destination.write_bytes(b'{"old": true}')

    AtomicFileWriter().replace_file(destination, b"{}")

    assert destination.read_bytes() == b"{}"


def test_replace_file_leaves_no_temporary_file_behind(tmp_path):
    AtomicFileWriter().replace_file(tmp_path / "settings.json", b"{}")

    assert list_file_names(tmp_path) == ["settings.json"]


def describe_descriptor(descriptor: int) -> str:
    return "directory" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file"


class FullSyncRecorder:
    def __init__(self) -> None:
        self.synchronised_kinds: list[str] = []
        self._original_fcntl = fcntl.fcntl

    def __call__(self, descriptor: int, command: int) -> int:
        if command == fcntl.F_FULLFSYNC:
            self.synchronised_kinds.append(describe_descriptor(descriptor))
        return self._original_fcntl(descriptor, command)


def disable_full_sync(monkeypatch) -> list[str]:
    """Make F_FULLFSYNC fail and return the kinds of descriptors that fall back to fsync."""
    fallback_kinds: list[str] = []
    original_fsync = os.fsync

    def unsupported_full_sync(descriptor: int, command: int) -> int:
        raise OSError(errno.ENOTTY, "F_FULLFSYNC is not supported")

    def recording_fsync(descriptor: int) -> None:
        fallback_kinds.append(describe_descriptor(descriptor))
        original_fsync(descriptor)

    monkeypatch.setattr(fcntl, "fcntl", unsupported_full_sync)
    monkeypatch.setattr(os, "fsync", recording_fsync)
    return fallback_kinds


def fail_for_directories(original_function):
    def guarded_function(descriptor: int, *arguments):
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise OSError(errno.EINVAL, "directories cannot be synchronised")
        return original_function(descriptor, *arguments)

    return guarded_function


def test_file_and_then_directory_are_flushed_with_full_fsync(tmp_path, monkeypatch):
    recorder = FullSyncRecorder()
    monkeypatch.setattr(fcntl, "fcntl", recorder)

    AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert recorder.synchronised_kinds == ["file", "directory"]


def test_replace_file_also_flushes_the_file_and_the_directory(tmp_path, monkeypatch):
    recorder = FullSyncRecorder()
    monkeypatch.setattr(fcntl, "fcntl", recorder)

    AtomicFileWriter().replace_file(tmp_path / "settings.json", b"{}")

    assert recorder.synchronised_kinds == ["file", "directory"]


def test_unsupported_full_fsync_still_writes_the_file(tmp_path, monkeypatch):
    disable_full_sync(monkeypatch)
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"


def test_unsupported_full_fsync_falls_back_to_fsync_for_the_file_and_the_directory(tmp_path, monkeypatch):
    fallback_kinds = disable_full_sync(monkeypatch)

    AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert fallback_kinds == ["file", "directory"]


def test_directory_synchronisation_failure_does_not_fail_the_write(tmp_path, monkeypatch):
    monkeypatch.setattr(fcntl, "fcntl", fail_for_directories(fcntl.fcntl))
    monkeypatch.setattr(os, "fsync", fail_for_directories(os.fsync))
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"


def test_publishes_with_rename_when_the_volume_has_no_hard_links(tmp_path, monkeypatch):
    def unsupported_link(source: Path, destination: Path) -> None:
        raise OSError(errno.ENOTSUP, "hard links are not supported")

    monkeypatch.setattr(os, "link", unsupported_link)
    destination = tmp_path / "report.pdf"

    AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"content"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_rename_fallback_refuses_a_destination_that_appeared_meanwhile(tmp_path, monkeypatch):
    destination = tmp_path / "report.pdf"

    def link_that_loses_a_race(source: Path, target: Path) -> None:
        destination.write_bytes(b"created by another process")
        raise OSError(errno.ENOTSUP, "hard links are not supported")

    monkeypatch.setattr(os, "link", link_that_loses_a_race)

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(destination, b"content")

    assert destination.read_bytes() == b"created by another process"
    assert list_file_names(tmp_path) == ["report.pdf"]


def test_losing_the_link_race_raises_file_exists_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    def link_to_an_existing_destination(source: Path, destination: Path) -> None:
        raise FileExistsError(destination)

    monkeypatch.setattr(os, "link", link_to_an_existing_destination)

    with pytest.raises(FileExistsError):
        AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == []


def test_failure_while_writing_the_content_leaves_no_temporary_file(tmp_path, monkeypatch):
    def full_disk(descriptor: int) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    disable_full_sync(monkeypatch)
    monkeypatch.setattr(os, "fsync", full_disk)

    with pytest.raises(OSError, match="No space left on device"):
        AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == []


def test_failure_to_publish_leaves_no_temporary_file(tmp_path, monkeypatch):
    def unsupported_link(source: Path, destination: Path) -> None:
        raise OSError(errno.ENOTSUP, "hard links are not supported")

    def failing_rename(source: Path, destination: Path) -> None:
        raise OSError(errno.EIO, "input/output error")

    monkeypatch.setattr(os, "link", unsupported_link)
    monkeypatch.setattr(os, "rename", failing_rename)

    with pytest.raises(OSError, match="input/output error"):
        AtomicFileWriter().write_new_file(tmp_path / "report.pdf", b"content")

    assert list_file_names(tmp_path) == []
