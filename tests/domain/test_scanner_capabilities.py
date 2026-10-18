import pytest

from digitalizadora.domain.scanner_capabilities import ScannerCapabilities


def build_capabilities(
    resolutions: tuple[int, ...] = (150, 300, 600),
    color_modes: tuple[str, ...] = ("RGB24", "Grayscale8"),
) -> ScannerCapabilities:
    return ScannerCapabilities(
        make_and_model="HP DeskJet 2800 series",
        platen_maximum_width=2550,
        platen_maximum_height=3507,
        supported_resolutions=resolutions,
        supported_color_modes=color_modes,
        supported_document_formats=("image/jpeg",),
    )


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (300, 300),
        (200, 300),
        (150, 150),
        (100, 150),
        (1, 150),
        (151, 300),
        (299, 300),
        (301, 600),
        (600, 600),
        (601, 600),
        (1200, 600),
    ],
)
def test_closest_supported_resolution(requested: int, expected: int) -> None:
    assert build_capabilities().closest_supported_resolution(requested) == expected


def test_closest_supported_resolution_returns_request_when_scanner_lists_none() -> None:
    assert build_capabilities(resolutions=()).closest_supported_resolution(250) == 250


def test_closest_supported_resolution_does_not_depend_on_list_order() -> None:
    capabilities = build_capabilities(resolutions=(600, 150, 300))

    assert capabilities.closest_supported_resolution(200) == 300


@pytest.mark.parametrize(
    ("escl_color_mode", "expected"),
    [
        ("RGB24", True),
        ("Grayscale8", True),
        ("BlackAndWhite1", False),
        ("rgb24", False),
        ("", False),
    ],
)
def test_supports_color_mode(escl_color_mode: str, expected: bool) -> None:
    assert build_capabilities().supports_color_mode(escl_color_mode) is expected


def test_supports_color_mode_is_false_when_scanner_lists_none() -> None:
    assert build_capabilities(color_modes=()).supports_color_mode("RGB24") is False
