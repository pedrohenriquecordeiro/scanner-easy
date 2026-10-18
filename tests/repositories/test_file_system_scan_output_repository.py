import errno
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_scan_output_repository import (
    MAXIMUM_NAME_ATTEMPTS,
    FileSystemScanOutputRepository,
)
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository

TIME_ZONE = timezone(timedelta(hours=-3))
SCANNED_AT = datetime(2026, 10, 13, 15, 30, 12, tzinfo=TIME_ZONE)
NEXT_DAY = datetime(2026, 10, 14, 9, 0, 0, tzinfo=TIME_ZONE)
READ_ONLY_FOLDER_MODE = 0o500
WRITABLE_FOLDER_MODE = 0o700


def build_encoded_scan(
    output_format: OutputFormat = OutputFormat.PDF, created_at: datetime = SCANNED_AT
) -> EncodedScan:
    return EncodedScan(
        content=b"scan content",
        output_format=output_format,
        created_at=created_at,
        thumbnail_jpeg=b"thumbnail",
    )


def build_settings(output_folder: Path) -> ApplicationSettings:
    return ApplicationSettings(output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT)


def build_repository(output_folder: Path, file_writer) -> FileSystemScanOutputRepository:
    return FileSystemScanOutputRepository(
        InMemoryApplicationSettingsRepository(build_settings(output_folder)), ScanFileNamingPolicy(), file_writer
    )


def build_real_repository(output_folder: Path) -> FileSystemScanOutputRepository:
    return build_repository(output_folder, AtomicFileWriter())


def test_output_folder_comes_from_the_settings(tmp_path):
    assert build_real_repository(tmp_path / "scans").output_folder() == tmp_path / "scans"


def test_first_file_of_the_day_ends_with_sequence_one(tmp_path):
    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path == tmp_path / "2026-10-13_00001.pdf"


def test_saved_file_holds_the_encoded_content(tmp_path):
    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.read_bytes() == b"scan content"


def test_next_file_of_the_day_ends_with_sequence_two(tmp_path):
    repository = build_real_repository(tmp_path)
    repository.save(build_encoded_scan())

    second_path = repository.save(build_encoded_scan())

    assert second_path.name == "2026-10-13_00002.pdf"


def test_sequence_continues_after_the_highest_existing_number_when_there_are_gaps(tmp_path):
    (tmp_path / "2026-10-13_00003.pdf").write_bytes(b"x")
    (tmp_path / "2026-10-13_00007.jpg").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00008.pdf"


def test_files_of_other_dates_do_not_interfere(tmp_path):
    (tmp_path / "2026-10-12_00009.pdf").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00001.pdf"


def test_each_date_has_its_own_counter(tmp_path):
    repository = build_real_repository(tmp_path)
    repository.save(build_encoded_scan(created_at=SCANNED_AT))

    next_day_path = repository.save(build_encoded_scan(created_at=NEXT_DAY))

    assert next_day_path.name == "2026-10-14_00001.pdf"


def test_files_with_other_extensions_do_not_interfere(tmp_path):
    (tmp_path / "2026-10-13_00009.png").write_bytes(b"x")
    (tmp_path / "2026-10-13_00009.txt").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00001.pdf"


def test_pdf_and_jpeg_of_the_same_date_share_the_counter(tmp_path):
    (tmp_path / "2026-10-13_00004.jpg").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan(OutputFormat.PDF))

    assert saved_path.name == "2026-10-13_00005.pdf"


def test_jpeg_uses_the_jpg_extension_and_the_shared_counter(tmp_path):
    (tmp_path / "2026-10-13_00004.pdf").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan(OutputFormat.JPEG))

    assert saved_path.name == "2026-10-13_00005.jpg"


def test_unrelated_files_and_leftover_temporary_files_are_ignored(tmp_path):
    for name in ("notes.txt", "2026-10-13_abc.pdf", ".2026-10-13_00009.pdf.4242-0a1b2c3d.part"):
        (tmp_path / name).write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00001.pdf"


def test_missing_output_folder_is_created(tmp_path):
    output_folder = tmp_path / "external disk" / "scans"

    saved_path = build_real_repository(output_folder).save(build_encoded_scan())

    assert saved_path.parent == output_folder
    assert saved_path.exists()


class FileWriterThatSucceedsOnAttempt:
    def __init__(self, successful_attempt: int) -> None:
        self._successful_attempt = successful_attempt
        self.attempted_destinations: list[Path] = []

    def write_new_file(self, destination: Path, content: bytes) -> None:
        self.attempted_destinations.append(destination)
        if len(self.attempted_destinations) < self._successful_attempt:
            raise FileExistsError(destination)


class FailingFileWriter:
    def __init__(self, error_number: int) -> None:
        self._error_number = error_number

    def write_new_file(self, destination: Path, content: bytes) -> None:
        raise OSError(self._error_number, os.strerror(self._error_number))


class RacingFileWriter:
    """Lets another 'process' take the first chosen name right before the real write."""

    def __init__(self, real_writer: AtomicFileWriter) -> None:
        self._real_writer = real_writer
        self._race_already_happened = False

    def write_new_file(self, destination: Path, content: bytes) -> None:
        if not self._race_already_happened:
            self._race_already_happened = True
            self._real_writer.write_new_file(destination, b"written by another process")
        self._real_writer.write_new_file(destination, content)


def test_output_folder_that_is_a_file_raises_output_folder_unavailable(tmp_path):
    blocking_file = tmp_path / "scans"
    blocking_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(blocking_file).save(build_encoded_scan())


def test_output_folder_below_a_file_raises_output_folder_unavailable(tmp_path):
    blocking_file = tmp_path / "scans"
    blocking_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(blocking_file / "nested").save(build_encoded_scan())


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permission bits")
def test_read_only_output_folder_raises_output_folder_unavailable(tmp_path):
    output_folder = tmp_path / "scans"
    output_folder.mkdir()
    output_folder.chmod(READ_ONLY_FOLDER_MODE)
    try:
        with pytest.raises(OutputFolderUnavailableError):
            build_real_repository(output_folder).save(build_encoded_scan())
    finally:
        output_folder.chmod(WRITABLE_FOLDER_MODE)


@pytest.mark.parametrize("error_number", [errno.ENOSPC, errno.EDQUOT])
def test_full_disk_while_writing_raises_insufficient_storage(tmp_path, error_number):
    repository = build_repository(tmp_path, FailingFileWriter(error_number))

    with pytest.raises(InsufficientStorageError):
        repository.save(build_encoded_scan())


def test_full_disk_while_creating_the_folder_raises_insufficient_storage(tmp_path, monkeypatch):
    def full_disk_mkdir(self: Path, *arguments: object, **options: object) -> None:
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

    monkeypatch.setattr(Path, "mkdir", full_disk_mkdir)

    with pytest.raises(InsufficientStorageError):
        build_real_repository(tmp_path / "scans").save(build_encoded_scan())


def test_input_output_error_while_writing_raises_output_folder_unavailable(tmp_path):
    repository = build_repository(tmp_path, FailingFileWriter(errno.EIO))

    with pytest.raises(OutputFolderUnavailableError):
        repository.save(build_encoded_scan())


def test_name_taken_by_another_process_moves_to_the_following_number(tmp_path):
    repository = build_repository(tmp_path, RacingFileWriter(AtomicFileWriter()))

    saved_path = repository.save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_00002.pdf"
    assert (tmp_path / "2026-10-13_00001.pdf").read_bytes() == b"written by another process"


def test_last_allowed_attempt_still_saves_the_file(tmp_path):
    file_writer = FileWriterThatSucceedsOnAttempt(MAXIMUM_NAME_ATTEMPTS)

    saved_path = build_repository(tmp_path, file_writer).save(build_encoded_scan())

    assert saved_path.name == "2026-10-13_01000.pdf"
    assert len(file_writer.attempted_destinations) == MAXIMUM_NAME_ATTEMPTS


def test_one_attempt_beyond_the_limit_raises_output_folder_unavailable(tmp_path):
    file_writer = FileWriterThatSucceedsOnAttempt(MAXIMUM_NAME_ATTEMPTS + 1)

    with pytest.raises(OutputFolderUnavailableError):
        build_repository(tmp_path, file_writer).save(build_encoded_scan())

    assert len(file_writer.attempted_destinations) == MAXIMUM_NAME_ATTEMPTS


def test_ensure_output_folder_ready_creates_the_missing_folder(tmp_path):
    output_folder = tmp_path / "external disk" / "scans"

    build_real_repository(output_folder).ensure_output_folder_ready()

    assert output_folder.is_dir()


def test_ensure_output_folder_ready_follows_the_current_settings(tmp_path):
    settings_repository = InMemoryApplicationSettingsRepository(build_settings(tmp_path / "first"))
    repository = FileSystemScanOutputRepository(settings_repository, ScanFileNamingPolicy(), AtomicFileWriter())
    settings_repository.save(build_settings(tmp_path / "second"))

    repository.ensure_output_folder_ready()

    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["second"]


def test_ensure_output_folder_ready_raises_unavailable_below_a_file(tmp_path):
    blocking_file = tmp_path / "scans"
    blocking_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(blocking_file / "nested").ensure_output_folder_ready()
