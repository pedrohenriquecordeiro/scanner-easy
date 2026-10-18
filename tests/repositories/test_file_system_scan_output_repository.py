import errno
import os
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.document_pdf_to_save import DocumentPdfToSave
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import InsufficientStorageError, OutputFolderUnavailableError, ScanFailedError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_scan_output_repository import (
    MAXIMUM_NAME_ATTEMPTS,
    FileSystemScanOutputRepository,
)
from tests.fakes.fixed_clock import FixedClock
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
    )


def build_settings(output_folder: Path) -> ApplicationSettings:
    return ApplicationSettings(output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT.settings)


def build_repository(output_folder: Path, file_writer) -> FileSystemScanOutputRepository:
    naming_policy = ScanFileNamingPolicy(FixedClock(SCANNED_AT))
    return FileSystemScanOutputRepository(
        InMemoryApplicationSettingsRepository(build_settings(output_folder)), naming_policy, file_writer
    )


def build_real_repository(output_folder: Path) -> FileSystemScanOutputRepository:
    return build_repository(output_folder, AtomicFileWriter())


def test_output_folder_comes_from_the_settings(tmp_path):
    assert build_real_repository(tmp_path / "scans").output_folder() == tmp_path / "scans"


FIRST_NAME = "2026_10_13__15_30_12_000000000"
SECOND_NAME = "2026_10_13__15_30_12_000000001"


def test_file_is_named_with_the_local_date_time_and_nanoseconds_of_the_clock(tmp_path):
    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path == tmp_path / f"{FIRST_NAME}.pdf"


def test_saved_file_holds_the_encoded_content(tmp_path):
    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.read_bytes() == b"scan content"


def test_a_file_saved_in_a_folder_goes_there_and_not_to_the_output_folder_of_the_settings(tmp_path):
    other_folder = tmp_path / "other"

    saved_path = build_real_repository(tmp_path / "scans").save_in_folder(other_folder, build_encoded_scan())

    assert saved_path == other_folder / f"{FIRST_NAME}.pdf"


def test_a_second_save_at_the_same_reading_gets_the_next_nanosecond(tmp_path):
    repository = build_real_repository(tmp_path)
    repository.save(build_encoded_scan())

    second_path = repository.save(build_encoded_scan())

    assert second_path.name == f"{SECOND_NAME}.pdf"


def test_old_files_with_the_daily_counter_are_left_alone_and_never_collide(tmp_path):
    (tmp_path / "2026-10-13_00001.pdf").write_bytes(b"old")
    (tmp_path / "2026-10-13_00007.jpg").write_bytes(b"old")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert (saved_path.name, (tmp_path / "2026-10-13_00001.pdf").read_bytes()) == (f"{FIRST_NAME}.pdf", b"old")


def test_the_date_of_the_name_follows_the_clock_and_not_the_folder_content(tmp_path):
    (tmp_path / "2026_10_12__15_30_12_000000000.pdf").write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == f"{FIRST_NAME}.pdf"


def test_pdf_and_jpeg_saved_at_the_same_reading_get_distinct_names(tmp_path):
    repository = build_real_repository(tmp_path)
    repository.save(build_encoded_scan(OutputFormat.PDF))

    saved_path = repository.save(build_encoded_scan(OutputFormat.JPEG))

    assert saved_path.name == f"{FIRST_NAME}.jpg"


def test_jpeg_uses_the_jpg_extension(tmp_path):
    saved_path = build_real_repository(tmp_path).save(build_encoded_scan(OutputFormat.JPEG))

    assert saved_path.name == f"{FIRST_NAME}.jpg"


def test_unrelated_files_and_leftover_temporary_files_are_ignored(tmp_path):
    for name in ("notes.txt", "2026-10-13_abc.pdf", ".2026_10_13__15_30_12_000000000.pdf.4242-0a1b2c3d.part"):
        (tmp_path / name).write_bytes(b"x")

    saved_path = build_real_repository(tmp_path).save(build_encoded_scan())

    assert saved_path.name == f"{FIRST_NAME}.pdf"


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

    assert saved_path.name == f"{SECOND_NAME}.pdf"
    assert (tmp_path / f"{FIRST_NAME}.pdf").read_bytes() == b"written by another process"


def test_last_allowed_attempt_still_saves_the_file(tmp_path):
    file_writer = FileWriterThatSucceedsOnAttempt(MAXIMUM_NAME_ATTEMPTS)

    saved_path = build_repository(tmp_path, file_writer).save(build_encoded_scan())

    assert saved_path.name == "2026_10_13__15_30_12_000000999.pdf"
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
    naming_policy = ScanFileNamingPolicy(FixedClock(SCANNED_AT))
    repository = FileSystemScanOutputRepository(settings_repository, naming_policy, AtomicFileWriter())
    settings_repository.save(build_settings(tmp_path / "second"))

    repository.ensure_output_folder_ready()

    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["second"]


def test_ensure_output_folder_ready_raises_unavailable_below_a_file(tmp_path):
    blocking_file = tmp_path / "scans"
    blocking_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(blocking_file / "nested").ensure_output_folder_ready()


FINALIZED_AT = datetime(2026, 10, 17, 10, 5, 0, tzinfo=TIME_ZONE)
DOCUMENT_NAME = "Contrato do apartamento"
ASSEMBLED_PDF = b"%PDF-1.7 assembled document"


def write_assembled_pdf(stream: BinaryIO) -> None:
    stream.write(ASSEMBLED_PDF)


class CountingPdfAssembly:
    """Stands in for the streamed assembly: writes the same PDF and counts how often it ran."""

    def __init__(self) -> None:
        self.call_count = 0

    def __call__(self, stream: BinaryIO) -> None:
        self.call_count += 1
        write_assembled_pdf(stream)


def build_document_pdf(
    document_name: str, write_content: Callable[[BinaryIO], None] = write_assembled_pdf
) -> DocumentPdfToSave:
    return DocumentPdfToSave(write_content=write_content, created_at=FINALIZED_AT, document_name=document_name)


def fail_with_error_number(error_number: int) -> Callable[[BinaryIO], None]:
    def failing_assembly(stream: BinaryIO) -> None:
        raise OSError(error_number, os.strerror(error_number))

    return failing_assembly


def skip_on_a_case_sensitive_volume(folder: Path) -> None:
    probe = folder / "letter-case-probe"
    probe.write_bytes(b"")
    is_case_sensitive = not (folder / "LETTER-CASE-PROBE").exists()
    probe.unlink()
    if is_case_sensitive:
        pytest.skip("the volume is case-sensitive; the default APFS volume of macOS is not")


class StreamWriterThatSucceedsOnAttempt:
    def __init__(self, successful_attempt: int) -> None:
        self._successful_attempt = successful_attempt
        self.attempted_destinations: list[Path] = []

    def write_new_file_from(self, destination: Path, write_content: Callable[[BinaryIO], None]) -> int:
        self.attempted_destinations.append(destination)
        if len(self.attempted_destinations) < self._successful_attempt:
            raise FileExistsError(destination)
        return len(ASSEMBLED_PDF)


class StreamWriterThatLosesTheFirstName:
    """Another 'process' takes the first chosen name while the PDF is being assembled."""

    def __init__(self, real_writer: AtomicFileWriter) -> None:
        self._real_writer = real_writer
        self._race_already_happened = False

    def write_new_file_from(self, destination: Path, write_content: Callable[[BinaryIO], None]) -> int:
        if self._race_already_happened:
            return self._real_writer.write_new_file_from(destination, write_content)
        self._race_already_happened = True

        def assemble_and_lose_the_name(stream: BinaryIO) -> None:
            write_content(stream)
            destination.write_bytes(b"written by another process")

        return self._real_writer.write_new_file_from(destination, assemble_and_lose_the_name)


def test_chosen_name_becomes_the_pdf_file_name(tmp_path):
    result = build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME))

    assert result.output_path == tmp_path / "Contrato do apartamento.pdf"


def test_saved_document_holds_what_the_assembly_wrote(tmp_path):
    result = build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME))

    assert result.output_path.read_bytes() == ASSEMBLED_PDF


def test_saved_document_result_has_the_path_the_moment_and_the_written_size(tmp_path):
    result = build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME))

    assert result == ScanResult(
        output_path=tmp_path / "Contrato do apartamento.pdf",
        output_format=OutputFormat.PDF,
        scanned_at=FINALIZED_AT,
        size_in_bytes=len(ASSEMBLED_PDF),
    )


def test_taken_chosen_name_moves_to_the_second_attempt(tmp_path):
    (tmp_path / "Contrato do apartamento.pdf").write_bytes(b"older document")

    result = build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME))

    assert result.output_path.name == "Contrato do apartamento (2).pdf"


def test_two_taken_names_move_to_the_third_attempt(tmp_path):
    (tmp_path / "Contrato do apartamento.pdf").write_bytes(b"older document")
    (tmp_path / "Contrato do apartamento (2).pdf").write_bytes(b"older document")

    result = build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME))

    assert result.output_path.name == "Contrato do apartamento (3).pdf"


def test_saving_a_document_never_overwrites_an_existing_file(tmp_path):
    (tmp_path / "Contrato do apartamento.pdf").write_bytes(b"older document")

    build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME))

    assert (tmp_path / "Contrato do apartamento.pdf").read_bytes() == b"older document"


def test_name_that_differs_only_in_letter_case_counts_as_taken(tmp_path):
    skip_on_a_case_sensitive_volume(tmp_path)
    (tmp_path / "Contrato do apartamento.pdf").write_bytes(b"older document")

    result = build_real_repository(tmp_path).save_document(build_document_pdf("contrato do apartamento"))

    assert result.output_path.name == "contrato do apartamento (2).pdf"


def test_taken_name_is_skipped_without_assembling_the_pdf(tmp_path):
    (tmp_path / "Contrato do apartamento.pdf").write_bytes(b"older document")
    assembly = CountingPdfAssembly()

    build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME, assembly))

    assert assembly.call_count == 1


def test_name_taken_during_the_assembly_assembles_again_under_the_next_name(tmp_path):
    assembly = CountingPdfAssembly()
    repository = build_repository(tmp_path, StreamWriterThatLosesTheFirstName(AtomicFileWriter()))

    result = repository.save_document(build_document_pdf(DOCUMENT_NAME, assembly))

    assert (result.output_path.name, assembly.call_count) == ("Contrato do apartamento (2).pdf", 2)


def test_empty_name_gets_the_timestamp_name_of_the_clock(tmp_path):
    (tmp_path / "2026-10-13_00007.pdf").write_bytes(b"x")

    result = build_real_repository(tmp_path).save_document(build_document_pdf(""))

    assert result.output_path.name == f"{FIRST_NAME}.pdf"


def test_last_allowed_name_attempt_still_saves_the_document(tmp_path):
    file_writer = StreamWriterThatSucceedsOnAttempt(MAXIMUM_NAME_ATTEMPTS)

    result = build_repository(tmp_path, file_writer).save_document(build_document_pdf(DOCUMENT_NAME))

    assert result.output_path.name == "Contrato do apartamento (1000).pdf"


def test_one_name_attempt_beyond_the_limit_raises_output_folder_unavailable(tmp_path):
    file_writer = StreamWriterThatSucceedsOnAttempt(MAXIMUM_NAME_ATTEMPTS + 1)

    with pytest.raises(OutputFolderUnavailableError):
        build_repository(tmp_path, file_writer).save_document(build_document_pdf(DOCUMENT_NAME))

    assert len(file_writer.attempted_destinations) == MAXIMUM_NAME_ATTEMPTS


@pytest.mark.parametrize("error_number", [errno.ENOSPC, errno.EDQUOT])
def test_full_disk_while_streaming_the_document_raises_insufficient_storage(tmp_path, error_number):
    document_pdf = build_document_pdf(DOCUMENT_NAME, fail_with_error_number(error_number))

    with pytest.raises(InsufficientStorageError):
        build_real_repository(tmp_path).save_document(document_pdf)


def test_input_output_error_while_streaming_the_document_raises_output_folder_unavailable(tmp_path):
    document_pdf = build_document_pdf(DOCUMENT_NAME, fail_with_error_number(errno.EIO))

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(tmp_path).save_document(document_pdf)


def test_assembly_failure_reaches_the_caller_unchanged(tmp_path):
    def unreadable_page(stream: BinaryIO) -> None:
        raise ScanFailedError("A scanned page could not be read as an image")

    with pytest.raises(ScanFailedError):
        build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME, unreadable_page))


def test_memory_error_of_the_assembly_reaches_the_caller_unchanged(tmp_path):
    def memory_exhausted(stream: BinaryIO) -> None:
        raise MemoryError

    with pytest.raises(MemoryError):
        build_real_repository(tmp_path).save_document(build_document_pdf(DOCUMENT_NAME, memory_exhausted))


def test_missing_output_folder_is_created_for_the_document(tmp_path):
    output_folder = tmp_path / "external disk" / "scans"

    result = build_real_repository(output_folder).save_document(build_document_pdf(DOCUMENT_NAME))

    assert result.output_path == output_folder / "Contrato do apartamento.pdf"


def test_output_folder_below_a_file_refuses_the_document(tmp_path):
    blocking_file = tmp_path / "scans"
    blocking_file.write_bytes(b"not a folder")

    with pytest.raises(OutputFolderUnavailableError):
        build_real_repository(blocking_file / "nested").save_document(build_document_pdf(DOCUMENT_NAME))


def test_describe_saved_scan_reports_the_size_of_the_file(tmp_path):
    saved_path = tmp_path / "2026_10_13__15_30_12_000000000.pdf"
    saved_path.write_bytes(b"scan content")

    described = build_real_repository(tmp_path).describe_saved_scan(saved_path)

    expected = ("2026_10_13__15_30_12_000000000.pdf", len(b"scan content"))
    assert (described.file_name, described.size_in_bytes) == expected


def test_describe_saved_scan_reports_the_modification_time_in_nanoseconds(tmp_path):
    saved_path = tmp_path / "2026_10_13__15_30_12_000000000.pdf"
    saved_path.write_bytes(b"scan content")

    described = build_real_repository(tmp_path).describe_saved_scan(saved_path)

    assert described.modified_at_nanoseconds == saved_path.stat().st_mtime_ns


def test_describe_saved_scan_changes_when_the_file_is_edited_later(tmp_path):
    saved_path = tmp_path / "2026_10_13__15_30_12_000000000.pdf"
    saved_path.write_bytes(b"scan content")
    repository = build_real_repository(tmp_path)
    before = repository.describe_saved_scan(saved_path)

    saved_path.write_bytes(b"scan content edited")

    assert repository.describe_saved_scan(saved_path) != before


def test_describe_saved_scan_of_a_file_that_is_gone_is_none(tmp_path):
    assert build_real_repository(tmp_path).describe_saved_scan(tmp_path / "2026_10_13__15_30_12_000000000.pdf") is None


def test_saving_the_same_image_twice_keeps_both_files_under_different_names(tmp_path):
    repository = build_real_repository(tmp_path)

    first_path = repository.save(build_encoded_scan())
    second_path = repository.save(build_encoded_scan())

    assert (first_path.name, second_path.name, first_path.read_bytes(), second_path.read_bytes()) == (
        "2026_10_13__15_30_12_000000000.pdf",
        "2026_10_13__15_30_12_000000001.pdf",
        b"scan content",
        b"scan content",
    )
