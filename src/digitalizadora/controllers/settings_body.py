from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.scan_preset import ScanPreset

SettingsBody = dict[str, str | int | bool | None]


def build_settings_body(settings: ApplicationSettings) -> SettingsBody:
    """The scan preset is computed from the saved quality: None is the "custom" combination."""
    matching_preset = ScanPreset.matching(settings.scan_settings)
    return {
        "output_folder": str(settings.output_folder),
        "output_format": settings.output_format.value,
        "dots_per_inch": settings.scan_settings.dots_per_inch,
        "color_mode": settings.scan_settings.color_mode.value,
        "scan_preset": None if matching_preset is None else matching_preset.value,
        "capture_mode": settings.capture_mode.value,
        "rotation_degrees": settings.adjustment.rotation.value,
        "auto_crop": settings.adjustment.auto_crop,
    }
