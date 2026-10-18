import pytest

from digitalizadora.domain.imaging.image_adjustment import (
    NO_ADJUSTMENT,
    REENCODING_JPEG_QUALITY,
    RENDERED_SIZE_FACTOR,
    ImageAdjustment,
)


def test_the_default_adjustment_changes_nothing() -> None:
    assert not NO_ADJUSTMENT.is_active


def test_an_automatic_crop_alone_is_active() -> None:
    assert ImageAdjustment(auto_crop=True).is_active


def test_the_adjustment_is_immutable() -> None:
    with pytest.raises(AttributeError):
        NO_ADJUSTMENT.auto_crop = True  # type: ignore[misc]


def test_every_image_written_again_takes_the_fixed_quality_of_one_hundred() -> None:
    assert REENCODING_JPEG_QUALITY == 100


def test_a_rewritten_image_is_estimated_at_four_times_the_size_of_the_scanner_one() -> None:
    assert RENDERED_SIZE_FACTOR == 4
