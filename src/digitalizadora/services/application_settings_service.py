from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.errors import InvalidSettingsError
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_preset import ScanPreset

NULL_CHARACTER = "\0"


@dataclass(frozen=True)
class SettingsUpdate:
    output_folder: str
    output_format: str
    scan_preset: str


def parse_enum_member[EnumMember: Enum](
    enum_type: type[EnumMember], raw_value: str, field_label: str
) -> EnumMember:
    try:
        return enum_type(raw_value)
    except ValueError as error:
        raise InvalidSettingsError(f"Unsupported {field_label}: {raw_value!r}") from error


def parse_output_folder(raw_folder: str) -> Path:
    if NULL_CHARACTER in raw_folder:
        raise InvalidSettingsError("Output folder must not contain a null character")
    try:
        folder = Path(raw_folder).expanduser()
    except RuntimeError as error:
        # Path.expanduser raises RuntimeError for "~someone" when that user does not exist.
        raise InvalidSettingsError(f"Cannot expand the home folder in {raw_folder!r}") from error
    if not folder.is_absolute():
        raise InvalidSettingsError(f"Output folder must be an absolute path: {raw_folder!r}")
    return folder


class ApplicationSettingsService:
    def __init__(
        self,
        settings_repository: ApplicationSettingsRepository,
        folder_preparer: Callable[[Path], None],
    ) -> None:
        self._settings_repository = settings_repository
        self._folder_preparer = folder_preparer

    def current(self) -> ApplicationSettings:
        return self._settings_repository.load()

    def update(self, update: SettingsUpdate) -> ApplicationSettings:
        output_format = parse_enum_member(OutputFormat, update.output_format, "output format")
        scan_preset = parse_enum_member(ScanPreset, update.scan_preset, "scan preset")
        output_folder = parse_output_folder(update.output_folder)
        self._folder_preparer(output_folder)
        settings = ApplicationSettings(
            output_folder=output_folder,
            output_format=output_format,
            scan_preset=scan_preset,
        )
        self._settings_repository.save(settings)
        return settings
