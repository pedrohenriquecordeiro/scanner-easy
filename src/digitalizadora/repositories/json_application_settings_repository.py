import json
import logging
from dataclasses import dataclass
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scan_quality import is_supported_dots_per_inch
from digitalizadora.domain.scan_settings import ScanSettings
from digitalizadora.repositories.atomic_file_writer import AtomicFileWriter

LOGGER = logging.getLogger(__name__)
CAPTURE_MODE_KEY = "capture_mode"
DOTS_PER_INCH_KEY = "dots_per_inch"
COLOR_MODE_KEY = "color_mode"
SCAN_PRESET_KEY = "scan_preset"
AUTO_CROP_KEY = "auto_crop"
SCAN_QUALITY_KEY = "scan_quality"
KNOWN_CAPTURE_MODE_VALUES = frozenset(capture_mode.value for capture_mode in CaptureMode)
KNOWN_COLOR_MODE_VALUES = frozenset(color_mode.value for color_mode in ColorMode)
KNOWN_SCAN_PRESET_VALUES = frozenset(scan_preset.value for scan_preset in ScanPreset)
DEFAULT_ADJUSTMENT = ImageAdjustment()


@dataclass(frozen=True)
class RejectedValue:
    """A value of a tolerant key that this version does not accept; the key then takes its default."""

    key: str
    text: str
    fallback_description: str


@dataclass(frozen=True)
class SettingsReading:
    settings: ApplicationSettings
    rejected_values: tuple[RejectedValue, ...]


def _is_plain_integer(raw_value: object) -> bool:
    return isinstance(raw_value, int) and not isinstance(raw_value, bool)


def _read_capture_mode(document: dict[str, object]) -> tuple[CaptureMode, RejectedValue | None]:
    """A missing key is a file written before the mode existed and means the quick mode; so does an unknown value."""
    if CAPTURE_MODE_KEY not in document:
        return CaptureMode.SINGLE, None
    raw_capture_mode = document[CAPTURE_MODE_KEY]
    if isinstance(raw_capture_mode, str) and raw_capture_mode in KNOWN_CAPTURE_MODE_VALUES:
        return CaptureMode(raw_capture_mode), None
    return CaptureMode.SINGLE, RejectedValue(CAPTURE_MODE_KEY, repr(raw_capture_mode), "the single capture mode")


def _read_auto_crop(document: dict[str, object]) -> tuple[bool, RejectedValue | None]:
    if AUTO_CROP_KEY not in document:
        return False, None
    raw_auto_crop = document[AUTO_CROP_KEY]
    if isinstance(raw_auto_crop, bool):
        return raw_auto_crop, None
    return False, RejectedValue(AUTO_CROP_KEY, repr(raw_auto_crop), "no automatic crop")


def _read_quality_pair(document: dict[str, object]) -> ScanSettings | None:
    raw_dots_per_inch = document.get(DOTS_PER_INCH_KEY)
    raw_color_mode = document.get(COLOR_MODE_KEY)
    if not (_is_plain_integer(raw_dots_per_inch) and is_supported_dots_per_inch(raw_dots_per_inch)):
        return None
    if not (isinstance(raw_color_mode, str) and raw_color_mode in KNOWN_COLOR_MODE_VALUES):
        return None
    return ScanSettings(raw_dots_per_inch, ColorMode(raw_color_mode))


def _read_fallback_preset(document: dict[str, object]) -> ScanPreset | None:
    raw_scan_preset = document.get(SCAN_PRESET_KEY)
    if isinstance(raw_scan_preset, str) and raw_scan_preset in KNOWN_SCAN_PRESET_VALUES:
        return ScanPreset(raw_scan_preset)
    return None


def _read_scan_settings(document: dict[str, object]) -> tuple[ScanSettings, RejectedValue | None]:
    """The pair of keys wins. An invalid pair falls back to the preset of an older file, or to the document preset
    when the file has none (a file written by this version); either way the other settings are kept. Without a
    pair, the preset of an older file is required."""
    quality_pair = _read_quality_pair(document)
    if quality_pair is not None:
        return quality_pair, None
    pair_is_present = DOTS_PER_INCH_KEY in document or COLOR_MODE_KEY in document
    if not pair_is_present:
        return ScanPreset(document[SCAN_PRESET_KEY]).settings, None
    fallback_preset = _read_fallback_preset(document) or ScanPreset.DOCUMENT
    pair_text = repr((document.get(DOTS_PER_INCH_KEY), document.get(COLOR_MODE_KEY)))
    return fallback_preset.settings, RejectedValue(SCAN_QUALITY_KEY, pair_text, f"the {fallback_preset.value} preset")


def read_application_settings(document: object) -> SettingsReading:
    if not isinstance(document, dict):
        raise ValueError("The settings document must be a JSON object")
    output_folder_text = document["output_folder"]
    if not isinstance(output_folder_text, str):
        raise ValueError("The output folder must be text")
    output_folder = Path(output_folder_text)
    if not output_folder.is_absolute():
        raise ValueError("The output folder must be an absolute path")
    output_format = OutputFormat(document["output_format"])
    scan_settings, rejected_quality = _read_scan_settings(document)
    capture_mode, rejected_capture_mode = _read_capture_mode(document)
    auto_crop, rejected_auto_crop = _read_auto_crop(document)
    rejected_values = tuple(
        rejected
        for rejected in (rejected_quality, rejected_capture_mode, rejected_auto_crop)
        if rejected is not None
    )
    settings = ApplicationSettings(
        output_folder=output_folder,
        output_format=output_format,
        scan_settings=scan_settings,
        capture_mode=capture_mode,
        adjustment=ImageAdjustment(auto_crop=auto_crop),
    )
    return SettingsReading(settings, rejected_values)


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
        # The state endpoint reads the settings on every poll: each rejected value is reported once, not once per read.
        self._reported_text_by_key: dict[str, str] = {}

    def load(self) -> ApplicationSettings:
        try:
            document = json.loads(self._storage_file.read_text(encoding="utf-8"))
            reading = read_application_settings(document)
        except FileNotFoundError:
            return self._default_settings
        except (OSError, ValueError, KeyError) as error:
            LOGGER.warning("Using the default settings because %s is unusable: %r", self._storage_file, error)
            return self._default_settings
        for rejected_value in reading.rejected_values:
            self._report_once(rejected_value)
        return reading.settings

    def save(self, settings: ApplicationSettings) -> None:
        document = {
            "output_folder": str(settings.output_folder),
            "output_format": settings.output_format.value,
            DOTS_PER_INCH_KEY: settings.scan_settings.dots_per_inch,
            COLOR_MODE_KEY: settings.scan_settings.color_mode.value,
            CAPTURE_MODE_KEY: settings.capture_mode.value,
            AUTO_CROP_KEY: settings.adjustment.auto_crop,
        }
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)
        encoded_document = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
        self._file_writer.replace_file(self._storage_file, encoded_document)

    def _report_once(self, rejected_value: RejectedValue) -> None:
        if self._reported_text_by_key.get(rejected_value.key) == rejected_value.text:
            return
        self._reported_text_by_key[rejected_value.key] = rejected_value.text
        LOGGER.warning(
            "Using %s because %s is not valid for %s in %s",
            rejected_value.fallback_description,
            rejected_value.text,
            rejected_value.key,
            self._storage_file,
        )
