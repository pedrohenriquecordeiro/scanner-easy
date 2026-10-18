from collections.abc import Callable, Iterable, Iterator
from itertools import islice
from pathlib import Path

from digitalizadora.domain.document_name_policy import FIRST_ATTEMPT_NUMBER, build_document_file_name
from digitalizadora.domain.document_pdf_to_save import DocumentPdfToSave
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.last_scan import SavedScanFile
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
from digitalizadora.domain.scan_result import ScanResult
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter
from digitalizadora.repositories.output_folder_preparer import prepare_output_folder, translate_storage_error

MAXIMUM_NAME_ATTEMPTS = 1000


class FileSystemScanOutputRepository:
    def __init__(
        self,
        settings_repository: ApplicationSettingsRepository,
        naming_policy: ScanFileNamingPolicy,
        file_writer: AtomicFileWriter,
    ) -> None:
        self._settings_repository = settings_repository
        self._naming_policy = naming_policy
        self._file_writer = file_writer

    def output_folder(self) -> Path:
        return self._settings_repository.load().output_folder

    def ensure_output_folder_ready(self) -> None:
        prepare_output_folder(self.output_folder())

    def save(self, encoded_scan: EncodedScan) -> Path:
        return self.save_in_folder(self.output_folder(), encoded_scan)

    def save_in_folder(self, output_folder: Path, encoded_scan: EncodedScan) -> Path:
        """Under a timestamp name in that folder; an edit of an old scan saves in the folder of the scan."""
        candidate_names = self._generated_file_names(output_folder, encoded_scan.output_format)
        destination, _ = self._write_under_a_free_name(
            output_folder,
            candidate_names,
            lambda candidate: self._file_writer.write_new_file(candidate, encoded_scan.content),
        )
        return destination

    def save_document(self, document_pdf: DocumentPdfToSave) -> ScanResult:
        """Streams the PDF under the first free name; a name that already exists is skipped before assembling.

        Only a real race (another process creating the name during the assembly) assembles again.
        """
        folder = self.output_folder()
        destination, size_in_bytes = self._write_under_a_free_name(
            folder,
            self._document_file_names(folder, document_pdf),
            lambda candidate: self._file_writer.write_new_file_from(candidate, document_pdf.write_content),
        )
        return ScanResult(
            output_path=destination,
            output_format=OutputFormat.PDF,
            scanned_at=document_pdf.created_at,
            size_in_bytes=size_in_bytes,
        )

    def describe_saved_scan(self, scan_path: Path) -> SavedScanFile | None:
        """The size and the modification time of a file the application saved, or None when it is gone."""
        try:
            file_status = scan_path.stat()
        except FileNotFoundError:
            return None
        except OSError as error:
            raise translate_storage_error(error, f"Cannot read the status of {scan_path}") from error
        return SavedScanFile(scan_path.name, file_status.st_size, file_status.st_mtime_ns)

    def _document_file_names(self, folder: Path, document_pdf: DocumentPdfToSave) -> Iterator[str]:
        if not document_pdf.document_name:
            return self._generated_file_names(folder, OutputFormat.PDF)
        self._prepare_folder(folder)
        attempt_numbers = range(FIRST_ATTEMPT_NUMBER, FIRST_ATTEMPT_NUMBER + MAXIMUM_NAME_ATTEMPTS)
        return (build_document_file_name(document_pdf.document_name, number) for number in attempt_numbers)

    def _generated_file_names(self, folder: Path, output_format: OutputFormat) -> Iterator[str]:
        self._prepare_folder(folder)
        return islice(self._naming_policy.file_names(output_format), MAXIMUM_NAME_ATTEMPTS)

    def _prepare_folder(self, folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise translate_storage_error(error, f"Cannot use the output folder {folder}") from error

    def _write_under_a_free_name[WrittenOutcome](
        self, folder: Path, candidate_names: Iterable[str], write_file: Callable[[Path], WrittenOutcome]
    ) -> tuple[Path, WrittenOutcome]:
        for candidate_name in candidate_names:
            destination = folder / candidate_name
            try:
                written_outcome = write_file(destination)
            except FileExistsError:
                continue
            except OSError as error:
                raise translate_storage_error(error, f"Cannot write {destination}") from error
            return destination, written_outcome
        raise OutputFolderUnavailableError(
            f"No free file name in {folder} after {MAXIMUM_NAME_ATTEMPTS} attempts"
        )
