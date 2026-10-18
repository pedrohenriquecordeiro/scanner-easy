from datetime import datetime
from pathlib import Path

from digitalizadora.domain.encoded_scan import EncodedScan
from digitalizadora.domain.errors import OutputFolderUnavailableError
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_file_naming_policy import ScanFileNamingPolicy
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
        folder = self.output_folder()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            first_sequence_number = self._highest_sequence_number(folder, encoded_scan.created_at) + 1
        except OSError as error:
            raise translate_storage_error(error, f"Cannot use the output folder {folder}") from error
        return self._write_under_a_free_name(folder, encoded_scan, first_sequence_number)

    def _write_under_a_free_name(self, folder: Path, encoded_scan: EncodedScan, first_sequence_number: int) -> Path:
        for sequence_number in range(first_sequence_number, first_sequence_number + MAXIMUM_NAME_ATTEMPTS):
            destination = folder / self._naming_policy.build_file_name(
                encoded_scan.created_at, sequence_number, encoded_scan.output_format
            )
            try:
                self._file_writer.write_new_file(destination, encoded_scan.content)
            except FileExistsError:
                continue
            except OSError as error:
                raise translate_storage_error(error, f"Cannot write {destination}") from error
            return destination
        raise OutputFolderUnavailableError(
            f"No free file name in {folder} after {MAXIMUM_NAME_ATTEMPTS} attempts"
        )

    def _highest_sequence_number(self, folder: Path, scanned_at: datetime) -> int:
        sequence_numbers = (
            self._naming_policy.extract_sequence_number(entry.name, scanned_at) for entry in folder.iterdir()
        )
        return max((number for number in sequence_numbers if number is not None), default=0)
