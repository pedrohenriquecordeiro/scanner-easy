import dataclasses
import errno
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

import pikepdf
import pytest

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.document_draft_reconciliation import page_file_name
from digitalizadora.domain.errors import (
    DocumentAssemblyFailedError,
    DocumentTooLargeError,
    InsufficientStorageError,
    OutputFolderUnavailableError,
)
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.file_system_document_draft_repository import CURRENT_DRAFT_FOLDER_NAME
from digitalizadora.repositories.file_system_scan_output_repository import FileSystemScanOutputRepository
from digitalizadora.services.document_finalizer import DocumentAssemblyInput, DocumentFinalizer
from digitalizadora.services.pdf_assembly_service import PdfAssemblyService, PdfDocumentMetadata
from digitalizadora.services.storage_guard_service import MINIMUM_FREE_SPACE_BYTES, StorageGuardService
from tests.fakes.document_drafts import DRAFT_CREATED_AT, seed_draft_folder
from tests.fakes.in_memory_settings_repository import InMemoryApplicationSettingsRepository
from tests.fakes.recording_free_space_reader import RecordingFreeSpaceReader
from tests.fakes.sample_images import build_sample_jpeg
from tests.fakes.scripted_file_writer import ScriptedFileWriter

FINALIZED_AT = DRAFT_CREATED_AT + timedelta(minutes=5)
DOCUMENT_NAME = "Contrato do apartamento"
DOCUMENT_FILE_NAME = "Contrato do apartamento.pdf"
POINTS_PER_INCH = 72
WIDE_PAGE_JPEG = build_sample_jpeg(width_pixels=144, height_pixels=72, dots_per_inch=POINTS_PER_INCH)
NARROW_PAGE_JPEG = build_sample_jpeg(width_pixels=72, height_pixels=72, dots_per_inch=POINTS_PER_INCH)
WIDE_PAGE_WIDTH_IN_POINTS = 144.0
NARROW_PAGE_WIDTH_IN_POINTS = 72.0
POINT_TOLERANCE = 0.01
PLENTY_OF_FREE_SPACE_IN_BYTES = 1024**4
FULL_DISK_ERROR = OSError(errno.ENOSPC, "No space left on device")


class ExhaustedMemoryPdfAssemblyService(PdfAssemblyService):
    """The assembly of a document too large for the free memory of the Mac."""

    def write_pdf_at_embedded_resolutions(
        self, page_files: Sequence[Path], metadata: PdfDocumentMetadata, output_stream: BinaryIO
    ) -> None:
        raise MemoryError


@pytest.fixture
def output_folder(tmp_path: Path) -> Path:
    return tmp_path / "output"


@pytest.fixture
def seeded_input(tmp_path: Path) -> DocumentAssemblyInput:
    """A seeded draft of a wide and a narrow page, with its page files in the order of the draft."""
    drafts_folder = tmp_path / "drafts"
    draft = seed_draft_folder(drafts_folder, [WIDE_PAGE_JPEG, NARROW_PAGE_JPEG])
    draft_folder = drafts_folder / CURRENT_DRAFT_FOLDER_NAME
    page_files = [draft_folder / page_file_name(page_identifier) for page_identifier in draft.page_identifiers]
    return DocumentAssemblyInput(draft=draft, page_files=page_files, finalized_at=FINALIZED_AT)


@pytest.fixture
def free_space_reader() -> RecordingFreeSpaceReader:
    return RecordingFreeSpaceReader(PLENTY_OF_FREE_SPACE_IN_BYTES)


def build_finalizer(
    output_folder: Path, free_space_reader: RecordingFreeSpaceReader, file_writer: AtomicFileWriter
) -> DocumentFinalizer:
    settings_repository = InMemoryApplicationSettingsRepository(
        ApplicationSettings(output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT)
    )
    return DocumentFinalizer(
        PdfAssemblyService(),
        FileSystemScanOutputRepository(settings_repository, ScanFileNamingPolicy(), file_writer),
        StorageGuardService(free_space_reader),
    )


@pytest.fixture
def finalizer(output_folder: Path, free_space_reader: RecordingFreeSpaceReader) -> DocumentFinalizer:
    return build_finalizer(output_folder, free_space_reader, AtomicFileWriter())


def with_document_name(assembly_input: DocumentAssemblyInput) -> DocumentAssemblyInput:
    return dataclasses.replace(assembly_input, draft=assembly_input.draft.renamed(DOCUMENT_NAME))


def read_page_widths(pdf_path: Path) -> list[float]:
    with pikepdf.open(pdf_path) as pdf:
        return [float(pdf_page.mediabox[2]) for pdf_page in pdf.pages]


def read_document_information(pdf_path: Path, key: str) -> str:
    with pikepdf.open(pdf_path) as pdf:
        return str(pdf.docinfo[key])


def test_ensure_capacity_creates_a_missing_output_folder(finalizer, seeded_input, output_folder):
    finalizer.ensure_capacity(seeded_input.draft)

    assert output_folder.is_dir()


def test_ensure_capacity_with_an_unusable_output_folder_raises_output_folder_unavailable(
    finalizer, seeded_input, output_folder
):
    output_folder.write_bytes(b"a file where the folder should be")

    with pytest.raises(OutputFolderUnavailableError):
        finalizer.ensure_capacity(seeded_input.draft)


def test_unusable_output_folder_is_reported_before_the_free_space_is_read(
    seeded_input, output_folder, free_space_reader
):
    output_folder.write_bytes(b"a file where the folder should be")
    finalizer = build_finalizer(output_folder, free_space_reader, AtomicFileWriter())

    with pytest.raises(OutputFolderUnavailableError):
        finalizer.ensure_capacity(seeded_input.draft)

    assert free_space_reader.requested_folders == []


def test_ensure_capacity_accepts_the_minimum_plus_the_draft_size_in_the_output_folder(seeded_input, output_folder):
    draft = seeded_input.draft
    free_space_reader = RecordingFreeSpaceReader(MINIMUM_FREE_SPACE_BYTES + draft.estimated_size_in_bytes)

    build_finalizer(output_folder, free_space_reader, AtomicFileWriter()).ensure_capacity(draft)

    assert free_space_reader.requested_folders == [output_folder]


def test_ensure_capacity_one_byte_short_raises_insufficient_storage(seeded_input, output_folder):
    draft = seeded_input.draft
    free_space_reader = RecordingFreeSpaceReader(MINIMUM_FREE_SPACE_BYTES + draft.estimated_size_in_bytes - 1)
    finalizer = build_finalizer(output_folder, free_space_reader, AtomicFileWriter())

    with pytest.raises(InsufficientStorageError):
        finalizer.ensure_capacity(draft)


def test_write_document_saves_the_pdf_under_the_document_name(finalizer, seeded_input, output_folder):
    result = finalizer.write_document(with_document_name(seeded_input))

    assert result.output_path == output_folder / DOCUMENT_FILE_NAME


def test_write_document_without_a_name_follows_the_sequence_of_the_finalization_day(
    finalizer, seeded_input, output_folder
):
    result = finalizer.write_document(seeded_input)

    assert result.output_path == output_folder / "2026-10-17_00001.pdf"


def test_pdf_title_is_the_document_name(finalizer, seeded_input):
    result = finalizer.write_document(with_document_name(seeded_input))

    assert read_document_information(result.output_path, "/Title") == DOCUMENT_NAME


def test_pdf_title_without_a_name_names_the_moment_the_draft_was_created(finalizer, seeded_input):
    result = finalizer.write_document(seeded_input)

    assert read_document_information(result.output_path, "/Title") == "Digitalização 2026-10-17 10:00:00"


def test_pdf_creation_date_is_the_finalization_moment_in_universal_time(finalizer, seeded_input):
    result = finalizer.write_document(seeded_input)

    assert read_document_information(result.output_path, "/CreationDate") == "D:20261017130500Z"


def test_pdf_keeps_the_order_of_the_page_files(finalizer, seeded_input):
    reversed_input = dataclasses.replace(seeded_input, page_files=list(reversed(seeded_input.page_files)))

    result = finalizer.write_document(reversed_input)

    assert read_page_widths(result.output_path) == pytest.approx(
        [NARROW_PAGE_WIDTH_IN_POINTS, WIDE_PAGE_WIDTH_IN_POINTS], abs=POINT_TOLERANCE
    )


def test_result_reports_the_size_of_the_written_pdf(finalizer, seeded_input):
    result = finalizer.write_document(seeded_input)

    assert result.size_in_bytes == result.output_path.stat().st_size


def test_result_is_a_pdf_dated_at_the_finalization_moment(finalizer, seeded_input):
    result = finalizer.write_document(seeded_input)

    assert (result.output_format, result.scanned_at) == (OutputFormat.PDF, FINALIZED_AT)


def test_unreadable_page_raises_document_assembly_failed(finalizer, seeded_input):
    seeded_input.page_files[0].write_bytes(b"not a jpeg")

    with pytest.raises(DocumentAssemblyFailedError):
        finalizer.write_document(seeded_input)


def test_unreadable_page_leaves_no_file_in_the_output_folder(finalizer, seeded_input, output_folder):
    seeded_input.page_files[0].write_bytes(b"not a jpeg")

    with pytest.raises(DocumentAssemblyFailedError):
        finalizer.write_document(seeded_input)

    assert list(output_folder.iterdir()) == []


def test_memory_error_while_assembling_raises_document_too_large(seeded_input, output_folder, free_space_reader):
    settings_repository = InMemoryApplicationSettingsRepository(
        ApplicationSettings(output_folder, OutputFormat.PDF, ScanPreset.DOCUMENT)
    )
    finalizer = DocumentFinalizer(
        ExhaustedMemoryPdfAssemblyService(),
        FileSystemScanOutputRepository(settings_repository, ScanFileNamingPolicy(), AtomicFileWriter()),
        StorageGuardService(free_space_reader),
    )

    with pytest.raises(DocumentTooLargeError):
        finalizer.write_document(seeded_input)


def test_full_output_disk_while_writing_raises_insufficient_storage(seeded_input, output_folder, free_space_reader):
    file_writer = ScriptedFileWriter({DOCUMENT_FILE_NAME: FULL_DISK_ERROR})
    finalizer = build_finalizer(output_folder, free_space_reader, file_writer)

    with pytest.raises(InsufficientStorageError):
        finalizer.write_document(with_document_name(seeded_input))
