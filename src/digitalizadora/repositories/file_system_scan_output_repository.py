from collections.abc import Callable, Iterable, Iterator, Sequence
from itertools import islice
from pathlib import Path

from digitalizadora.domain.documents.document_name_policy import FIRST_ATTEMPT_NUMBER, build_document_file_name
from digitalizadora.domain.documents.document_pdf_to_save import DocumentPdfToSave
from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.quick_scan.last_scan import SavedScanFile
from digitalizadora.domain.scan_file_naming_policy import SINGLE_FILE_COUNT, ScanFileNamingPolicy
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

    def save_scans(self, encoded_scans: Sequence[EncodedScan]) -> tuple[Path, ...]:
        return self.save_scans_in_folder(self.output_folder(), encoded_scans)

    def save_scans_in_folder(self, output_folder: Path, encoded_scans: Sequence[EncodedScan]) -> tuple[Path, ...]:
        """The files of one write, in that folder, under names of one timestamp (a counter tells them apart).

        All the files have the output format of the first one. An edit of an old scan saves in the folder of the
        scan. A name taken by another process takes back the files already made and moves all of them one
        nanosecond ahead."""
        if not encoded_scans:
            return ()
        name_groups = self._generated_name_groups(output_folder, encoded_scans)
        for file_names in name_groups:
            try:
                return self._write_files(output_folder, file_names, encoded_scans)
            except FileExistsError:
                continue
        raise OutputFolderUnavailableError(
            f"No free file name in {output_folder} after {MAXIMUM_NAME_ATTEMPTS} attempts"
        )

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
            self._prepare_folder(folder)
            return self._single_file_names()
        self._prepare_folder(folder)
        attempt_numbers = range(FIRST_ATTEMPT_NUMBER, FIRST_ATTEMPT_NUMBER + MAXIMUM_NAME_ATTEMPTS)
        return (build_document_file_name(document_pdf.document_name, number) for number in attempt_numbers)

    def _single_file_names(self) -> Iterator[str]:
        name_groups = self._naming_policy.name_groups(OutputFormat.PDF, SINGLE_FILE_COUNT)
        limited_name_groups = islice(name_groups, MAXIMUM_NAME_ATTEMPTS)
        return (file_names[0] for file_names in limited_name_groups)

    def _generated_name_groups(self, folder: Path, encoded_scans: Sequence[EncodedScan]) -> Iterator[tuple[str, ...]]:
        self._prepare_folder(folder)
        name_groups = self._naming_policy.name_groups(encoded_scans[0].output_format, len(encoded_scans))
        return islice(name_groups, MAXIMUM_NAME_ATTEMPTS)

    def _write_files(
        self, folder: Path, file_names: tuple[str, ...], encoded_scans: Sequence[EncodedScan]
    ) -> tuple[Path, ...]:
        written_paths: list[Path] = []
        for file_name, encoded_scan in zip(file_names, encoded_scans, strict=True):
            destination = folder / file_name
            try:
                self._file_writer.write_new_file(destination, encoded_scan.content)
            except FileExistsError:
                self._take_back(written_paths)
                raise
            except OSError as error:
                raise translate_storage_error(error, f"Cannot write {destination}") from error
            written_paths.append(destination)
        return tuple(written_paths)

    def _take_back(self, written_paths: Iterable[Path]) -> None:
        """Only the files this write has just created, so that no file of a half-made group stays behind."""
        for written_path in written_paths:
            written_path.unlink(missing_ok=True)

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
