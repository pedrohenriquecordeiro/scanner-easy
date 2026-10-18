from digitalizadora.domain.settings.application_settings import ApplicationSettings

SettingsBody = dict[str, str | int | bool | None]


def build_settings_body(settings: ApplicationSettings) -> SettingsBody:
    """The settings the page shows; the old preset and rotation are no longer part of them."""
    return {
        "output_folder": str(settings.output_folder),
        "output_format": settings.output_format.value,
        "dots_per_inch": settings.scan_settings.dots_per_inch,
        "color_mode": settings.scan_settings.color_mode.value,
        "capture_mode": settings.capture_mode.value,
        "auto_crop": settings.adjustment.auto_crop,
        "crop_margin": settings.adjustment.crop_margin,
    }
