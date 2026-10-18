from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
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


SCANS_FOLDER = Path("/Volumes/Scans")


def test_capture_mode_defaults_to_single() -> None:
    application_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT)

    assert application_settings.capture_mode is CaptureMode.SINGLE


def test_settings_that_differ_only_in_capture_mode_are_different() -> None:
    single_mode_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT)
    document_mode_settings = ApplicationSettings(
        SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT, CaptureMode.DOCUMENT
    )

    assert single_mode_settings != document_mode_settings


def test_capture_mode_does_not_change_the_scan_request() -> None:
    single_mode_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.JPEG, ScanPreset.PHOTO)
    document_mode_settings = ApplicationSettings(
        SCANS_FOLDER, OutputFormat.JPEG, ScanPreset.PHOTO, CaptureMode.DOCUMENT
    )

    assert document_mode_settings.to_scan_request() == single_mode_settings.to_scan_request()
