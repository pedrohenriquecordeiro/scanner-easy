from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.errors import InvalidSettingsError
from digitalizadora.domain.image_adjustment import ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.ports import ApplicationSettingsRepository
from digitalizadora.domain.scan_quality import is_supported_dots_per_inch
from digitalizadora.domain.scan_settings import ScanSettings

NULL_CHARACTER = "\0"


@dataclass(frozen=True)
class SettingsUpdate:
    """The two first fields are required; None in any other field keeps the saved value."""

    output_folder: str
    output_format: str
    capture_mode: str | None = None
    dots_per_inch: int | None = None
    color_mode: str | None = None
    auto_crop: bool | None = None
    crop_margin: bool | None = None
    jpeg_quality: int | None = None


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
        saved = self.current()
        output_format = parse_enum_member(OutputFormat, update.output_format, "output format")
        scan_settings = self._resolve_scan_settings(update, saved)
        capture_mode = self._resolve_capture_mode(update, saved)
        adjustment = self._resolve_adjustment(update, saved)
        output_folder = parse_output_folder(update.output_folder)
        self._folder_preparer(output_folder)
        settings = ApplicationSettings(
            output_folder=output_folder,
            output_format=output_format,
            scan_settings=scan_settings,
            capture_mode=capture_mode,
            adjustment=adjustment,
        )
        self._settings_repository.save(settings)
        return settings

    @staticmethod
    def _resolve_scan_settings(update: SettingsUpdate, saved: ApplicationSettings) -> ScanSettings:
        if update.dots_per_inch is None and update.color_mode is None:
            return saved.scan_settings
        return ScanSettings(
            dots_per_inch=_resolve_dots_per_inch(update.dots_per_inch, saved.scan_settings),
            color_mode=_resolve_color_mode(update.color_mode, saved.scan_settings),
        )

    @staticmethod
    def _resolve_capture_mode(update: SettingsUpdate, saved: ApplicationSettings) -> CaptureMode:
        if update.capture_mode is None:
            return saved.capture_mode
        return parse_enum_member(CaptureMode, update.capture_mode, "capture mode")

    @staticmethod
    def _resolve_adjustment(update: SettingsUpdate, saved: ApplicationSettings) -> ImageAdjustment:
        return ImageAdjustment(
            auto_crop=saved.adjustment.auto_crop if update.auto_crop is None else update.auto_crop,
            crop_margin=saved.adjustment.crop_margin if update.crop_margin is None else update.crop_margin,
            jpeg_quality=saved.adjustment.jpeg_quality if update.jpeg_quality is None else update.jpeg_quality,
        )


def _resolve_dots_per_inch(requested_dots_per_inch: int | None, saved_settings: ScanSettings) -> int:
    if requested_dots_per_inch is None:
        return saved_settings.dots_per_inch
    if not is_supported_dots_per_inch(requested_dots_per_inch):
        raise InvalidSettingsError(f"Unsupported resolution: {requested_dots_per_inch!r}")
    return requested_dots_per_inch


def _resolve_color_mode(requested_color_mode: str | None, saved_settings: ScanSettings) -> ColorMode:
    if requested_color_mode is None:
        return saved_settings.color_mode
    return parse_enum_member(ColorMode, requested_color_mode, "colour mode")

