from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset


def test_to_scan_request_combines_preset_settings_and_output_format() -> None:
    application_settings = ApplicationSettings(
        output_folder=Path("/Volumes/Scans"),
        output_format=OutputFormat.JPEG,
        scan_preset=ScanPreset.PHOTO,
    )

    scan_request = application_settings.to_scan_request()

    assert scan_request.settings == ScanPreset.PHOTO.settings
    assert scan_request.output_format is OutputFormat.JPEG
