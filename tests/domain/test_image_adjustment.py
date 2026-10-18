import pytest

from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment
from digitalizadora.domain.page_rotation import PageRotation


def test_the_default_adjustment_changes_nothing() -> None:
    assert not NO_ADJUSTMENT.is_active


def test_a_rotation_alone_is_active() -> None:
    assert ImageAdjustment(rotation=PageRotation.HALF_TURN).is_active


def test_an_automatic_crop_alone_is_active() -> None:
    assert ImageAdjustment(auto_crop=True).is_active


def test_a_rotation_with_a_crop_is_active() -> None:
    assert ImageAdjustment(rotation=PageRotation.CLOCKWISE_90, auto_crop=True).is_active


def test_the_adjustment_is_immutable() -> None:
    with pytest.raises(AttributeError):
        NO_ADJUSTMENT.auto_crop = True  # type: ignore[misc]
