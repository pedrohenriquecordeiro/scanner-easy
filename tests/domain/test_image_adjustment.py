import pytest

from digitalizadora.domain.errors import InvalidSettingsError
from digitalizadora.domain.image_adjustment import (
    DEFAULT_JPEG_QUALITY,
    MAXIMUM_JPEG_QUALITY,
    MINIMUM_JPEG_QUALITY,
    NO_ADJUSTMENT,
    ImageAdjustment,
    is_valid_jpeg_quality,
    rendered_size_factor,
)


def test_the_default_adjustment_changes_nothing() -> None:
    assert not NO_ADJUSTMENT.is_active


def test_an_automatic_crop_alone_is_active() -> None:
    assert ImageAdjustment(auto_crop=True).is_active


def test_the_quality_alone_is_not_active() -> None:
    assert not ImageAdjustment(jpeg_quality=60).is_active


def test_the_adjustment_is_immutable() -> None:
    with pytest.raises(AttributeError):
        NO_ADJUSTMENT.auto_crop = True  # type: ignore[misc]


def test_the_default_quality_is_ninety() -> None:
    assert NO_ADJUSTMENT.jpeg_quality == DEFAULT_JPEG_QUALITY == 90


def test_the_quality_has_the_documented_range() -> None:
    assert (MINIMUM_JPEG_QUALITY, MAXIMUM_JPEG_QUALITY) == (50, 100)


@pytest.mark.parametrize("jpeg_quality", [50, 75, 100])
def test_a_quality_inside_the_range_is_kept(jpeg_quality: int) -> None:
    assert ImageAdjustment(jpeg_quality=jpeg_quality).jpeg_quality == jpeg_quality


@pytest.mark.parametrize("jpeg_quality", [49, 101, 0, -90, 10**30])
def test_a_quality_outside_the_range_is_refused(jpeg_quality: int) -> None:
    with pytest.raises(InvalidSettingsError):
        ImageAdjustment(jpeg_quality=jpeg_quality)


@pytest.mark.parametrize("jpeg_quality", [True, False, 90.0, "90", None])
def test_a_quality_that_is_not_a_whole_number_is_refused(jpeg_quality: object) -> None:
    with pytest.raises(InvalidSettingsError):
        ImageAdjustment(jpeg_quality=jpeg_quality)  # type: ignore[arg-type]


@pytest.mark.parametrize(("jpeg_quality", "expected"), [(50, True), (100, True), (49, False), (True, False)])
def test_is_valid_jpeg_quality_follows_the_range(jpeg_quality: object, expected: bool) -> None:
    assert is_valid_jpeg_quality(jpeg_quality) is expected


@pytest.mark.parametrize(("jpeg_quality", "expected_factor"), [(50, 2), (90, 2), (91, 3), (97, 3), (98, 4), (100, 4)])
def test_the_rendered_size_factor_grows_with_the_quality(jpeg_quality: int, expected_factor: int) -> None:
    assert rendered_size_factor(jpeg_quality) == expected_factor
