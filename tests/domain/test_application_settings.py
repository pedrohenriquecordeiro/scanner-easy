from pathlib import Path

from digitalizadora.domain.application_settings import ApplicationSettings
from digitalizadora.domain.capture_mode import CaptureMode
from digitalizadora.domain.imaging.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.output_format import OutputFormat
from digitalizadora.domain.scan_preset import ScanPreset
from digitalizadora.domain.scanning.color_mode import ColorMode
from digitalizadora.domain.scanning.scan_settings import ScanSettings


def test_to_scan_request_combines_preset_settings_and_output_format() -> None:
    application_settings = ApplicationSettings(
        output_folder=Path("/Volumes/Scans"),
        output_format=OutputFormat.JPEG,
        scan_settings=ScanPreset.PHOTO.settings,
    )

    scan_request = application_settings.to_scan_request()

    assert scan_request.settings == ScanPreset.PHOTO.settings
    assert scan_request.output_format is OutputFormat.JPEG


SCANS_FOLDER = Path("/Volumes/Scans")


def test_capture_mode_defaults_to_single() -> None:
    application_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT.settings)

    assert application_settings.capture_mode is CaptureMode.SINGLE


def test_settings_that_differ_only_in_capture_mode_are_different() -> None:
    single_mode_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT.settings)
    document_mode_settings = ApplicationSettings(
        SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT.settings, CaptureMode.DOCUMENT
    )

    assert single_mode_settings != document_mode_settings


def test_capture_mode_does_not_change_the_scan_request() -> None:
    single_mode_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.JPEG, ScanPreset.PHOTO.settings)
    document_mode_settings = ApplicationSettings(
        SCANS_FOLDER, OutputFormat.JPEG, ScanPreset.PHOTO.settings, CaptureMode.DOCUMENT
    )

    assert document_mode_settings.to_scan_request() == single_mode_settings.to_scan_request()


def test_adjustment_defaults_to_no_adjustment() -> None:
    application_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT.settings)

    assert application_settings.adjustment == NO_ADJUSTMENT


def test_to_scan_request_carries_the_adjustment() -> None:
    adjustment = ImageAdjustment(auto_crop=True)
    application_settings = ApplicationSettings(
        SCANS_FOLDER, OutputFormat.PDF, ScanPreset.DOCUMENT.settings, adjustment=adjustment
    )

    assert application_settings.to_scan_request().adjustment == adjustment


def test_to_scan_request_uses_the_custom_scan_settings() -> None:
    custom_settings = ScanSettings(1200, ColorMode.GRAYSCALE)
    application_settings = ApplicationSettings(SCANS_FOLDER, OutputFormat.JPEG, custom_settings)

    assert application_settings.to_scan_request().settings == custom_settings
