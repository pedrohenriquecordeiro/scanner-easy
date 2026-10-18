import pytest

from digitalizadora.domain.settings.scan_quality import (
    SUPPORTED_DOTS_PER_INCH,
    is_supported_dots_per_inch,
    pixels_per_page,
    scan_timeout_multiplier,
)


def test_every_resolution_of_the_printer_is_supported() -> None:
    assert SUPPORTED_DOTS_PER_INCH == (75, 100, 150, 200, 300, 400, 600, 1200)


@pytest.mark.parametrize("dots_per_inch", SUPPORTED_DOTS_PER_INCH)
def test_a_listed_resolution_is_supported(dots_per_inch: int) -> None:
    assert is_supported_dots_per_inch(dots_per_inch)


@pytest.mark.parametrize("dots_per_inch", [0, 72, 301, 2400, -300])
def test_an_unlisted_resolution_is_not_supported(dots_per_inch: int) -> None:
    assert not is_supported_dots_per_inch(dots_per_inch)


def test_a_boolean_is_not_a_resolution() -> None:
    assert not is_supported_dots_per_inch(True)


def test_pixels_per_page_at_the_highest_resolution() -> None:
    assert pixels_per_page(1200) == 143_085_600


def test_pixels_per_page_at_the_document_resolution() -> None:
    assert pixels_per_page(300) == 2550 * 3507


@pytest.mark.parametrize("dots_per_inch", [75, 150, 300, 600])
def test_timeout_multiplier_stays_at_one_up_to_the_reference_resolution(dots_per_inch: int) -> None:
    assert scan_timeout_multiplier(dots_per_inch) == 1.0


def test_timeout_multiplier_grows_with_the_area_above_the_reference_resolution() -> None:
    assert scan_timeout_multiplier(1200) == 4.0
