from digitalizadora.domain.application_settings import ApplicationSettings


def build_settings_body(settings: ApplicationSettings) -> dict[str, str]:
    return {
        "output_folder": str(settings.output_folder),
        "output_format": settings.output_format.value,
        "scan_preset": settings.scan_preset.value,
        "capture_mode": settings.capture_mode.value,
    }
