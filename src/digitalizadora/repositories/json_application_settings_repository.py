import json
import logging
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

LOGGER = logging.getLogger(__name__)


def parse_application_settings(document: object) -> ApplicationSettings:
    if not isinstance(document, dict):
        raise ValueError("The settings document must be a JSON object")
    output_folder_text = document["output_folder"]
    if not isinstance(output_folder_text, str):
        raise ValueError("The output folder must be text")
    output_folder = Path(output_folder_text)
    if not output_folder.is_absolute():
        raise ValueError("The output folder must be an absolute path")
    return ApplicationSettings(
        output_folder=output_folder,
        output_format=OutputFormat(document["output_format"]),
        scan_preset=ScanPreset(document["scan_preset"]),
    )


class JsonApplicationSettingsRepository:
    def __init__(
        self,
        storage_file: Path,
        default_settings: ApplicationSettings,
        file_writer: AtomicFileWriter,
    ) -> None:
        self._storage_file = storage_file
        self._default_settings = default_settings
        self._file_writer = file_writer

    def load(self) -> ApplicationSettings:
        try:
            document = json.loads(self._storage_file.read_text(encoding="utf-8"))
            return parse_application_settings(document)
        except FileNotFoundError:
            return self._default_settings
        except (OSError, ValueError, KeyError) as error:
            LOGGER.warning("Using the default settings because %s is unusable: %r", self._storage_file, error)
            return self._default_settings

    def save(self, settings: ApplicationSettings) -> None:
        document = {
            "output_folder": str(settings.output_folder),
            "output_format": settings.output_format.value,
            "scan_preset": settings.scan_preset.value,
        }
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        encoded_document = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
        self._file_writer.replace_file(self._storage_file, encoded_document)
