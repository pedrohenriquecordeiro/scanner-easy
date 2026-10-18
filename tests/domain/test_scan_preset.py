import pytest

from digitalizadora.domain.color_mode import ColorMode
from digitalizadora.domain.scan_preset import ScanPreset


@pytest.mark.parametrize(
    ("preset", "expected_dots_per_inch", "expected_color_mode"),
    [
        (ScanPreset.DOCUMENT, 300, ColorMode.COLOR),
        (ScanPreset.DOCUMENT_ECONOMY, 200, ColorMode.GRAYSCALE),
        (ScanPreset.PHOTO, 600, ColorMode.COLOR),
    ],
)
def test_preset_settings_table(
    preset: ScanPreset, expected_dots_per_inch: int, expected_color_mode: ColorMode
) -> None:
    assert preset.settings.dots_per_inch == expected_dots_per_inch
    assert preset.settings.color_mode is expected_color_mode


def test_preset_is_created_from_its_stored_text() -> None:
    assert ScanPreset("document_economy") is ScanPreset.DOCUMENT_ECONOMY
