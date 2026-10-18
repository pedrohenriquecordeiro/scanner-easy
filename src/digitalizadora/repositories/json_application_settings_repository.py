import json
import logging
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

LOGGER = logging.getLogger(__name__)
CAPTURE_MODE_KEY = "capture_mode"
KNOWN_CAPTURE_MODE_VALUES = frozenset(capture_mode.value for capture_mode in CaptureMode)


def parse_capture_mode(document: dict[str, object]) -> CaptureMode:
    """Reads the capture mode on its own, so an unknown value never discards the output folder.

    A missing key is a file written before the mode existed and means the quick mode;
    any other value this version does not know also means the quick mode (the repository reports it).
    """
    raw_capture_mode = document.get(CAPTURE_MODE_KEY, CaptureMode.SINGLE.value)
    if isinstance(raw_capture_mode, str) and raw_capture_mode in KNOWN_CAPTURE_MODE_VALUES:
        return CaptureMode(raw_capture_mode)
    return CaptureMode.SINGLE


def find_unknown_capture_mode_text(document: dict[str, object]) -> str | None:
    """The text of a capture mode this version does not know, or None when the key is missing or known."""
    if CAPTURE_MODE_KEY not in document:
        return None
    raw_capture_mode = document[CAPTURE_MODE_KEY]
    if isinstance(raw_capture_mode, str) and raw_capture_mode in KNOWN_CAPTURE_MODE_VALUES:
        return None
    return repr(raw_capture_mode)


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
        capture_mode=parse_capture_mode(document),
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
        # The state endpoint reads the settings on every poll: each unknown mode is reported once, not once per read.
        self._reported_capture_mode_text: str | None = None

    def load(self) -> ApplicationSettings:
        try:
            document = json.loads(self._storage_file.read_text(encoding="utf-8"))
            settings = parse_application_settings(document)
        except FileNotFoundError:
            return self._default_settings
        except (OSError, ValueError, KeyError) as error:
            LOGGER.warning("Using the default settings because %s is unusable: %r", self._storage_file, error)
            return self._default_settings
        self._report_unknown_capture_mode(document)
        return settings

    def save(self, settings: ApplicationSettings) -> None:
        document = {
            "output_folder": str(settings.output_folder),
            "output_format": settings.output_format.value,
            "scan_preset": settings.scan_preset.value,
            CAPTURE_MODE_KEY: settings.capture_mode.value,
        }
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        encoded_document = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
        self._file_writer.replace_file(self._storage_file, encoded_document)

    def _report_unknown_capture_mode(self, document: dict[str, object]) -> None:
        unknown_capture_mode_text = find_unknown_capture_mode_text(document)
        if unknown_capture_mode_text is None or unknown_capture_mode_text == self._reported_capture_mode_text:
            return
        self._reported_capture_mode_text = unknown_capture_mode_text
        LOGGER.warning(
            "Using the single capture mode because %s is not a known capture mode", unknown_capture_mode_text
        )
