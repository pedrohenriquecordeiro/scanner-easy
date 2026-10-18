import errno
from typing import BinaryIO

import pytest

from tests.fakes.scripted_file_writer import ScriptedFileWriter

FULL_DISK_ERROR = OSError(errno.ENOSPC, "No space left on device")


def write_streamed_content(stream: BinaryIO) -> None:
    stream.write(b"streamed")


def test_write_new_file_writes_for_real(tmp_path):
    ScriptedFileWriter({}).write_new_file(tmp_path / "page.jpg", b"jpeg")

    assert (tmp_path / "page.jpg").read_bytes() == b"jpeg"


def test_write_new_file_is_recorded_once(tmp_path):
    file_writer = ScriptedFileWriter({})

    file_writer.write_new_file(tmp_path / "page.jpg", b"jpeg")

    assert file_writer.written_file_names == ["page.jpg"]


def test_write_new_file_from_is_recorded_and_returns_the_size(tmp_path):
    file_writer = ScriptedFileWriter({})

    written_size = file_writer.write_new_file_from(tmp_path / "document.pdf", write_streamed_content)

    assert (file_writer.written_file_names, written_size) == (["document.pdf"], len(b"streamed"))


def test_replace_file_is_recorded(tmp_path):
    file_writer = ScriptedFileWriter({})

    file_writer.replace_file(tmp_path / "manifest.json", b"{}")

    assert file_writer.written_file_names == ["manifest.json"]


def test_configured_name_fails_with_the_configured_error(tmp_path):
    file_writer = ScriptedFileWriter({"manifest.json": FULL_DISK_ERROR})

    with pytest.raises(OSError) as raised:
        file_writer.replace_file(tmp_path / "manifest.json", b"{}")

    assert raised.value is FULL_DISK_ERROR


def test_failed_write_creates_nothing_and_is_not_recorded(tmp_path):
    file_writer = ScriptedFileWriter({"page.jpg": FULL_DISK_ERROR})

    with pytest.raises(OSError):
        file_writer.write_new_file(tmp_path / "page.jpg", b"jpeg")

    assert (sorted(tmp_path.iterdir()), file_writer.written_file_names) == ([], [])


def test_configured_name_fails_only_once(tmp_path):
    file_writer = ScriptedFileWriter({"manifest.json": FULL_DISK_ERROR})
    with pytest.raises(OSError):
        file_writer.replace_file(tmp_path / "manifest.json", b"{}")

    file_writer.replace_file(tmp_path / "manifest.json", b"{}")

    assert file_writer.written_file_names == ["manifest.json"]


def test_other_names_are_written_normally(tmp_path):
    file_writer = ScriptedFileWriter({"thumbnail.jpg": FULL_DISK_ERROR})

    file_writer.write_new_file(tmp_path / "page.jpg", b"jpeg")

    assert file_writer.written_file_names == ["page.jpg"]
