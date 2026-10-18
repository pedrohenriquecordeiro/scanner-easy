import pytest

from digitalizadora.domain.image_adjustment import NO_ADJUSTMENT, ImageAdjustment


def test_the_default_adjustment_changes_nothing() -> None:
    assert not NO_ADJUSTMENT.is_active


def test_an_automatic_crop_alone_is_active() -> None:
    assert ImageAdjustment(auto_crop=True).is_active


def test_the_adjustment_is_immutable() -> None:
    with pytest.raises(AttributeError):
        NO_ADJUSTMENT.auto_crop = True  # type: ignore[misc]
